"""Pruebas unitarias de todos los endpoints REST de gamificación.

Cumple con:
- Al menos 2 pruebas por endpoint, incluyendo explícitamente un caso de error.
- Aislamiento total de MongoDB mediante `IsolatedDatabaseMixin`.
"""
import unittest
from unittest.mock import patch

from pymongo.errors import PyMongoError

from app import engine, main
from tests.helpers import AsgiClient, IsolatedDatabaseMixin


class EndpointTests(IsolatedDatabaseMixin, unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.client = AsgiClient(main.app)

    # ------------------------------------------------------------------
    # 1. GET /health
    # ------------------------------------------------------------------
    def test_health_ok(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_health_method_not_allowed_error(self):
        response = self.client.post("/health")
        self.assertEqual(response.status_code, 405)

    # ------------------------------------------------------------------
    # 2. GET /ready
    # ------------------------------------------------------------------
    def test_ready_ok_when_db_responds(self):
        response = self.client.get("/ready")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ready"})
        self.fake_client.admin.command.assert_called_once_with("ping")

    def test_ready_returns_503_when_db_unavailable(self):
        self.fake_client.admin.command.side_effect = PyMongoError("Connection refused")
        response = self.client.get("/ready")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"detail": "Gamification database unavailable"})

    # ------------------------------------------------------------------
    # 3. GET /api/v1/gamification/{user_id}
    # ------------------------------------------------------------------
    def test_get_profile_existing_user_with_activity(self):
        engine.handle_event({
            "type": "chat.message.created",
            "subject_id": "msg-1",
            "occurred_at": "2026-10-19T12:00:00+00:00",
            "data": {"id": "msg-1", "channel_id": "ch-1", "author_id": "user-ana"},
        })

        response = self.client.get("/api/v1/gamification/user-ana")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["user_id"], "user-ana")
        self.assertEqual(body["xp"], 10)
        self.assertEqual(body["level"], 1)
        self.assertEqual(body["messages_sent"], 1)
        self.assertEqual(body["achievements"][0]["code"], "primer_mensaje")

    def test_get_profile_returns_404_when_user_does_not_exist(self):
        with patch.object(main, "user_exists", return_value=False):
            response = self.client.get("/api/v1/gamification/usuario-inexistente")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"detail": "User not found"})

    # ------------------------------------------------------------------
    # 4. GET /api/v1/gamification/{user_id}/xp-history
    # ------------------------------------------------------------------
    def test_get_xp_history_returns_transactions(self):
        engine.handle_event({
            "type": "chat.message.created",
            "subject_id": "msg-10",
            "occurred_at": "2026-10-19T12:00:00+00:00",
            "data": {"id": "msg-10", "channel_id": "ch-1", "author_id": "user-bob"},
        })

        response = self.client.get("/api/v1/gamification/user-bob/xp-history")
        self.assertEqual(response.status_code, 200)
        history = response.json()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["user_id"], "user-bob")
        self.assertEqual(history[0]["amount"], 10)
        self.assertEqual(history[0]["reason"], "message.created")

    def test_get_xp_history_invalid_limit_returns_422(self):
        response = self.client.get("/api/v1/gamification/user-bob/xp-history?limit=0")
        self.assertEqual(response.status_code, 422)

    # ------------------------------------------------------------------
    # 5. GET /api/v1/leaderboard
    # ------------------------------------------------------------------
    def test_get_leaderboard_sorted_by_xp_desc(self):
        for i in range(3):
            engine.handle_event({
                "type": "chat.message.created",
                "subject_id": f"msg-top-{i}",
                "occurred_at": "2026-10-19T12:00:00+00:00",
                "data": {"id": f"msg-top-{i}", "channel_id": "ch-1", "author_id": "user-top"},
            })
        engine.handle_event({
            "type": "chat.message.created",
            "subject_id": "msg-low-1",
            "occurred_at": "2026-10-19T12:01:00+00:00",
            "data": {"id": "msg-low-1", "channel_id": "ch-1", "author_id": "user-low"},
        })

        response = self.client.get("/api/v1/leaderboard?limit=2")
        self.assertEqual(response.status_code, 200)
        ranking = response.json()
        self.assertEqual(len(ranking), 2)
        self.assertEqual(ranking[0]["user_id"], "user-top")
        self.assertEqual(ranking[0]["position"], 1)
        self.assertEqual(ranking[0]["xp"], 30)
        self.assertEqual(ranking[1]["user_id"], "user-low")
        self.assertEqual(ranking[1]["position"], 2)

    def test_get_leaderboard_limit_exceeded_returns_422(self):
        response = self.client.get("/api/v1/leaderboard?limit=500")
        self.assertEqual(response.status_code, 422)

    # ------------------------------------------------------------------
    # 6. GET /api/v1/achievements
    # ------------------------------------------------------------------
    def test_list_achievements_returns_catalog(self):
        response = self.client.get("/api/v1/achievements")
        self.assertEqual(response.status_code, 200)
        catalog = response.json()
        codes = {item["code"] for item in catalog}
        self.assertIn("primer_mensaje", codes)
        self.assertIn("nivel_5", codes)

    def test_achievements_post_not_allowed_returns_405(self):
        response = self.client.post("/api/v1/achievements", json={"code": "fake"})
        self.assertEqual(response.status_code, 405)

    # ------------------------------------------------------------------
    # 7. GET /api/v1/events
    # ------------------------------------------------------------------
    def test_list_events_filters_by_type(self):
        for i in range(3):
            engine.handle_event({
                "type": "chat.message.created",
                "subject_id": f"msg-ev-{i}",
                "occurred_at": "2026-10-19T12:00:00+00:00",
                "data": {"id": f"msg-ev-{i}", "channel_id": "ch-1", "author_id": "user-ev"},
            })

        response = self.client.get("/api/v1/events?type=gamification.level_up")
        self.assertEqual(response.status_code, 200)
        events = response.json()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["type"], "gamification.level_up")
        self.assertEqual(events[0]["subject_id"], "user-ev")

    def test_list_events_invalid_event_type_returns_422(self):
        response = self.client.get("/api/v1/events?type=evento.inexistente")
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()