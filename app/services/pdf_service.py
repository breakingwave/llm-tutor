import logging
import time
from dataclasses import dataclass
from pathlib import Path

import pymupdf
from fastapi import UploadFile

from app.config import PDFSettings
from app.models.api_log import APICallLog
from app.models.material import MaterialChunk
from app.services.api_logger import APILogger
from app.services.chunking import AutoChunkingStrategy, ChunkingStrategy

logger = logging.getLogger("llm_tutor.pdf")


@dataclass(slots=True)
class ParsedPDF:
    text: str
    toc_entries: list[dict]
    page_texts: list[str]


class PDFService:
    def __init__(
        self,
        settings: PDFSettings,
        api_logger: APILogger,
        chunking_strategy: ChunkingStrategy | None = None,
    ):
        self.settings = settings
        self.api_logger = api_logger
        self.chunker = chunking_strategy or AutoChunkingStrategy()

    async def save_upload(self, file: UploadFile, session_id: str) -> Path:
        """Save uploaded PDF to data/uploads/{session_id}/."""
        content = await file.read()
        return self.save_bytes(file.filename or "upload.pdf", content, session_id)

    def save_bytes(self, file_name: str, content: bytes, session_id: str) -> Path:
        upload_dir = Path(self.settings.upload_dir) / session_id
        return self.save_bytes_to_dir(
            file_name=file_name,
            content=content,
            target_dir=upload_dir,
            max_file_size_mb=self.settings.max_file_size_mb,
        )

    def save_bytes_to_dir(
        self,
        file_name: str,
        content: bytes,
        target_dir: Path,
        *,
        max_file_size_mb: int | None = None,
    ) -> Path:
        target_dir.mkdir(parents=True, exist_ok=True)
        file_path = target_dir / file_name
        # Check file size
        max_mb = max_file_size_mb if max_file_size_mb is not None else self.settings.max_file_size_mb
        max_bytes = max_mb * 1024 * 1024
        if len(content) > max_bytes:
            raise ValueError(
                f"File too large: {len(content) / 1024 / 1024:.1f}MB "
                f"(max {max_mb}MB)"
            )

        file_path.write_bytes(content)
        logger.info("Saved PDF: %s (%d bytes)", file_path, len(content))
        return file_path

    def parse_pdf(self, file_path: Path) -> tuple[str, list[dict]]:
        parsed = self.parse_pdf_document(file_path)
        return parsed.text, parsed.toc_entries

    def parse_pdf_document(self, file_path: Path) -> ParsedPDF:
        """Extract full text, ToC, and page-aligned text from a PDF via PyMuPDF."""
        start = time.perf_counter()
        error_str = None
        text = ""
        toc_entries: list[dict] = []
        page_texts: list[str] = []

        try:
            doc = pymupdf.open(str(file_path))

            # Extract ToC if available
            toc = doc.get_toc()  # [[level, title, page_num], ...]
            for entry in toc:
                toc_entries.append({
                    "level": entry[0],
                    "title": entry[1],
                    "page_num": entry[2],
                })

            # Extract text page by page
            text_pages: list[str] = []
            for page in doc:
                page_text = page.get_text()
                page_texts.append(page_text)
                if page_text.strip():
                    text_pages.append(page_text)
            text = "\n\n".join(text_pages)
            doc.close()
        except Exception as e:
            error_str = str(e)
            logger.error("PDF parsing failed for %s: %s", file_path, e)
            raise
        finally:
            latency = (time.perf_counter() - start) * 1000
            self.api_logger.log_call(APICallLog(
                module="gathering",
                operation="pdf_parse",
                service="pymupdf",
                latency_ms=latency,
                request_payload={"file": str(file_path)},
                response_payload={
                    "text_length": len(text),
                    "toc_entries": len(toc_entries),
                },
                error=error_str,
            ))

        return ParsedPDF(text=text, toc_entries=toc_entries, page_texts=page_texts)

    def chunk_pdf(
        self,
        text: str,
        toc_entries: list[dict],
        file_name: str,
        material_id: str,
        page_texts: list[str] | None = None,
    ) -> list[MaterialChunk]:
        """Chunk PDF text using the configured chunking strategy."""
        return self.chunker.chunk(
            text,
            material_id,
            file_name=file_name,
            toc_entries=toc_entries if toc_entries else None,
            page_texts=page_texts,
            chunk_size=self.settings.chunk_size,
            chunk_overlap=self.settings.chunk_overlap,
        )
