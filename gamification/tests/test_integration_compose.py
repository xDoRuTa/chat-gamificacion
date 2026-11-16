"""Prueba de integración de punta a punta sobre el stack de Docker Compose.

Valida la comunicación real entre:
  users -> channels -> messages -> RabbitMQ -> gamification-consumer -> MongoDB -> gamification API
"""
import json
import os
import time
import unittest
from urllib.error import URLError
from urllib.request import Request, urlopen


def _detect_base_urls() -> dict[str, str]:
    """Detecta si se ejecuta dentro de la red Docker (`microsvcs`) o en el host."""
    in_docker = os.path.exists("/.dockerenv")
    if in_docker:
        return {
            "users": os.environ.get("USERS_URL", "http://users:8000"),
            "channels": os.environ.get("CHANNELS_URL", "http://channels:8000"),
            "messages": os.environ.get("MESSAGES_URL", "http://messages:8000"),
            "gamification": os.environ.get("GAMIFICATION_URL", "http://localhost:8000"),
        }
    return {
        "users": os.environ.get("USERS_URL", "http://localhost:8001"),
        "channels": os.environ.get("CHANNELS_URL", "http://localhost:8002"),
        "messages": os.environ.get("MESSAGES_URL", "http://localhost:8003"),
        "gamification": os.environ.get("GAMIFICATION_URL", "http://localhost:8004"),
    }


def _http_json(method: str, url: str, body: dict | None = None) -> tuple[int, dict | list]:
    data = json.dumps(body).encode() if body is not None else None
    req = Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=5) as resp:
        return resp.status, json.loads(resp.read())


class DockerComposeIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.urls = _detect_base_urls()
        try:
            status, _ = _http_json("GET", f"{cls.urls['gamification']}/ready")
            if status != 200:
                raise unittest.SkipTest("Stack Docker Compose no está listo (/ready != 200)")
        except (URLError, TimeoutError, OSError) as exc:
            raise unittest.SkipTest(
                f"Servicios de Docker Compose no accesibles ({exc}). "
                "Levanta el entorno con `docker compose up -d` para ejecutar esta prueba."
            )

    def test_end_to_end_chat_messages_award_xp_and_level_up(self):
        """Flujo completo: crear usuario/canal, enviar 3 mensajes y verificar XP/nivel/logros."""
        # 1. Crear usuario y canal en el chat base
        _, user = _http_json(
            "POST", f"{self.urls['users']}/api/v1/users", {"display_name": "Test Compose E2E"}
        )
        _, channel = _http_json(
            "POST", f"{self.urls['channels']}/api/v1/channels", {"name": "test-compose-e2e"}
        )
        user_id = user["id"]
        channel_id = channel["id"]

        # 2. Publicar 3 mensajes en el chat base (emite chat.message.created por RabbitMQ)
        for idx in range(3):
            status, _ = _http_json(
                "POST",
                f"{self.urls['messages']}/api/v1/channels/{channel_id}/messages",
                {"author_id": user_id, "content": f"Mensaje de integración #{idx + 1}"},
            )
            self.assertIn(status, (200, 201))

        # 3. Esperar procesamiento asíncrono del consumidor de gamificación
        profile = None
        for _ in range(30):
            _, profile = _http_json("GET", f"{self.urls['gamification']}/api/v1/gamification/{user_id}")
            if profile["messages_sent"] >= 3 and profile["level"] >= 2:
                break
            time.sleep(0.5)

        self.assertIsNotNone(profile)
        self.assertEqual(profile["messages_sent"], 3)
        self.assertEqual(profile["xp"], 30)
        self.assertEqual(profile["level"], 2)
        achievement_codes = {a["code"] for a in profile["achievements"]}
        self.assertIn("primer_mensaje", achievement_codes)

        # 4. Verificar historial de XP y eventos publicados
        _, history = _http_json(
            "GET", f"{self.urls['gamification']}/api/v1/gamification/{user_id}/xp-history"
        )
        self.assertEqual(len(history), 3)

        _, events = _http_json("GET", f"{self.urls['gamification']}/api/v1/events?limit=200")
        user_event_types = {e["type"] for e in events if e["subject_id"] == user_id}
        self.assertIn("gamification.xp.awarded", user_event_types)
        self.assertIn("gamification.level_up", user_event_types)
        self.assertIn("gamification.achievement.unlocked", user_event_types)


if __name__ == "__main__":
    unittest.main()