"""Conexión y topología de RabbitMQ compartida por el consumidor y scripts."""
import json
import logging
import time

import pika

from .config import (CHAT_EXCHANGE, CONSUMED_EVENTS, DEAD_LETTER_EXCHANGE,
                     DEAD_LETTER_QUEUE, GAMIFICATION_EXCHANGE, QUEUE,
                     RABBITMQ_URL)

log = logging.getLogger(__name__)


def connect(retries: int = 30, delay: float = 2.0) -> pika.BlockingConnection:
    for attempt in range(1, retries + 1):
        try:
            return pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
        except pika.exceptions.AMQPConnectionError:
            log.warning("RabbitMQ no disponible (intento %d/%d)", attempt, retries)
            time.sleep(delay)
    raise RuntimeError("No fue posible conectarse a RabbitMQ")


def declare_topology(channel) -> None:
    # Mismos parámetros con que `messages` declara el exchange (no durable);
    # declararlo distinto produciría PRECONDITION_FAILED.
    channel.exchange_declare(exchange=CHAT_EXCHANGE, exchange_type="topic")
    channel.exchange_declare(exchange=GAMIFICATION_EXCHANGE,
                             exchange_type="topic", durable=True)

    # Cola de mensajes muertos: eventos inválidos o que no se pudieron procesar.
    channel.exchange_declare(exchange=DEAD_LETTER_EXCHANGE,
                             exchange_type="fanout", durable=True)
    channel.queue_declare(queue=DEAD_LETTER_QUEUE, durable=True)
    channel.queue_bind(queue=DEAD_LETTER_QUEUE, exchange=DEAD_LETTER_EXCHANGE)

    channel.queue_declare(queue=QUEUE, durable=True, arguments={
        "x-dead-letter-exchange": DEAD_LETTER_EXCHANGE})
    for routing_key in CONSUMED_EVENTS:
        channel.queue_bind(queue=QUEUE, exchange=CHAT_EXCHANGE,
                           routing_key=routing_key)


def publish(channel, exchange: str, routing_key: str, event: dict) -> None:
    channel.basic_publish(
        exchange=exchange, routing_key=routing_key, body=json.dumps(event),
        properties=pika.BasicProperties(
            content_type="application/json",
            delivery_mode=pika.DeliveryMode.Persistent))
