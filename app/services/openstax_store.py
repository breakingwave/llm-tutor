import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field
from uuid import uuid4

logger = logging.getLogger("llm_tutor.openstax_store")


class OpenStaxBook(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    title: str
    file_name: str
    chunk_count: int = 0
    uploaded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class OpenStaxStore:
    """JSON file store for shared OpenStax book metadata."""

    def __init__(self, data_dir: str):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._index_path = self.data_dir / "books.json"
        self._books: list[OpenStaxBook] = []
        self._load()

    def _load(self) -> None:
        if self._index_path.exists():
            data = json.loads(self._index_path.read_text())
            self._books = [OpenStaxBook(**b) for b in data]

    def save(self) -> None:
        data = [b.model_dump(mode="json") for b in self._books]
        self._index_path.write_text(json.dumps(data, indent=2, default=str))

    def list_books(self) -> list[OpenStaxBook]:
        return list(self._books)

    def get_book(self, book_id: str) -> OpenStaxBook | None:
        return next((b for b in self._books if b.id == book_id), None)

    def add_book(self, book: OpenStaxBook) -> None:
        self._books.append(book)
        self.save()

    def remove_book(self, book_id: str) -> OpenStaxBook | None:
        book = self.get_book(book_id)
        if book:
            self._books = [b for b in self._books if b.id != book_id]
            self.save()
        return book
