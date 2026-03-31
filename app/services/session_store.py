import json
from pathlib import Path

from app.models.user import UserProfile
from app.models.curriculum import Curriculum
from app.models.chat import ChatSession
from app.models.material import Material


class SessionData:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.user_profile: UserProfile = UserProfile(id=session_id)
        self.curricula: list[Curriculum] = []
        self.chat_sessions: list[ChatSession] = []
        self.materials: list[Material] = []
        self.gathering_tasks: dict[str, dict] = {}

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "user_profile": self.user_profile.model_dump(mode="json"),
            "curricula": [c.model_dump(mode="json") for c in self.curricula],
            "chat_sessions": [c.model_dump(mode="json") for c in self.chat_sessions],
            "materials": [m.model_dump(mode="json") for m in self.materials],
            "gathering_tasks": self.gathering_tasks,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SessionData":
        session = cls(data["session_id"])
        session.user_profile = UserProfile(**data.get("user_profile", {}))
        session.curricula = [Curriculum(**c) for c in data.get("curricula", [])]
        session.chat_sessions = [ChatSession(**c) for c in data.get("chat_sessions", [])]
        session.materials = [Material(**m) for m in data.get("materials", [])]
        session.gathering_tasks = data.get("gathering_tasks", {})
        return session


class SessionStore:
    def __init__(self, data_dir: str):
        self.sessions_dir = Path(data_dir) / "sessions"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, SessionData] = {}

    def _file_path(self, session_id: str) -> Path:
        return self.sessions_dir / f"{session_id}.json"

    def create(self, user_profile: UserProfile) -> SessionData:
        session = SessionData(user_profile.id)
        session.user_profile = user_profile
        self._cache[user_profile.id] = session
        self.save(user_profile.id)
        return session

    def get(self, session_id: str) -> SessionData | None:
        if session_id in self._cache:
            return self._cache[session_id]
        path = self._file_path(session_id)
        if not path.exists():
            return None
        with open(path) as f:
            data = json.load(f)
        session = SessionData.from_dict(data)
        self._cache[session_id] = session
        return session

    def save(self, session_id: str) -> None:
        session = self._cache.get(session_id)
        if not session:
            return
        path = self._file_path(session_id)
        with open(path, "w") as f:
            json.dump(session.to_dict(), f, indent=2, default=str)

    def list_sessions(self) -> list[str]:
        return [p.stem for p in self.sessions_dir.glob("*.json")]

    def delete(self, session_id: str) -> bool:
        self._cache.pop(session_id, None)
        path = self._file_path(session_id)
        if not path.exists():
            return False
        path.unlink()
        return True
