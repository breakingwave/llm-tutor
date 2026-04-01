from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr

from app.models.account import UserAccount
from app.services.auth import AuthService
from app.services.user_store import UserStore
from app.config import Settings
from app.dependencies import get_auth_service, get_user_store, get_current_user, get_settings

router = APIRouter(prefix="/api/auth", tags=["auth"])


class AuthForm(BaseModel):
    email: str
    password: str


class BackgroundUpdate(BaseModel):
    background: str


@router.post("/register")
async def register(
    form: AuthForm,
    auth: AuthService = Depends(get_auth_service),
    store: UserStore = Depends(get_user_store),
    settings: Settings = Depends(get_settings),
):
    if not settings.auth.allow_self_registration:
        raise HTTPException(status_code=403, detail="Self-registration is disabled")

    if store.get_by_email(form.email):
        raise HTTPException(status_code=409, detail="Email already registered")

    password_hash = auth.hash_password(form.password)
    user = store.create_user(form.email, password_hash)
    token = auth.create_token(user.id, user.role)

    return {
        "token": token,
        "user": {"id": user.id, "email": user.email, "role": user.role},
    }


@router.post("/login")
async def login(
    form: AuthForm,
    auth: AuthService = Depends(get_auth_service),
    store: UserStore = Depends(get_user_store),
):
    user = store.get_by_email(form.email)
    if not user or not auth.check_password(form.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = auth.create_token(user.id, user.role)
    return {
        "token": token,
        "user": {"id": user.id, "email": user.email, "role": user.role},
    }


@router.get("/me")
async def get_me(user: UserAccount = Depends(get_current_user)):
    return {
        "id": user.id,
        "email": user.email,
        "role": user.role,
        "background": user.background,
        "total_upload_bytes": user.total_upload_bytes,
        "session_ids": user.session_ids,
    }


@router.put("/me/background")
async def update_my_background(
    update: BackgroundUpdate,
    user: UserAccount = Depends(get_current_user),
    store: UserStore = Depends(get_user_store),
):
    store.update_background(user.id, update.background)
    return {"status": "updated"}
