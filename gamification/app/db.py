"""Acceso a la base de datos propia del servicio de gamificación."""
from pymongo import ASCENDING, DESCENDING, MongoClient

from .config import MONGODB_URL

client = MongoClient(MONGODB_URL, serverSelectionTimeoutMS=3000)
database = client.chat_gamification

# Perfil de gamificación por usuario (_id = user_id).
profiles = database.profiles
# Historial de XP otorgados (una fila por transacción).
xp_transactions = database.xp_transactions
# Claves de eventos ya procesados, para tolerar entregas duplicadas.
processed_events = database.processed_events
# Eventos publicados por este servicio (registro consultable vía API).
published_events = database.published_events


def ensure_indexes() -> None:
    profiles.create_index([("xp", DESCENDING)])
    xp_transactions.create_index([("user_id", ASCENDING), ("occurred_at", DESCENDING)])
    published_events.create_index([("occurred_at", DESCENDING)])
