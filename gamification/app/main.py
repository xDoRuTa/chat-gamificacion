"""API REST del servicio de gamificación de participación."""
from contextlib import asynccontextmanager
from typing import Annotated
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import urlopen

from fastapi import APIRouter, FastAPI, HTTPException, Path, Query, Request
from fastapi.responses import JSONResponse
from pymongo import DESCENDING
from pymongo.errors import PyMongoError

from . import db, rules
from .config import USERS_URL
from .schemas import (AchievementDefinition, ErrorResponse, GamificationEvent,
                      GamificationEventType, GamificationProfile,
                      LeaderboardEntry, XpTransaction)

DESCRIPTION = """
Capacidad vertical de **gamificación** para el chat base.

Consume de forma asíncrona (RabbitMQ) los eventos `chat.message.created` y
`chat.reaction.added`, otorga **XP**, calcula el **nivel** y desbloquea
**logros**. Publica `gamification.xp.awarded`, `gamification.level_up` y
`gamification.achievement.unlocked` en el exchange `gamification`.

Esta API es de solo lectura: el estado solo cambia a partir de eventos.
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        db.ensure_indexes()
    except PyMongoError:
        pass  # La API responde 503 en cada consulta mientras Mongo no esté.
    yield


app = FastAPI(
    lifespan=lifespan,
    title="Chat Gamification",
    version="1.0.0",
    description=DESCRIPTION,
    openapi_tags=[
        {"name": "Perfiles", "description": "XP, nivel y logros por usuario."},
        {"name": "Ranking", "description": "Usuarios con más XP."},
        {"name": "Logros", "description": "Catálogo de logros disponibles."},
        {"name": "Eventos", "description": "Eventos publicados por el servicio."},
    ],
)
v1 = APIRouter(prefix="/api/v1")

UserId = Annotated[str, Path(description="Identificador del usuario (servicio `users`)")]
NOT_FOUND = {404: {"model": ErrorResponse, "description": "Usuario inexistente"}}
UNAVAILABLE = {503: {"model": ErrorResponse, "description": "Dependencia no disponible"}}


@app.exception_handler(PyMongoError)
def database_unavailable(request: Request, error: PyMongoError):
    return JSONResponse(status_code=503,
                        content={"detail": "Gamification database unavailable"})


def user_exists(user_id: str) -> bool:
    """Valida contra la API pública de `users` (nunca contra su base)."""
    try:
        with urlopen(f"{USERS_URL}/api/v1/users/{quote(user_id)}", timeout=2) as response:
            return response.status == 200
    except HTTPError as error:
        if error.code == 404:
            return False
        raise HTTPException(status_code=502, detail="Users service failed")
    except URLError:
        raise HTTPException(status_code=503, detail="Users service unavailable")


def to_profile(document: dict) -> GamificationProfile:
    level = document.get("level", 1)
    return GamificationProfile(
        user_id=document["user_id"],
        xp=document.get("xp", 0),
        level=level,
        current_level_xp=rules.xp_for_level(level),
        next_level_xp=rules.xp_for_level(level + 1),
        messages_sent=document.get("messages_sent", 0),
        reactions_received=document.get("reactions_received", 0),
        achievements=document.get("achievements", []),
    )


@app.get("/health", tags=["Salud"], summary="Liveness: el proceso responde")
def health():
    return {"status": "ok"}


@app.get("/ready", tags=["Salud"], summary="Readiness: la base de datos responde",
         responses=UNAVAILABLE)
def ready():
    db.client.admin.command("ping")  # PyMongoError -> 503 por el handler global
    return {"status": "ready"}


@v1.get("/gamification/{user_id}", response_model=GamificationProfile,
        tags=["Perfiles"], summary="Estado de gamificación de un usuario",
        responses={**NOT_FOUND, **UNAVAILABLE})
def get_profile(user_id: UserId):
    """Devuelve XP, nivel, progreso al siguiente nivel y logros.

    Un usuario existente sin actividad obtiene un perfil en nivel 1 con 0 XP.
    """
    document = db.profiles.find_one({"_id": user_id})
    if document is None:
        if not user_exists(user_id):
            raise HTTPException(status_code=404, detail="User not found")
        document = {"user_id": user_id}
    return to_profile(document)


@v1.get("/gamification/{user_id}/xp-history", response_model=list[XpTransaction],
        tags=["Perfiles"], summary="Historial de XP de un usuario")
def get_xp_history(user_id: UserId,
                   limit: Annotated[int, Query(ge=1, le=100)] = 20):
    return list(db.xp_transactions.find({"user_id": user_id}, {"_id": 0})
                .sort("occurred_at", DESCENDING).limit(limit))


@v1.get("/leaderboard", response_model=list[LeaderboardEntry],
        tags=["Ranking"], summary="Ranking de usuarios por XP")
def get_leaderboard(limit: Annotated[int, Query(ge=1, le=100)] = 10):
    top = db.profiles.find({}, {"_id": 0, "user_id": 1, "xp": 1, "level": 1}) \
        .sort("xp", DESCENDING).limit(limit)
    return [LeaderboardEntry(position=i, **p) for i, p in enumerate(top, start=1)]


@v1.get("/achievements", response_model=list[AchievementDefinition],
        tags=["Logros"], summary="Catálogo de logros")
def list_achievements():
    return [AchievementDefinition(code=a.code, name=a.name, description=a.description)
            for a in rules.ACHIEVEMENTS]


@v1.get("/events", response_model=list[GamificationEvent], tags=["Eventos"],
        summary="Eventos publicados (exploración local del contrato)")
def list_events(type: GamificationEventType | None = None,
                limit: Annotated[int, Query(ge=1, le=200)] = 50):
    query = {"type": type} if type else {}
    return list(db.published_events.find(query, {"_id": 0})
                .sort("occurred_at", DESCENDING).limit(limit))


app.include_router(v1)
