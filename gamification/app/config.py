"""Configuración del servicio de gamificación (variables de entorno)."""
import os

MONGODB_URL = os.environ.get("MONGODB_URL", "mongodb://gamification-mongodb:27017")
RABBITMQ_URL = os.environ.get("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")
USERS_URL = os.environ.get("USERS_URL", "http://users:8000")
MESSAGES_URL = os.environ.get("MESSAGES_URL", "http://messages:8000")
POLL_INTERVAL_SECONDS = float(os.environ.get("POLL_INTERVAL_SECONDS", "3"))

# Exchange donde el núcleo del chat publica sus eventos (lo declara `messages`).
CHAT_EXCHANGE = "chat"
# Exchange propio donde publicamos los eventos de gamificación.
GAMIFICATION_EXCHANGE = "gamification"

QUEUE = "gamification.chat-events"
DEAD_LETTER_EXCHANGE = "gamification.dlx"
DEAD_LETTER_QUEUE = "gamification.chat-events.dead"

CONSUMED_EVENTS = ("chat.message.created", "chat.reaction.added")
