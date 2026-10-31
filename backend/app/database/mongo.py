"""MongoDB wrapper (activity/audit logs + flexible product metadata) with in-memory fallback."""
import logging
from datetime import datetime, timezone
from typing import Any

from app.core.config import settings

log = logging.getLogger(__name__)


class MongoStore:
    def __init__(self, url: str, db_name: str):
        self._mem: dict[str, list[dict]] = {}
        self._db = None
        if url:
            try:
                from pymongo import MongoClient

                client = MongoClient(url, serverSelectionTimeoutMS=2000)
                client.admin.command("ping")
                self._db = client[db_name]
                self._db["activity_logs"].create_index([("user_id", 1), ("ts", -1)])
                self._db["audit_logs"].create_index([("user_id", 1), ("ts", -1)])
                self._db["product_metadata"].create_index("category", unique=True)
            except Exception as exc:
                log.warning("MongoDB unavailable, using in-memory store: %s", exc)
                self._db = None

    @property
    def backend(self) -> str:
        return "mongodb" if self._db is not None else "memory"

    def ping(self) -> bool:
        try:
            if self._db is not None:
                self._db.client.admin.command("ping")
            return True
        except Exception:
            return False

    def insert(self, collection: str, doc: dict[str, Any]) -> None:
        doc = {**doc, "ts": datetime.now(timezone.utc)}
        if self._db is not None:
            try:
                self._db[collection].insert_one(doc)
                return
            except Exception as exc:
                log.warning("Mongo insert failed: %s", exc)
                doc.pop("_id", None)
        self._mem.setdefault(collection, []).append(doc)

    def recent(self, collection: str, filt: dict[str, Any], limit: int = 20) -> list[dict]:
        if self._db is not None:
            try:
                cursor = self._db[collection].find(filt, {"_id": 0}).sort("ts", -1).limit(limit)
                return list(cursor)
            except Exception as exc:
                log.warning("Mongo find failed: %s", exc)
        rows = [
            d for d in self._mem.get(collection, []) if all(d.get(k) == v for k, v in filt.items())
        ]
        return sorted(rows, key=lambda d: d["ts"], reverse=True)[:limit]

    def upsert(self, collection: str, key: dict[str, Any], doc: dict[str, Any]) -> None:
        if self._db is not None:
            try:
                self._db[collection].update_one(key, {"$set": doc}, upsert=True)
                return
            except Exception as exc:
                log.warning("Mongo upsert failed: %s", exc)
        rows = self._mem.setdefault(collection, [])
        for row in rows:
            if all(row.get(k) == v for k, v in key.items()):
                row.update(doc)
                return
        rows.append({**key, **doc, "ts": datetime.now(timezone.utc)})

    def get(self, collection: str, filt: dict[str, Any]) -> dict | None:
        rows = self.recent(collection, filt, limit=1)
        return rows[0] if rows else None


mongo = MongoStore(settings.mongo_url, settings.mongo_db)


def log_activity(user_id: int | None, action: str, **details: Any) -> None:
    mongo.insert("activity_logs", {"user_id": user_id, "action": action, "details": details})


def log_audit(user_id: int, action: str, **details: Any) -> None:
    mongo.insert("audit_logs", {"user_id": user_id, "action": action, "details": details})
