import logging
from pathlib import Path

from app.config import Settings
from app.services.chunking import OpenStaxChunkingStrategy
from app.services.openstax_store import OpenStaxBook, OpenStaxStore
from app.services.pdf_service import PDFService
from app.services.vector_store import VectorStoreService

logger = logging.getLogger("llm_tutor.openstax.service")


class OpenStaxService:
    def __init__(
        self,
        settings: Settings,
        pdf_service: PDFService,
        vector_store: VectorStoreService,
        openstax_store: OpenStaxStore,
    ):
        self.settings = settings
        self.pdf_service = pdf_service
        self.vector_store = vector_store
        self.openstax_store = openstax_store
        self.chunker = OpenStaxChunkingStrategy()

    def list_books(self) -> list[OpenStaxBook]:
        return self.openstax_store.list_books()

    async def upload_book(self, file_name: str, content: bytes) -> OpenStaxBook:
        if not file_name.lower().endswith(".pdf"):
            raise ValueError("Only PDF files are supported")

        upload_dir = Path(self.settings.openstax.upload_dir)
        file_path = self.pdf_service.save_bytes_to_dir(
            file_name=file_name,
            content=content,
            target_dir=upload_dir,
            max_file_size_mb=self.settings.pdf.max_file_size_mb,
        )

        parsed = self.pdf_service.parse_pdf_document(file_path)
        if not parsed.text.strip():
            file_path.unlink(missing_ok=True)
            raise ValueError("PDF contains no extractable text")

        title = Path(file_name).stem.replace("_", " ").replace("-", " ").title()
        book = OpenStaxBook(title=title, file_name=file_name)

        chunks = self.chunker.chunk(
            parsed.text,
            book.id,
            file_name=file_name,
            toc_entries=parsed.toc_entries or None,
            page_texts=parsed.page_texts,
            chunk_size=self.settings.openstax.chunk_size,
            chunk_overlap=self.settings.openstax.chunk_overlap,
        )

        indexed = await self.vector_store.index_chunks(
            chunks,
            collection_name=self.settings.openstax.collection_name,
        )

        book.chunk_count = indexed
        self.openstax_store.add_book(book)
        logger.info("Uploaded OpenStax book '%s' with %d chunks", book.title, indexed)
        return book

    async def delete_book(self, book_id: str) -> OpenStaxBook:
        book = self.openstax_store.remove_book(book_id)
        if not book:
            raise ValueError("Book not found")

        await self.vector_store.delete_by_material_id(
            book_id,
            collection_name=self.settings.openstax.collection_name,
        )

        file_path = Path(self.settings.openstax.upload_dir) / book.file_name
        file_path.unlink(missing_ok=True)
        return book

    async def reindex_book(self, book_id: str) -> OpenStaxBook:
        book = self.openstax_store.get_book(book_id)
        if not book:
            raise ValueError("Book not found")

        file_path = Path(self.settings.openstax.upload_dir) / book.file_name
        if not file_path.exists():
            raise ValueError("Book PDF file not found on disk")

        await self.vector_store.delete_by_material_id(
            book_id,
            collection_name=self.settings.openstax.collection_name,
        )

        parsed = self.pdf_service.parse_pdf_document(file_path)
        chunks = self.chunker.chunk(
            parsed.text,
            book.id,
            file_name=book.file_name,
            toc_entries=parsed.toc_entries or None,
            page_texts=parsed.page_texts,
            chunk_size=self.settings.openstax.chunk_size,
            chunk_overlap=self.settings.openstax.chunk_overlap,
        )
        indexed = await self.vector_store.index_chunks(
            chunks,
            collection_name=self.settings.openstax.collection_name,
        )

        book.chunk_count = indexed
        self.openstax_store.save()
        logger.info("Re-indexed OpenStax book '%s' with %d chunks", book.title, indexed)
        return book
