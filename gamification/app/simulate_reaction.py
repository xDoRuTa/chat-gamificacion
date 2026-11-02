"""Publica un `chat.reaction.added` de prueba en el exchange del chat.

El chat base todavía no publica reacciones; este script emite el evento con el
contrato propuesto para poder demostrar el flujo de punta a punta:

    docker compose exec gamification python -m app.simulate_reaction \
        <message_id> <message_author_id> <user_id> [emoji]
"""
import argparse
from datetime import datetime, timezone
from uuid import uuid4

from . import broker
from .config import CHAT_EXCHANGE


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("message_id")
    parser.add_argument("message_author_id")
    parser.add_argument("user_id", help="Usuario que reacciona")
    parser.add_argument("emoji", nargs="?", default="👍")
    args = parser.parse_args()

    reaction_id = str(uuid4())
    event = {"type": "chat.reaction.added", "subject_id": reaction_id,
             "occurred_at": datetime.now(timezone.utc).isoformat(),
             "data": {"id": reaction_id, "message_id": args.message_id,
                      "message_author_id": args.message_author_id,
                      "user_id": args.user_id, "emoji": args.emoji}}

    connection = broker.connect(retries=3)
    channel = connection.channel()
    broker.declare_topology(channel)
    broker.publish(channel, CHAT_EXCHANGE, event["type"], event)
    connection.close()
    print(f"Publicado chat.reaction.added {reaction_id}")


if __name__ == "__main__":
    main()
