import shutil
from pathlib import Path

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.config import Settings
from app.services.api_logger import APILogger
from app.models.account import UserAccount
from app.services.auth import AuthService
from app.services.session_store import SessionStore
from app.services.user_store import UserStore
from app.services.vector_store import VectorStoreService
from app.dependencies import (
    get_auth_service,
    get_api_logger,
    get_current_user,
    get_session_store,
    get_settings,
    get_user_store,
    get_vector_store_service,
    require_admin,
)

router = APIRouter(prefix="/api/admin/users", tags=["admin-users"])


class CreateUserRequest(BaseModel):
    email: str
    password: str
    role: str = "user"


@router.get("/logs/costs")
async def get_cost_breakdown(
    _: UserAccount = Depends(require_admin),
    api_logger: APILogger = Depends(get_api_logger),
    since: str | None = Query(default=None),
    until: str | None = Query(default=None),
):
    try:
        since_dt = datetime.fromisoformat(since) if since else None
        until_dt = datetime.fromisoformat(until) if until else None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid datetime filter: {exc}")
    by_module_service = api_logger.aggregate_costs(
        since=since_dt,
        until=until_dt,
        group_by=("module", "service"),
    )
    by_session = api_logger.aggregate_costs(
        since=since_dt,
        until=until_dt,
        group_by=("session_id",),
    )
    return {
        "since": since_dt.isoformat() if since_dt else None,
        "until": until_dt.isoformat() if until_dt else None,
        "by_module_service": by_module_service,
        "by_session": by_session,
    }


@router.get("")
async def list_users(
    _: UserAccount = Depends(require_admin),
    store: UserStore = Depends(get_user_store),
):
    users = store.list_users()
    return {
        "users": [
            {
                "id": user.id,
                "email": user.email,
                "role": user.role,
                "total_upload_bytes": user.total_upload_bytes,
                "session_ids": user.session_ids,
                "created_at": user.created_at.isoformat(),
            }
            for user in users
        ]
    }


@router.post("")
async def create_user(
    payload: CreateUserRequest,
    _: UserAccount = Depends(require_admin),
    auth: AuthService = Depends(get_auth_service),
    store: UserStore = Depends(get_user_store),
):
    email = payload.email.strip().lower()
    if "@" not in email or email.startswith("@") or email.endswith("@"):
        raise HTTPException(status_code=400, detail="Invalid email format")

    role = payload.role.strip().lower()
    if role not in {"user", "admin"}:
        raise HTTPException(status_code=400, detail="Role must be 'user' or 'admin'")
    if store.get_by_email(email):
        raise HTTPException(status_code=409, detail="Email already registered")
    if len(payload.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    password_hash = auth.hash_password(payload.password)
    user = store.create_user(email, password_hash, role=role)
    return {"id": user.id, "email": user.email, "role": user.role}


def _safe_unlink(path_str: str, uploads_root: Path) -> None:
    file_path = Path(path_str).resolve()
    uploads_root_resolved = uploads_root.resolve()
    if uploads_root_resolved in file_path.parents and file_path.exists() and file_path.is_file():
        file_path.unlink()


@router.delete("/{user_id}")
async def delete_user(
    user_id: str,
    admin_user: UserAccount = Depends(require_admin),
    store: UserStore = Depends(get_user_store),
    session_store: SessionStore = Depends(get_session_store),
    vector_store: VectorStoreService = Depends(get_vector_store_service),
    settings: Settings = Depends(get_settings),
):
    target_user = store.get_by_id(user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    if admin_user.id == target_user.id:
        raise HTTPException(status_code=400, detail="Admin cannot delete their own account")
    if target_user.role == "admin" and store.count_admins() <= 1:
        raise HTTPException(status_code=400, detail="Cannot delete the last admin account")

    uploads_root = Path(settings.pdf.upload_dir)
    deleted_sessions: list[str] = []
    deleted_materials = 0

    for session_id in list(target_user.session_ids):
        session_data = session_store.get(session_id)
        if session_data:
            for material in session_data.materials:
                await vector_store.delete_by_material_id(material.id, session_id=session_id)
                file_path = material.metadata.get("file_path")
                if isinstance(file_path, str) and file_path:
                    _safe_unlink(file_path, uploads_root)
                deleted_materials += 1
        session_store.delete(session_id)

        session_upload_dir = uploads_root / session_id
        if session_upload_dir.exists() and session_upload_dir.is_dir():
            shutil.rmtree(session_upload_dir, ignore_errors=True)
        deleted_sessions.append(session_id)

    store.delete_user(target_user.id)
    return {
        "status": "deleted",
        "user_id": target_user.id,
        "deleted_sessions": deleted_sessions,
        "deleted_material_count": deleted_materials,
    }
