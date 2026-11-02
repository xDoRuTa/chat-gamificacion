"""Demo de punta a punta del flujo de usuario (solo biblioteca estándar).

    python demo.py

Por defecto apunta a docker compose (localhost); en el cluster las URLs se
pasan por variables de entorno (ver k8s/evidencia/flujo-integrado.yaml).

1. Crea un usuario y un canal en el chat base.
2. El usuario envía 3 mensajes  ->  `messages` publica chat.message.created.
3. Gamificación consume los eventos, otorga +10 XP c/u y sube al nivel 2.
4. Se consulta GET /api/v1/gamification/{user_id} como lo haría la UI.
"""
import json
import os
import time
from urllib.request import Request, urlopen

USERS = os.environ.get("USERS_URL", "http://localhost:8001") + "/api/v1"
CHANNELS = os.environ.get("CHANNELS_URL", "http://localhost:8002") + "/api/v1"
MESSAGES = os.environ.get("MESSAGES_URL", "http://localhost:8003") + "/api/v1"
GAMIFICATION = os.environ.get("GAMIFICATION_URL", "http://localhost:8004") + "/api/v1"


def call(method: str, url: str, body: dict | None = None):
    data = json.dumps(body).encode() if body is not None else None
    request = Request(url, data=data, method=method,
                      headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=5) as response:
        return json.loads(response.read())


def main() -> None:
    user = call("POST", f"{USERS}/users", {"display_name": "Ana (demo gamificacion)"})
    channel = call("POST", f"{CHANNELS}/channels", {"name": "demo-gamificacion"})
    print(f"Usuario {user['id']} y canal {channel['id']} creados")

    for text in ("Hola a todos", "¿Alguien entendió sagas?", "Les dejo un resumen"):
        call("POST", f"{MESSAGES}/channels/{channel['id']}/messages",
             {"author_id": user["id"], "content": text})
        print(f"Mensaje enviado: {text}")

    for _ in range(30):
        profile = call("GET", f"{GAMIFICATION}/gamification/{user['id']}")
        if profile["messages_sent"] >= 3:
            break
        time.sleep(1)

    print(json.dumps(profile, indent=2, ensure_ascii=False))
    if profile["level"] >= 2:
        print(f"\n🎉 ¡Nivel {profile['level']} alcanzado! ({profile['xp']} XP)")

    events = [e for e in call("GET", f"{GAMIFICATION}/events?limit=200")
              if e["subject_id"] == user["id"]]
    print("\nEventos publicados por gamificación para este usuario:")
    for event in reversed(events):
        print(f"  {event['type']:<36} {event['data']}")


if __name__ == "__main__":
    main()
