"""Redis-backed session storage for stateless scaling."""
import json
import logging
from datetime import datetime, timezone

from app.config import settings

logger = logging.getLogger(__name__)

_redis = None
USE_REDIS = False
_memory_store: dict[str, dict] = {}


def init_redis() -> bool:
    global _redis, USE_REDIS
    if not settings.redis_url:
        USE_REDIS = False
        logger.warning("REDIS_URL not set — using in-memory store (not scalable)")
        return False

    try:
        import redis

        _redis = redis.from_url(settings.redis_url, decode_responses=True)
        _redis.ping()
        USE_REDIS = True
        logger.info("Connected to Redis")
        return True
    except Exception as exc:
        USE_REDIS = False
        logger.warning("Redis unavailable (%s) — using in-memory store", exc)
        return False


def redis_ping() -> bool:
    if not USE_REDIS or _redis is None:
        return False
    try:
        _redis.ping()
        return True
    except Exception:
        return False


def save_session(session_id: str, data: dict, ttl_seconds: int = 3600) -> None:
    serialized = json.dumps(data)
    if USE_REDIS:
        _redis.setex(f"session:{session_id}", ttl_seconds, serialized)
    else:
        _memory_store[f"session:{session_id}"] = data


def load_session(session_id: str) -> dict:
    if USE_REDIS:
        data = _redis.get(f"session:{session_id}")
        return json.loads(data) if data else {}
    return _memory_store.get(f"session:{session_id}", {})


def append_to_history(session_id: str, role: str, content: str) -> list:
    session = load_session(session_id)
    history = session.get("history", [])
    history.append({
        "role": role,
        "content": content,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    if len(history) > 20:
        history = history[-20:]
    session["history"] = history
    save_session(session_id, session)
    return history
