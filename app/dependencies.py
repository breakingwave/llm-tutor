from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Header, HTTPException

from app.config import (
    EnvSettings,
    load_models_config,
    load_prompts_config,
    load_settings,
    ModelsConfig,
    PromptsConfig,
    Settings,
)
from app.models.account import UserAccount
from app.services.api_logger import APILogger
from app.services.auth import AuthService
from app.services.llm import LLMService
from app.services.openstax_service import OpenStaxService
from app.services.openstax_store import OpenStaxStore
from app.services.pdf_service import PDFService
from app.services.session_store import SessionStore
from app.services.user_store import UserStore
from app.services.vector_store import VectorStoreService


@lru_cache
def get_env_settings() -> EnvSettings:
    return EnvSettings()


@lru_cache
def get_settings() -> Settings:
    return load_settings()


@lru_cache
def get_models_config() -> ModelsConfig:
    return load_models_config()


@lru_cache
def get_prompts_config() -> PromptsConfig:
    return load_prompts_config()


@lru_cache
def get_api_logger() -> APILogger:
    settings = get_settings()
    return APILogger(settings.logging)


@lru_cache
def get_llm_service() -> LLMService:
    env = get_env_settings()
    return LLMService(
        models_config=get_models_config(),
        prompts_config=get_prompts_config(),
        api_logger=get_api_logger(),
        llm_base_url=env.llm_base_url,
        llm_api_key=env.llm_api_key,
    )


@lru_cache
def get_session_store() -> SessionStore:
    settings = get_settings()
    return SessionStore(settings.app.data_dir)


@lru_cache
def get_pdf_service() -> PDFService:
    from app.services.chunking import AutoChunkingStrategy
    settings = get_settings()
    return PDFService(settings.pdf, get_api_logger(), AutoChunkingStrategy())


@lru_cache
def get_vector_store_service() -> VectorStoreService:
    settings = get_settings()
    models = get_models_config()
    env_key = get_env_settings().openai_api_key
    return VectorStoreService(
        qdrant_settings=settings.qdrant,
        embedding_model=models.defaults.get("embedding_model", "openai/text-embedding-3-small"),
        api_logger=get_api_logger(),
        openai_api_key=env_key.strip() if env_key else None,
    )


@lru_cache
def get_openstax_store() -> OpenStaxStore:
    settings = get_settings()
    return OpenStaxStore(settings.openstax.upload_dir)


@lru_cache
def get_openstax_service() -> OpenStaxService:
    return OpenStaxService(
        settings=get_settings(),
        pdf_service=get_pdf_service(),
        vector_store=get_vector_store_service(),
        openstax_store=get_openstax_store(),
    )


@lru_cache
def get_user_store() -> UserStore:
    settings = get_settings()
    return UserStore(settings.app.data_dir)


@lru_cache
def get_auth_service() -> AuthService:
    settings = get_settings()
    env = get_env_settings()
    auth_settings = settings.auth
    if env.jwt_secret:
        auth_settings.jwt_secret = env.jwt_secret
    return AuthService(auth_settings)


async def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    auth: AuthService = Depends(get_auth_service),
    store: UserStore = Depends(get_user_store),
) -> UserAccount:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")
    token = authorization.removeprefix("Bearer ")
    try:
        payload = auth.verify_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = store.get_by_id(payload["sub"])
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


async def require_admin(
    user: UserAccount = Depends(get_current_user),
) -> UserAccount:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
