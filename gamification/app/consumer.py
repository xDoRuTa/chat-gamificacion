"""Consumidor de eventos del chat. Se ejecuta con `python -m app.consumer`.

Corre en un contenedor separado de la API: si falla, el chat y la consulta de
perfiles siguen funcionando, y los eventos esperan en la cola durable.
"""
import json
import logging
import time

import pika
from pydantic import ValidationError
from pymongo.errors import PyMongoError

from . import broker, db, engine
from .config import GAMIFICATION_EXCHANGE, QUEUE

log = logging.getLogger("gamification.consumer")


def on_message(channel, method, properties, body: bytes) -> None:
    try:
        outgoing = engine.handle_event(json.loads(body))
    except (json.JSONDecodeError, ValidationError) as error:
        log.warning("Evento inválido enviado a la cola de muertos: %s", error)
        channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        return
    except PyMongoError:
        log.exception("Base de datos no disponible; el evento se reintentará")
        time.sleep(2)
        channel.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
        return
    except Exception:
        log.exception("Error inesperado; evento enviado a la cola de muertos")
        channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        return

    for event in outgoing:
        broker.publish(channel, GAMIFICATION_EXCHANGE, event["type"], event)
        log.info("Publicado %s para %s", event["type"], event["subject_id"])
    channel.basic_ack(delivery_tag=method.delivery_tag)


def run() -> None:
    db.ensure_indexes()
    while True:
        try:
            connection = broker.connect()
            channel = connection.channel()
            broker.declare_topology(channel)
            channel.basic_qos(prefetch_count=10)
            channel.basic_consume(queue=QUEUE, on_message_callback=on_message)
            log.info("Esperando eventos en la cola %s...", QUEUE)
            channel.start_consuming()
        except pika.exceptions.AMQPConnectionError:
            log.warning("Conexión con RabbitMQ perdida; reconectando...")
            time.sleep(2)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("pika").setLevel(logging.WARNING)
    run()
