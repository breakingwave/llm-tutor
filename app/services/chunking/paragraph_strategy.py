from app.models.material import MaterialChunk
from app.services.chunking.base import ChunkingStrategy


class ParagraphChunkingStrategy(ChunkingStrategy):
    """Chunk text at paragraph boundaries with configurable size and overlap."""

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
        sub_texts = self._split_at_paragraphs(text, chunk_size, chunk_overlap)
        chunks = []
        for idx, sub_text in enumerate(sub_texts):
            chunks.append(MaterialChunk(
                material_id=material_id,
                content=sub_text,
                chunk_index=idx,
                chapter="",
                section="",
            ))
        return chunks

    @staticmethod
    def _split_at_paragraphs(
        text: str, target_words: int, overlap: int = 0,
    ) -> list[str]:
        """Split text into chunks at paragraph boundaries."""
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        if not paragraphs:
            paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
        if not paragraphs:
            return [text] if text.strip() else []

        result: list[str] = []
        current: list[str] = []
        current_words = 0

        for para in paragraphs:
            para_words = len(para.split())
            if current_words + para_words > target_words and current:
                result.append("\n\n".join(current))
                if overlap > 0 and para_words < target_words:
                    current = [current[-1]] if current else []
                    current_words = len(current[0].split()) if current else 0
                else:
                    current = []
                    current_words = 0
            current.append(para)
            current_words += para_words

        if current:
            result.append("\n\n".join(current))

        return result
