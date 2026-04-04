import logging
import time
import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.config import EnvSettings, load_settings
from app.dependencies import get_api_logger
from app.models.api_log import APICallLog
from app.routers.auth import router as auth_router
from app.routers.admin_users import router as admin_users_router
from app.routers.pages import router as pages_router
from app.routers.openstax import router as openstax_router
from app.modules.dialogue.router import router as dialogue_router
from app.modules.curriculum.router import router as curriculum_router
from app.modules.gathering.router import router as gathering_router
from app.modules.gathering.pdf_router import router as pdf_router
from app.ui import init_nicegui


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = load_settings()

    # Set up logging
    log_level = logging.DEBUG if settings.app.debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Ensure data directories exist
    Path(settings.app.data_dir, "sessions").mkdir(parents=True, exist_ok=True)
    Path(settings.logging.log_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.pdf.upload_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.openstax.upload_dir).mkdir(parents=True, exist_ok=True)
    if settings.qdrant.path:
        Path(settings.qdrant.path).mkdir(parents=True, exist_ok=True)

    logging.getLogger("llm_tutor").info("LLM Tutor starting up")
    yield
    logging.getLogger("llm_tutor").info("LLM Tutor shutting down")


app = FastAPI(title="LLM Tutor", lifespan=lifespan)

env_settings = EnvSettings()
cors_origins = [origin.strip() for origin in env_settings.cors_origins.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins or ["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _extract_session_id(request: Request, request_payload: dict) -> str | None:
    session_id = request.query_params.get("session_id")
    if session_id:
        return session_id
    payload_session_id = request_payload.get("session_id")
    if isinstance(payload_session_id, str):
        return payload_session_id
    return None


async def _summarize_request_payload(request: Request) -> dict:
    if request.method not in {"POST", "PUT", "PATCH"}:
        return {}
    content_type = request.headers.get("content-type", "").lower()
    if "application/json" not in content_type:
        return {}
    try:
        body = await request.body()
        if not body:
            return {}
        data = json.loads(body.decode("utf-8"))
        if isinstance(data, dict):
            return data
        return {"body_type": type(data).__name__}
    except Exception:
        return {"parse_error": True}


@app.middleware("http")
async def log_http_requests(request: Request, call_next):
    request_payload = await _summarize_request_payload(request)
    start = time.perf_counter()
    error_str = None
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    except Exception as exc:
        error_str = str(exc)
        raise
    finally:
        latency_ms = (time.perf_counter() - start) * 1000
        get_api_logger().log_call(
            APICallLog(
                module="http",
                operation=request.url.path,
                service="fastapi",
                model=None,
                latency_ms=latency_ms,
                cost_estimate_usd=0.0,
                request_payload={
                    "method": request.method,
                    "path": request.url.path,
                    "query": dict(request.query_params),
                    "payload": request_payload,
                },
                response_payload={"status_code": status_code},
                error=error_str,
                session_id=_extract_session_id(request, request_payload),
            )
        )


@app.get("/health")
async def health_check():
    return {"status": "ok"}

# Register API routers
app.include_router(auth_router)
app.include_router(admin_users_router)
app.include_router(pages_router)
app.include_router(openstax_router)
app.include_router(dialogue_router)
app.include_router(curriculum_router)
app.include_router(gathering_router)
app.include_router(pdf_router)

init_nicegui(app)
