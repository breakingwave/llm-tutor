from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.config import AuthSettings


class AuthService:
    def __init__(self, settings: AuthSettings):
        self.secret = settings.jwt_secret
        self.algorithm = settings.jwt_algorithm
        self.expire_hours = settings.jwt_expire_hours

    def hash_password(self, password: str) -> str:
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    def check_password(self, password: str, password_hash: str) -> bool:
        return bcrypt.checkpw(password.encode(), password_hash.encode())

    def create_token(self, user_id: str, role: str) -> str:
        payload = {
            "sub": user_id,
            "role": role,
            "exp": datetime.now(timezone.utc) + timedelta(hours=self.expire_hours),
        }
        return jwt.encode(payload, self.secret, algorithm=self.algorithm)

    def verify_token(self, token: str) -> dict:
        return jwt.decode(token, self.secret, algorithms=[self.algorithm])
