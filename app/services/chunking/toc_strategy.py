from app.models.material import MaterialChunk
from app.services.chunking.base import ChunkingStrategy
from app.services.chunking.paragraph_strategy import ParagraphChunkingStrategy


class ToCChunkingStrategy(ChunkingStrategy):
    """Chunk text using Table of Contents section boundaries.

    Falls back to paragraph chunking if no sections can be found in text.
    """

    def __init__(self):
        self._paragraph_fallback = ParagraphChunkingStrategy()

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
        if not toc_entries:
            return self._paragraph_fallback.chunk(
                text, material_id,
                file_name=file_name,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )

        # Build section boundaries by finding titles in text
        sections: list[dict] = []
        for entry in toc_entries:
            title = entry["title"].strip()
            if not title:
                continue
            pos = text.find(title)
            if pos >= 0:
                sections.append({
                    "title": title,
                    "level": entry["level"],
                    "start": pos,
                })

        if not sections:
            return self._paragraph_fallback.chunk(
                text, material_id,
                file_name=file_name,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )

        sections.sort(key=lambda s: s["start"])

        chunks: list[MaterialChunk] = []
        chunk_idx = 0
        current_chapter = ""

        for i, sec in enumerate(sections):
            end = sections[i + 1]["start"] if i + 1 < len(sections) else len(text)
            section_text = text[sec["start"]:end].strip()

            if sec["level"] <= 1:
                current_chapter = sec["title"]

            if not section_text:
                continue

            word_count = len(section_text.split())

            if word_count <= chunk_size * 1.5:
                chunks.append(MaterialChunk(
                    material_id=material_id,
                    content=section_text,
                    chunk_index=chunk_idx,
                    chapter=current_chapter,
                    section=sec["title"],
                ))
                chunk_idx += 1
            else:
                sub_texts = ParagraphChunkingStrategy._split_at_paragraphs(
                    section_text, chunk_size
                )
                for sub_text in sub_texts:
                    chunks.append(MaterialChunk(
                        material_id=material_id,
                        content=sub_text,
                        chunk_index=chunk_idx,
                        chapter=current_chapter,
                        section=sec["title"],
                    ))
                    chunk_idx += 1

        return chunks
