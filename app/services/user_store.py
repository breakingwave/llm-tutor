import json
from pathlib import Path

from app.models.account import UserAccount


class UserStore:
    def __init__(self, data_dir: str):
        self._path = Path(data_dir) / "users.json"
        self._users: dict[str, UserAccount] = {}
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            with open(self._path) as f:
                data = json.load(f)
            for entry in data:
                user = UserAccount(**entry)
                self._users[user.id] = user

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w") as f:
            json.dump(
                [u.model_dump(mode="json") for u in self._users.values()],
                f,
                indent=2,
                default=str,
            )

    def list_users(self) -> list[UserAccount]:
        return list(self._users.values())

    def create_user(self, email: str, password_hash: str, role: str = "user") -> UserAccount:
        user = UserAccount(email=email, password_hash=password_hash, role=role)
        self._users[user.id] = user
        self.save()
        return user

    def get_by_email(self, email: str) -> UserAccount | None:
        for user in self._users.values():
            if user.email == email:
                return user
        return None

    def get_by_id(self, user_id: str) -> UserAccount | None:
        return self._users.get(user_id)

    def delete_user(self, user_id: str) -> bool:
        if user_id not in self._users:
            return False
        del self._users[user_id]
        self.save()
        return True

    def count_admins(self) -> int:
        return sum(1 for user in self._users.values() if user.role == "admin")

    def add_session(self, user_id: str, session_id: str) -> None:
        user = self._users.get(user_id)
        if user and session_id not in user.session_ids:
            user.session_ids.append(session_id)
            self.save()

    def update_upload_bytes(self, user_id: str, delta_bytes: int) -> None:
        user = self._users.get(user_id)
        if user:
            user.total_upload_bytes += delta_bytes
            self.save()
