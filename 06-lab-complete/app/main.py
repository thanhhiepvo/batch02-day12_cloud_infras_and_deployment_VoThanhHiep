"""
Production AI Agent — Kết hợp tất cả Day 12 concepts

Checklist:
  ✅ Config từ environment (12-factor)
  ✅ Structured JSON logging
  ✅ API Key authentication
  ✅ Rate limiting (Redis-backed)
  ✅ Cost guard (monthly budget)
  ✅ Conversation history (Redis-backed)
  ✅ Health check + Readiness probe
  ✅ Graceful shutdown
  ✅ Stateless design
"""
import time
import signal
import logging
import json
import uuid
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

from app.config import settings
from app.auth import verify_api_key
from app.rate_limiter import check_rate_limit
from app.cost_guard import check_budget, record_usage
from app.session import (
    init_redis,
    redis_ping,
    USE_REDIS,
    append_to_history,
    load_session,
)
from utils.mock_llm import ask as llm_ask

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format='{"ts":"%(asctime)s","lvl":"%(levelname)s","msg":"%(message)s"}',
)
logger = logging.getLogger(__name__)

START_TIME = time.time()
_is_ready = False
_request_count = 0
_error_count = 0


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _is_ready
    logger.info(json.dumps({
        "event": "startup",
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "instance_id": settings.instance_id,
    }))
    init_redis()
    time.sleep(0.1)
    _is_ready = True
    logger.info(json.dumps({"event": "ready", "storage": "redis" if USE_REDIS else "in-memory"}))

    yield

    _is_ready = False
    logger.info(json.dumps({"event": "shutdown", "instance_id": settings.instance_id}))


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
)


@app.middleware("http")
async def request_middleware(request: Request, call_next):
    global _request_count, _error_count
    start = time.time()
    _request_count += 1
    try:
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        if "server" in response.headers:
            del response.headers["server"]
        duration = round((time.time() - start) * 1000, 1)
        logger.info(json.dumps({
            "event": "request",
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "ms": duration,
            "instance_id": settings.instance_id,
        }))
        return response
    except Exception:
        _error_count += 1
        raise


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    session_id: str | None = None


class AskResponse(BaseModel):
    session_id: str
    question: str
    answer: str
    model: str
    turn: int
    history_count: int
    served_by: str
    storage: str
    timestamp: str


@app.get("/", tags=["Info"])
def root():
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "instance_id": settings.instance_id,
        "endpoints": {
            "ask": "POST /ask (requires X-API-Key)",
            "health": "GET /health",
            "ready": "GET /ready",
            "history": "GET /ask/{session_id}/history",
        },
    }


@app.post("/ask", response_model=AskResponse, tags=["Agent"])
async def ask_agent(
    body: AskRequest,
    request: Request,
    user_id: str = Depends(verify_api_key),
):
    check_rate_limit(user_id)
    check_budget(user_id)

    session_id = body.session_id or str(uuid.uuid4())
    append_to_history(session_id, "user", body.question)

    input_tokens = len(body.question.split()) * 2
    answer = llm_ask(body.question)
    output_tokens = len(answer.split()) * 2
    record_usage(user_id, input_tokens, output_tokens)

    history = append_to_history(session_id, "assistant", answer)
    user_turns = len([m for m in history if m["role"] == "user"])

    logger.info(json.dumps({
        "event": "agent_call",
        "session_id": session_id,
        "q_len": len(body.question),
        "client": str(request.client.host) if request.client else "unknown",
        "instance_id": settings.instance_id,
    }))

    return AskResponse(
        session_id=session_id,
        question=body.question,
        answer=answer,
        model=settings.llm_model,
        turn=user_turns,
        history_count=len(history),
        served_by=settings.instance_id,
        storage="redis" if USE_REDIS else "in-memory",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@app.get("/ask/{session_id}/history", tags=["Agent"])
def get_history(session_id: str, _key: str = Depends(verify_api_key)):
    session = load_session(session_id)
    if not session:
        raise HTTPException(404, f"Session {session_id} not found or expired")
    messages = session.get("history", [])
    return {
        "session_id": session_id,
        "messages": messages,
        "count": len(messages),
    }


@app.get("/health", tags=["Operations"])
def health():
    redis_ok = redis_ping() if USE_REDIS else None
    status = "ok"
    if USE_REDIS and not redis_ok:
        status = "degraded"

    return {
        "status": status,
        "version": settings.app_version,
        "environment": settings.environment,
        "instance_id": settings.instance_id,
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "total_requests": _request_count,
        "storage": "redis" if USE_REDIS else "in-memory",
        "redis_connected": redis_ok,
        "checks": {"llm": "mock" if not settings.openai_api_key else "openai"},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/ready", tags=["Operations"])
def ready():
    if not _is_ready:
        raise HTTPException(503, "Not ready")
    if USE_REDIS and not redis_ping():
        raise HTTPException(503, "Redis not available")
    return {"ready": True, "instance_id": settings.instance_id}


def _handle_signal(signum, _frame):
    logger.info(json.dumps({"event": "signal", "signum": signum}))

signal.signal(signal.SIGTERM, _handle_signal)


if __name__ == "__main__":
    logger.info("Starting %s on %s:%s", settings.app_name, settings.host, settings.port)
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        timeout_graceful_shutdown=30,
    )
