"""Infraestructura de aislamiento de base de datos y cliente ASGI sin dependencias."""
import asyncio
from copy import deepcopy
from dataclasses import dataclass
import json
from unittest.mock import MagicMock, patch
from urllib.parse import urlsplit

from pymongo import DESCENDING
from pymongo.errors import DuplicateKeyError

from app import db, main

ORIGINAL_USER_EXISTS = main.user_exists


@dataclass
class SimpleResponse:
    status_code: int
    body: bytes

    def json(self):
        return json.loads(self.body.decode("utf-8"))


class AsgiClient:
    """Cliente HTTP ligero sobre ASGI usando solo biblioteca estándar de Python."""

    def __init__(self, app):
        self.app = app

    def request(self, method: str, url: str, json_body: dict | None = None) -> SimpleResponse:
        parts = urlsplit(url)
        raw_body = json.dumps(json_body).encode("utf-8") if json_body is not None else b""
        headers = [(b"host", b"testserver")]
        if json_body is not None:
            headers.append((b"content-type", b"application/json"))

        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": method.upper(),
            "scheme": "http",
            "path": parts.path,
            "raw_path": parts.path.encode("utf-8"),
            "query_string": parts.query.encode("utf-8"),
            "headers": headers,
            "client": ("127.0.0.1", 50000),
            "server": ("testserver", 80),
        }

        status_code = 500
        chunks: list[bytes] = []
        body_sent = False

        async def receive():
            nonlocal body_sent
            if not body_sent:
                body_sent = True
                return {"type": "http.request", "body": raw_body, "more_body": False}
            return {"type": "http.disconnect"}

        async def send(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            elif message["type"] == "http.response.body":
                chunks.append(message.get("body", b""))

        asyncio.run(self.app(scope, receive, send))
        return SimpleResponse(status_code=status_code, body=b"".join(chunks))

    def get(self, url: str) -> SimpleResponse:
        return self.request("GET", url)

    def post(self, url: str, json: dict | None = None) -> SimpleResponse:
        return self.request("POST", url, json_body=json)


class FakeUpdateResult:
    def __init__(self, modified_count: int):
        self.modified_count = modified_count


class FakeCursor:
    def __init__(self, docs: list[dict], projection: dict | None = None):
        self._docs = docs
        self._projection = projection

    def sort(self, field: str, direction: int):
        reverse = direction == DESCENDING
        self._docs.sort(key=lambda d: d.get(field, ""), reverse=reverse)
        return self

    def limit(self, count: int):
        self._docs = self._docs[:count]
        return self

    def __iter__(self):
        for doc in self._docs:
            item = deepcopy(doc)
            if self._projection:
                include = {k for k, v in self._projection.items() if v}
                exclude = {k for k, v in self._projection.items() if not v}
                if include:
                    item = {k: v for k, v in item.items() if k in include}
                for k in exclude:
                    item.pop(k, None)
            yield item


class InMemoryCollection:
    """Simula las operaciones de PyMongo utilizadas por `app.engine` y `app.main`."""

    def __init__(self):
        self.documents: list[dict] = []

    def clear(self) -> None:
        self.documents.clear()

    def create_index(self, *args, **kwargs) -> None:
        return None

    def _matches(self, doc: dict, query: dict) -> bool:
        for key, condition in query.items():
            if "." in key:
                parts = key.split(".")
                val = doc.get(parts[0], [])
                if isinstance(val, list):
                    values = [item.get(parts[1]) for item in val if isinstance(item, dict)]
                    if isinstance(condition, dict) and "$ne" in condition:
                        if condition["$ne"] in values:
                            return False
                    elif condition not in values:
                        return False
                continue

            doc_val = doc.get(key)
            if isinstance(condition, dict):
                if "$lt" in condition and not (doc_val is not None and doc_val < condition["$lt"]):
                    return False
                if "$ne" in condition and doc_val == condition["$ne"]:
                    return False
            else:
                if doc_val != condition:
                    return False
        return True

    def insert_one(self, document: dict) -> None:
        doc = deepcopy(document)
        if "_id" in doc and any(d.get("_id") == doc["_id"] for d in self.documents):
            raise DuplicateKeyError(f"E11000 duplicate key error: _id={doc['_id']}")
        self.documents.append(doc)

    def find_one(self, query: dict) -> dict | None:
        for doc in self.documents:
            if self._matches(doc, query):
                return deepcopy(doc)
        return None

    def find(self, query: dict, projection: dict | None = None) -> FakeCursor:
        matched = [deepcopy(d) for d in self.documents if self._matches(d, query)]
        return FakeCursor(matched, projection)

    def delete_one(self, query: dict) -> None:
        for idx, doc in enumerate(self.documents):
            if self._matches(doc, query):
                self.documents.pop(idx)
                return

    def update_one(self, query: dict, update: dict) -> FakeUpdateResult:
        for doc in self.documents:
            if self._matches(doc, query):
                if "$set" in update:
                    doc.update(deepcopy(update["$set"]))
                if "$push" in update:
                    for field, value in update["$push"].items():
                        doc.setdefault(field, []).append(deepcopy(value))
                return FakeUpdateResult(modified_count=1)
        return FakeUpdateResult(modified_count=0)

    def find_one_and_update(
        self, query: dict, update: dict, upsert: bool = False, return_document=None
    ) -> dict | None:
        target = None
        for doc in self.documents:
            if self._matches(doc, query):
                target = doc
                break

        if target is None:
            if not upsert:
                return None
            target = deepcopy(query)
            if "$setOnInsert" in update:
                target.update(deepcopy(update["$setOnInsert"]))
            self.documents.append(target)

        if "$inc" in update:
            for field, amount in update["$inc"].items():
                target[field] = target.get(field, 0) + amount
        if "$set" in update:
            target.update(deepcopy(update["$set"]))

        return deepcopy(target)


class IsolatedDatabaseMixin:
    """Mixin/Fixture que aísla la BD en memoria por cada caso de prueba."""

    def setUp(self) -> None:
        super().setUp()
        self.fake_profiles = InMemoryCollection()
        self.fake_xp_transactions = InMemoryCollection()
        self.fake_processed_events = InMemoryCollection()
        self.fake_published_events = InMemoryCollection()
        self.fake_client = MagicMock()

        self._patches = [
            patch.object(db, "profiles", self.fake_profiles),
            patch.object(db, "xp_transactions", self.fake_xp_transactions),
            patch.object(db, "processed_events", self.fake_processed_events),
            patch.object(db, "published_events", self.fake_published_events),
            patch.object(db, "client", self.fake_client),
            patch.object(main, "user_exists", return_value=True),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self) -> None:
        for p in reversed(self._patches):
            p.stop()
        super().tearDown()