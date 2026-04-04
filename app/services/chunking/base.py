from abc import ABC, abstractmethod

from app.models.material import MaterialChunk


class ChunkingStrategy(ABC):
    """Base class for text chunking strategies."""

    @abstractmethod
    def chunk(
        self,
        text: str,
        material_id: str,
        *,
        file_name: str = "",
        toc_entries: list[dict] | None = None,
        page_texts: list[str] | None = None,
        chunk_size: int = 1500,
        chunk_overlap: int = 150,
    ) -> list[MaterialChunk]:
        """Split text into chunks.

        Args:
            text: Full text to chunk.
            material_id: ID of the parent material.
            file_name: Source file name (for metadata).
            toc_entries: Table of contents entries [{level, title, page_num}].
            page_texts: Extracted page text in original page order.
            chunk_size: Target words per chunk.
            chunk_overlap: Overlap words between chunks.

        Returns:
            Ordered list of MaterialChunk objects.
        """
        ...
