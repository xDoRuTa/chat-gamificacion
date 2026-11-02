"""Reglas del dominio de gamificación: XP, niveles y logros.

Funciones puras, sin acceso a base de datos ni broker, para poder testearlas
de forma aislada.
"""
import math
from dataclasses import dataclass
from typing import Callable

XP_PER_MESSAGE = 10
XP_PER_REACTION = 5

# XP mínimos para el nivel n: LEVEL_STEP * (n - 1)^2  ->  0, 25, 100, 225, 400...
LEVEL_STEP = 25


def level_for_xp(xp: int) -> int:
    return math.isqrt(max(xp, 0) // LEVEL_STEP) + 1


def xp_for_level(level: int) -> int:
    return LEVEL_STEP * (level - 1) ** 2


@dataclass(frozen=True)
class Achievement:
    code: str
    name: str
    description: str
    condition: Callable[[dict], bool]


ACHIEVEMENTS: tuple[Achievement, ...] = (
    Achievement("primer_mensaje", "Primer mensaje",
                "Envió su primer mensaje en el chat.",
                lambda p: p.get("messages_sent", 0) >= 1),
    Achievement("conversador", "Conversador",
                "Envió 50 mensajes en el chat.",
                lambda p: p.get("messages_sent", 0) >= 50),
    Achievement("primera_reaccion", "Primera reacción",
                "Uno de sus mensajes recibió su primera reacción.",
                lambda p: p.get("reactions_received", 0) >= 1),
    Achievement("cien_reacciones", "100 reacciones recibidas",
                "Sus mensajes acumulan 100 reacciones.",
                lambda p: p.get("reactions_received", 0) >= 100),
    Achievement("nivel_5", "Veterano",
                "Alcanzó el nivel 5.",
                lambda p: p.get("level", 1) >= 5),
)


def newly_unlocked(profile: dict) -> list[Achievement]:
    """Logros cuya condición se cumple y que el usuario aún no tiene."""
    owned = {a["code"] for a in profile.get("achievements", [])}
    return [a for a in ACHIEVEMENTS if a.code not in owned and a.condition(profile)]
