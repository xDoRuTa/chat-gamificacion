"""Pruebas de contrato entre el servicio de gamificación y el chat base.

Verifica los tres puntos de acoplamiento definidos en la arquitectura:
1. Contrato de eventos consumidos desde `messages` (`chat.message.created` y
   `chat.reaction.added`) y manejo de mensajes inválidos en el consumidor.
2. Contrato HTTP con el servicio `users` (`GET /api/v1/users/{user_id}`).
3. Contrato de los eventos publicados hacia el exchange `gamification`.
"""
import io
import json
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

from fastapi import HTTPException

from app import consumer, engine, main
from app.schemas import GamificationEvent
from tests.helpers import IsolatedDatabaseMixin, ORIGINAL_USER_EXISTS


class ChatBaseContractTests(IsolatedDatabaseMixin, unittest.TestCase):
    def test_contract_message_created_from_messages_service(self):
        """Valida el payload exacto publicado por `messages` en `chat.message.created`."""
        chat_base_payload = {
            "type": "chat.message.created",
            "subject_id": "9f8e7d6c-5b4a-3210-fedc-ba9876543210",
            "occurred_at": "2026-10-19T14:30:00.123456+00:00",
            "data": {
                "id": "9f8e7d6c-5b4a-3210-fedc-ba9876543210",
                "channel_id": "11111111-2222-3333-4444-555555555555",
                "author_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            },
        }

        emitted = engine.handle_event(chat_base_payload)

        self.assertEqual(len(emitted), 2)
        for raw_event in emitted:
            validated = GamificationEvent.model_validate(raw_event)
            self.assertEqual(validated.version, 1)
            self.assertEqual(validated.subject_id, "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")

        duplicated = engine.handle_event(chat_base_payload)
        self.assertEqual(duplicated, [])

    def test_contract_reaction_added_and_self_reaction_rule(self):
        """Valida el contrato de `chat.reaction.added` y que autoreacciones no den XP."""
        self_reaction = {
            "type": "chat.reaction.added",
            "subject_id": "react-1",
            "occurred_at": "2026-10-19T14:31:00+00:00",
            "data": {
                "id": "react-1",
                "message_id": "msg-1",
                "message_author_id": "user-1",
                "user_id": "user-1",
                "emoji": "👍",
            },
        }
        self.assertEqual(engine.handle_event(self_reaction), [])

        valid_reaction = {
            "type": "chat.reaction.added",
            "subject_id": "react-2",
            "occurred_at": "2026-10-19T14:32:00+00:00",
            "data": {
                "id": "react-2",
                "message_id": "msg-1",
                "message_author_id": "user-1",
                "user_id": "user-2",
                "emoji": "🔥",
            },
        }
        emitted = engine.handle_event(valid_reaction)
        self.assertEqual(len(emitted), 2)
        self.assertEqual(emitted[0]["type"], "gamification.xp.awarded")
        self.assertEqual(emitted[0]["data"]["amount"], 5)

    def test_consumer_sends_malformed_chat_event_to_dead_letter_queue(self):
        """Si el chat base envía un payload que rompe el contrato, va a DLQ sin requeue."""
        channel = MagicMock()
        method = MagicMock(delivery_tag=42)
        broken_payload = json.dumps({
            "type": "chat.message.created",
            "subject_id": "msg-broken",
            "occurred_at": "2026-10-19T14:35:00+00:00",
            "data": {"id": "msg-broken"},
        }).encode()

        consumer.on_message(channel, method, None, broken_payload)

        channel.basic_nack.assert_called_once_with(delivery_tag=42, requeue=False)
        channel.basic_ack.assert_not_called()

    def test_contract_users_service_http_integration(self):
        """Valida el contrato HTTP GET /api/v1/users/{id} con el servicio `users`."""
        ok_response = MagicMock()
        ok_response.status = 200
        ok_ctx = MagicMock()
        ok_ctx.__enter__.return_value = ok_response

        with patch.object(main, "urlopen", return_value=ok_ctx) as mock_urlopen:
            self.assertTrue(ORIGINAL_USER_EXISTS("user-123"))
            called_url = mock_urlopen.call_args[0][0]
            self.assertTrue(called_url.endswith("/api/v1/users/user-123"))

        not_found = HTTPError(
            url="http://users:8000/api/v1/users/missing",
            code=404,
            msg="Not Found",
            hdrs={},
            fp=io.BytesIO(b""),
        )
        with patch.object(main, "urlopen", side_effect=not_found):
            self.assertFalse(ORIGINAL_USER_EXISTS("missing"))

        with patch.object(main, "urlopen", side_effect=URLError("Connection refused")):
            with self.assertRaises(HTTPException) as exc_ctx:
                ORIGINAL_USER_EXISTS("user-123")
            self.assertEqual(exc_ctx.exception.status_code, 503)


if __name__ == "__main__":
    unittest.main()