"""Production-ready AI agent for Day 12 final project."""
import json
import logging
import signal
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

from app.auth import verify_api_key
from app.config import settings
from app.cost_guard import check_budget, estimate_cost, record_cost, usage
from app.rate_limiter import check_rate_limit
from app.storage import storage
from utils.mock_llm import ask as llm_ask


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO), handlers=[handler])
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
        "storage": "redis" if storage.using_redis else "memory",
    }))
    storage.ping()
    _is_ready = True
    logger.info(json.dumps({"event": "ready"}))
    yield
    _is_ready = False
    logger.info(json.dumps({"event": "shutdown"}))


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
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if "server" in response.headers:
            del response.headers["server"]
        logger.info(json.dumps({
            "event": "request",
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "duration_ms": round((time.time() - start) * 1000, 1),
        }))
        return response
    except Exception:
        _error_count += 1
        logger.exception("request failed")
        raise


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    user_id: str = Field("default-user", min_length=1, max_length=120)


class AskResponse(BaseModel):
    user_id: str
    question: str
    answer: str
    model: str
    history_length: int
    usage: dict
    timestamp: str


def _history_key(user_id: str) -> str:
    return f"history:{user_id}"


def _append_history(user_id: str, role: str, content: str) -> None:
    key = _history_key(user_id)
    storage.rpush_json(key, {
        "role": role,
        "content": content,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    storage.ltrim(key, -20, -1)
    storage.expire(key, settings.session_ttl_seconds)


def _history(user_id: str) -> list[dict]:
    return storage.lrange_json(_history_key(user_id), 0, -1)


@app.get("/", tags=["Info"])
def root():
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "storage": "redis" if storage.using_redis else "memory",
        "endpoints": {
            "ask": "POST /ask (requires X-API-Key)",
            "health": "GET /health",
            "ready": "GET /ready",
        },
    }


@app.post("/ask", response_model=AskResponse, tags=["Agent"])
async def ask_agent(
    body: AskRequest,
    request: Request,
    _user_from_key: str = Depends(verify_api_key),
):
    user_id = body.user_id
    check_rate_limit(user_id)

    input_tokens = len(body.question.split()) * 2
    estimated_input_cost = estimate_cost(input_tokens, 0)
    check_budget(user_id, estimated_input_cost)

    _append_history(user_id, "user", body.question)
    answer = llm_ask(body.question)
    _append_history(user_id, "assistant", answer)

    output_tokens = len(answer.split()) * 2
    total_cost = estimate_cost(input_tokens, output_tokens)
    check_budget(user_id, total_cost)
    record_cost(user_id, total_cost)

    logger.info(json.dumps({
        "event": "agent_call",
        "user_id": user_id,
        "question_length": len(body.question),
        "client": str(request.client.host) if request.client else "unknown",
    }))

    return AskResponse(
        user_id=user_id,
        question=body.question,
        answer=answer,
        model=settings.llm_model,
        history_length=len(_history(user_id)),
        usage=usage(user_id),
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@app.get("/history/{user_id}", tags=["Agent"])
def history(user_id: str, _key: str = Depends(verify_api_key)):
    messages = _history(user_id)
    return {"user_id": user_id, "count": len(messages), "messages": messages}


@app.delete("/history/{user_id}", tags=["Agent"])
def clear_history(user_id: str, _key: str = Depends(verify_api_key)):
    key = _history_key(user_id)
    if storage.client:
        storage.client.delete(key)
    else:
        storage.memory_lists.pop(key, None)
    return {"deleted": user_id}


@app.get("/health", tags=["Operations"])
def health():
    return {
        "status": "ok",
        "version": settings.app_version,
        "environment": settings.environment,
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "total_requests": _request_count,
        "checks": {"llm": "mock" if not settings.openai_api_key else "openai"},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/ready", tags=["Operations"])
def ready():
    if not _is_ready:
        raise HTTPException(503, "Not ready")
    try:
        storage.ping()
    except Exception as exc:
        raise HTTPException(503, f"Storage not ready: {exc}") from exc
    return {"ready": True, "storage": "redis" if storage.using_redis else "memory"}


@app.get("/metrics", tags=["Operations"])
def metrics(_key: str = Depends(verify_api_key)):
    return {
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "total_requests": _request_count,
        "error_count": _error_count,
        "storage": "redis" if storage.using_redis else "memory",
    }


def _handle_signal(signum, _frame):
    logger.info(json.dumps({"event": "SIGTERM", "signum": signum}))


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
