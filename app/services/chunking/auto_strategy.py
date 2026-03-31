from app.models.material import MaterialChunk
from app.services.chunking.base import ChunkingStrategy
from app.services.chunking.paragraph_strategy import ParagraphChunkingStrategy
from app.services.chunking.toc_strategy import ToCChunkingStrategy


class AutoChunkingStrategy(ChunkingStrategy):
    """Automatically picks ToC strategy if entries exist, else paragraph."""

    def __init__(self):
        self._toc = ToCChunkingStrategy()
        self._paragraph = ParagraphChunkingStrategy()

    def chunk(
        self,
        text: str,
        material_id: str,
        *,
        file_name: str = "",
        toc_entries: list[dict] | None = None,
        chunk_size: int = 1500,
        chunk_overlap: int = 150,
    ) -> list[MaterialChunk]:
        if toc_entries:
            return self._toc.chunk(
                text, material_id,
                file_name=file_name,
                toc_entries=toc_entries,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )
        return self._paragraph.chunk(
            text, material_id,
            file_name=file_name,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
