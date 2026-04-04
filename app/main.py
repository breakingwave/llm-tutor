import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import EnvSettings, load_settings
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
