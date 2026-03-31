"""JSON extraction and parsing utilities for LLM responses."""
import re


def extract_json(text: str) -> str:
    """Extract JSON from text, handling markdown code blocks.
    Returns the text as-is if no code block is found.
    """
    if not text or not isinstance(text, str):
        return text or ""
    text = text.strip()
    m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if m:
        return m.group(1).strip()
    return text
