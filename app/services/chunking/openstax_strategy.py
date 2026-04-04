import re

from app.models.material import MaterialChunk
from app.services.chunking.base import ChunkingStrategy
from app.services.chunking.paragraph_strategy import ParagraphChunkingStrategy
from app.services.chunking.toc_strategy import ToCChunkingStrategy

_IGNORED_SECTION_TITLES = {
    "contents",
    "preface",
    "key terms",
    "key equations",
    "chapter summary",
    "summary",
    "visual connection questions",
    "review questions",
    "critical thinking questions",
    "exercises",
    "references",
    "index",
}


class OpenStaxChunkingStrategy(ChunkingStrategy):
    """Chunk OpenStax books by chapter/sub-chapter ToC boundaries."""

    def __init__(self):
        self._paragraph = ParagraphChunkingStrategy()
        self._fallback = ToCChunkingStrategy()

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
        if not toc_entries or not page_texts:
            return self._fallback.chunk(
                text,
                material_id,
                file_name=file_name,
                toc_entries=toc_entries,
                page_texts=page_texts,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )

        sections = self._build_sections(toc_entries)
        if not sections:
            return self._fallback.chunk(
                text,
                material_id,
                file_name=file_name,
                toc_entries=toc_entries,
                page_texts=page_texts,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )

        chunks: list[MaterialChunk] = []
        chunk_index = 0

        for idx, section in enumerate(sections):
            next_section = sections[idx + 1] if idx + 1 < len(sections) else None
            section_text = self._extract_section_text(section, next_section, page_texts)
            section_text = self._clean_section_text(section_text)
            if not section_text:
                continue
            if section["title"].lower() == "introduction" and len(section_text.split()) < 80:
                continue

            words = len(section_text.split())
            if words <= chunk_size * 1.75:
                chunks.append(
                    MaterialChunk(
                        material_id=material_id,
                        content=section_text,
                        chunk_index=chunk_index,
                        chapter=section["chapter"],
                        section=section["title"],
                    )
                )
                chunk_index += 1
                continue

            for part in self._paragraph._split_at_paragraphs(section_text, chunk_size, chunk_overlap):
                chunks.append(
                    MaterialChunk(
                        material_id=material_id,
                        content=part,
                        chunk_index=chunk_index,
                        chapter=section["chapter"],
                        section=section["title"],
                    )
                )
                chunk_index += 1

        return chunks or self._paragraph.chunk(
            text,
            material_id,
            file_name=file_name,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

    def _build_sections(self, toc_entries: list[dict]) -> list[dict]:
        entries = sorted(
            (
                {
                    "level": int(entry.get("level", 0)),
                    "title": str(entry.get("title", "")).strip(),
                    "page_num": int(entry.get("page_num", 0)),
                }
                for entry in toc_entries
                if entry.get("title") and entry.get("page_num")
            ),
            key=lambda entry: (entry["page_num"], entry["level"]),
        )

        sections: list[dict] = []
        current_chapter = ""

        for entry in entries:
            title = entry["title"]
            if not title:
                continue

            if entry["level"] == 1 and title.lower().startswith("chapter"):
                current_chapter = title
                continue

            if entry["level"] != 2 or not current_chapter:
                continue

            normalized = title.lower()
            if normalized in _IGNORED_SECTION_TITLES:
                continue
            if normalized.startswith("appendix"):
                continue
            if re.match(r"chapter\s+\d+", normalized):
                continue
            if normalized != "introduction" and not re.match(r"\d+(\.\d+)?", normalized):
                continue

            sections.append(
                {
                    "title": title,
                    "chapter": current_chapter,
                    "page_num": entry["page_num"],
                }
            )

        return sections

    def _extract_section_text(
        self,
        section: dict,
        next_section: dict | None,
        page_texts: list[str],
    ) -> str:
        start_page_idx = max(0, section["page_num"] - 1)
        if start_page_idx >= len(page_texts):
            return ""

        end_page_idx = len(page_texts) - 1
        same_page_boundary_title = None
        if next_section:
            next_page_idx = max(0, next_section["page_num"] - 1)
            if next_page_idx == start_page_idx:
                same_page_boundary_title = next_section["title"]
                end_page_idx = start_page_idx
            else:
                end_page_idx = min(len(page_texts) - 1, next_page_idx - 1)

        pages = page_texts[start_page_idx : end_page_idx + 1]
        if not pages:
            return ""

        pages[0] = self._trim_before_heading(pages[0], section["title"])
        if same_page_boundary_title:
            pages[0] = self._trim_before_heading(pages[0], section["title"])
            pages[-1] = self._trim_after_heading(pages[-1], same_page_boundary_title)

        return "\n\n".join(page.strip() for page in pages if page and page.strip())

    def _clean_section_text(self, text: str) -> str:
        cleaned = re.sub(r"\n{3,}", "\n\n", text).strip()
        return cleaned

    def _trim_before_heading(self, text: str, title: str) -> str:
        matches = self._find_heading_matches(text, title)
        if not matches:
            return text
        return text[matches[-1].start() :].strip()

    def _trim_after_heading(self, text: str, title: str) -> str:
        matches = self._find_heading_matches(text, title)
        if not matches:
            return text
        return text[: matches[0].start()].strip()

    def _find_heading_matches(self, text: str, title: str) -> list[re.Match[str]]:
        compact_title = " ".join(title.split())
        if not compact_title:
            return []
        pattern = re.escape(compact_title)
        pattern = pattern.replace(r"\ ", r"\s+")
        return list(re.finditer(pattern, text, flags=re.IGNORECASE))
