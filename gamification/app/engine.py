"""Motor de XP: transforma eventos del chat en XP, niveles y logros."""
import logging
from datetime import datetime, timezone
from uuid import uuid4

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from . import db, rules
from .schemas import ChatEvent, MessageCreatedData, ReactionAddedData

log = logging.getLogger(__name__)

COUNTERS = ("messages_sent", "reactions_received")


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_event(event_type: str, user_id: str, data: dict) -> dict:
    """Crea un evento de gamificación y lo registra en la base propia."""
    event = {"id": str(uuid4()), "type": event_type, "version": 1,
             "subject_id": user_id, "occurred_at": now(), "data": data}
    db.published_events.insert_one({**event})
    return event


def handle_event(raw: dict) -> list[dict]:
    """Procesa un evento del chat y devuelve los eventos a publicar.

    La entrega del broker es "al menos una vez": cada evento se marca como
    procesado y los duplicados se ignoran.
    """
    event = ChatEvent.model_validate(raw)
    key = f"{event.type}:{event.subject_id}"
    try:
        db.processed_events.insert_one({"_id": key, "processed_at": now()})
    except DuplicateKeyError:
        log.info("Evento duplicado ignorado: %s", key)
        return []

    try:
        if event.type == "chat.message.created":
            message = MessageCreatedData.model_validate(event.data)
            return award_xp(message.author_id, rules.XP_PER_MESSAGE,
                            "message.created", key, "messages_sent")
        if event.type == "chat.reaction.added":
            reaction = ReactionAddedData.model_validate(event.data)
            if reaction.user_id == reaction.message_author_id:
                log.info("Reacción propia sin XP: %s", key)
                return []
            return award_xp(reaction.message_author_id, rules.XP_PER_REACTION,
                            "reaction.received", key, "reactions_received")
        log.info("Evento sin reglas de gamificación: %s", event.type)
        return []
    except Exception:
        # Libera la marca para que el evento pueda reprocesarse más adelante.
        db.processed_events.delete_one({"_id": key})
        raise


def award_xp(user_id: str, amount: int, reason: str, source_event: str,
             counter: str) -> list[dict]:
    other_counters = {c: 0 for c in COUNTERS if c != counter}
    profile = db.profiles.find_one_and_update(
        {"_id": user_id},
        {"$inc": {"xp": amount, counter: 1},
         "$set": {"updated_at": now()},
         "$setOnInsert": {"user_id": user_id, "level": 1, "achievements": [],
                          **other_counters}},
        upsert=True, return_document=ReturnDocument.AFTER)

    db.xp_transactions.insert_one({
        "id": str(uuid4()), "user_id": user_id, "amount": amount,
        "reason": reason, "source_event": source_event, "occurred_at": now()})
    events = [new_event("gamification.xp.awarded", user_id, {
        "user_id": user_id, "amount": amount, "reason": reason,
        "total_xp": profile["xp"]})]

    new_level = rules.level_for_xp(profile["xp"])
    if new_level > profile["level"]:
        # Condición sobre el nivel: si dos consumidores compiten, solo uno emite.
        result = db.profiles.update_one(
            {"_id": user_id, "level": {"$lt": new_level}},
            {"$set": {"level": new_level}})
        if result.modified_count:
            events.append(new_event("gamification.level_up", user_id, {
                "user_id": user_id, "previous_level": profile["level"],
                "new_level": new_level, "xp": profile["xp"]}))
            profile["level"] = new_level

    for achievement in rules.newly_unlocked(profile):
        unlocked = {"code": achievement.code, "name": achievement.name,
                    "description": achievement.description,
                    "unlocked_at": now()}
        result = db.profiles.update_one(
            {"_id": user_id, "achievements.code": {"$ne": achievement.code}},
            {"$push": {"achievements": unlocked}})
        if result.modified_count:
            events.append(new_event("gamification.achievement.unlocked",
                                    user_id, {"user_id": user_id, **unlocked}))
    return events
