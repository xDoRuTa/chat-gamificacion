"""Lector de eventos del chat por HTTP. Se ejecuta con `python -m app.poller`.

En el cluster del curso el `messages` base no publica en un broker; su único
contrato de eventos es `GET /api/v1/events` (lista en memoria, en orden de
emisión). Este proceso lo consulta periódicamente y entrega cada evento nuevo al
mismo motor que usa el consumidor de RabbitMQ. La deduplicación del motor hace
seguro releer eventos (por ejemplo, al reiniciar el poller).
"""
import json
import logging
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from pydantic import ValidationError
from pymongo.errors import PyMongoError

from . import db, engine
from .config import CONSUMED_EVENTS, MESSAGES_URL, POLL_INTERVAL_SECONDS

log = logging.getLogger("gamification.poller")

# La liveness probe revisa que este archivo se actualice en cada ciclo.
HEARTBEAT = Path("/tmp/poller-heartbeat")


def fetch_events() -> list[dict]:
    with urlopen(f"{MESSAGES_URL}/api/v1/events", timeout=5) as response:
        return json.loads(response.read())


def process(events: list[dict], start: int) -> int:
    """Procesa events[start:] y devuelve el índice desde donde seguir."""
    for index in range(start, len(events)):
        raw = events[index]
        if raw.get("type") not in CONSUMED_EVENTS:
            continue
        try:
            for event in engine.handle_event(raw):
                log.info("Emitido %s para %s", event["type"], event["subject_id"])
        except ValidationError as error:
            log.warning("Evento inválido ignorado: %s", error)
        except PyMongoError:
            log.exception("Base de datos no disponible; se reintentará")
            return index
    return len(events)


def run() -> None:
    next_index = 0
    indexes_ready = False
    while True:
        try:
            if not indexes_ready:
                db.ensure_indexes()
                indexes_ready = True
            events = fetch_events()
            if len(events) < next_index:
                # `messages` se reinició y su lista en memoria empezó de nuevo.
                next_index = 0
            next_index = process(events, next_index)
        except (URLError, TimeoutError, json.JSONDecodeError) as error:
            log.warning("No se pudo leer %s/api/v1/events: %s", MESSAGES_URL, error)
        except PyMongoError:
            log.exception("Base de datos no disponible; se reintentará")
        HEARTBEAT.touch()
        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    run()
