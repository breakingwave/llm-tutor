import logging
import time
from pathlib import Path

import pymupdf
from fastapi import UploadFile

from app.config import PDFSettings
from app.models.api_log import APICallLog
from app.models.material import MaterialChunk
from app.services.api_logger import APILogger
from app.services.chunking import AutoChunkingStrategy, ChunkingStrategy

logger = logging.getLogger("llm_tutor.pdf")


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
        upload_dir = Path(self.settings.upload_dir) / session_id
        upload_dir.mkdir(parents=True, exist_ok=True)

        file_path = upload_dir / file.filename
        content = await file.read()

        # Check file size
        max_bytes = self.settings.max_file_size_mb * 1024 * 1024
        if len(content) > max_bytes:
            raise ValueError(
                f"File too large: {len(content) / 1024 / 1024:.1f}MB "
                f"(max {self.settings.max_file_size_mb}MB)"
            )

        file_path.write_bytes(content)
        logger.info("Saved PDF: %s (%d bytes)", file_path, len(content))
        return file_path

    def parse_pdf(self, file_path: Path) -> tuple[str, list[dict]]:
        """Extract full text and ToC from a PDF via PyMuPDF.

        Returns (full_text, toc_entries) where toc_entries is
        [{level, title, page_num}, ...].
        """
        start = time.perf_counter()
        error_str = None
        text = ""
        toc_entries: list[dict] = []

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
            pages = []
            for page in doc:
                page_text = page.get_text()
                if page_text.strip():
                    pages.append(page_text)
            text = "\n\n".join(pages)
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

        return text, toc_entries

    def chunk_pdf(
        self,
        text: str,
        toc_entries: list[dict],
        file_name: str,
        material_id: str,
    ) -> list[MaterialChunk]:
        """Chunk PDF text using the configured chunking strategy."""
        return self.chunker.chunk(
            text,
            material_id,
            file_name=file_name,
            toc_entries=toc_entries if toc_entries else None,
            chunk_size=self.settings.chunk_size,
            chunk_overlap=self.settings.chunk_overlap,
        )
