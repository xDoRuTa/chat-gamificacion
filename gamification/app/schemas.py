"""Esquemas (Pydantic) de la API REST y de los eventos consumidos/publicados."""
from typing import Literal

from pydantic import BaseModel, Field


# ---------- Eventos consumidos desde el chat base ----------

class ChatEvent(BaseModel):
    """Sobre común de los eventos del chat base."""
    type: str
    subject_id: str
    occurred_at: str
    data: dict


class MessageCreatedData(BaseModel):
    """`data` de `chat.message.created` (publicado por `messages`)."""
    id: str
    channel_id: str
    author_id: str


class ReactionAddedData(BaseModel):
    """`data` de `chat.reaction.added`.

    Contrato propuesto al núcleo: el chat base aún no publica reacciones.
    """
    id: str
    message_id: str
    message_author_id: str = Field(description="Autor del mensaje que recibió la reacción")
    user_id: str = Field(description="Usuario que reaccionó")
    emoji: str = Field(min_length=1, max_length=32)


# ---------- Eventos publicados por gamificación ----------

GamificationEventType = Literal[
    "gamification.xp.awarded",
    "gamification.level_up",
    "gamification.achievement.unlocked",
]


class GamificationEvent(BaseModel):
    id: str
    type: GamificationEventType
    version: int = 1
    subject_id: str = Field(description="user_id afectado")
    occurred_at: str
    data: dict

    model_config = {"json_schema_extra": {"examples": [{
        "id": "6f1c0c7e-3f0a-4a53-9a1e-0f7f0c1b2d3e",
        "type": "gamification.level_up",
        "version": 1,
        "subject_id": "b3c1f2a4-1111-2222-3333-444455556666",
        "occurred_at": "2026-10-19T15:04:05.000000+00:00",
        "data": {"user_id": "b3c1f2a4-1111-2222-3333-444455556666",
                 "previous_level": 1, "new_level": 2, "xp": 30},
    }]}}


# ---------- Respuestas de la API REST ----------

class UnlockedAchievement(BaseModel):
    code: str
    name: str
    description: str
    unlocked_at: str


class GamificationProfile(BaseModel):
    user_id: str
    xp: int = Field(ge=0, description="Puntos de experiencia acumulados")
    level: int = Field(ge=1, description="Nivel calculado a partir de los XP")
    current_level_xp: int = Field(description="XP mínimos del nivel actual")
    next_level_xp: int = Field(description="XP necesarios para el siguiente nivel")
    messages_sent: int = Field(ge=0)
    reactions_received: int = Field(ge=0)
    achievements: list[UnlockedAchievement]

    model_config = {"json_schema_extra": {"examples": [{
        "user_id": "b3c1f2a4-1111-2222-3333-444455556666",
        "xp": 30,
        "level": 2,
        "current_level_xp": 25,
        "next_level_xp": 100,
        "messages_sent": 3,
        "reactions_received": 0,
        "achievements": [{
            "code": "primer_mensaje",
            "name": "Primer mensaje",
            "description": "Envió su primer mensaje en el chat.",
            "unlocked_at": "2026-10-19T15:04:05.000000+00:00",
        }],
    }]}}


class XpTransaction(BaseModel):
    id: str
    user_id: str
    amount: int
    reason: Literal["message.created", "reaction.received"]
    source_event: str = Field(description="Evento del chat que originó los XP")
    occurred_at: str


class LeaderboardEntry(BaseModel):
    position: int
    user_id: str
    xp: int
    level: int


class AchievementDefinition(BaseModel):
    code: str
    name: str
    description: str


class ErrorResponse(BaseModel):
    detail: str

    model_config = {"json_schema_extra": {"examples": [{"detail": "User not found"}]}}
