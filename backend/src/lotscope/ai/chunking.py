_MAX_CHARS = 1500
_OVERLAP = 150


def chunk_text(value: str, *, max_chars: int = _MAX_CHARS, overlap: int = _OVERLAP) -> list[str]:
    cleaned = value.strip()
    if not cleaned:
        return []
    if len(cleaned) <= max_chars:
        return [cleaned]
    chunks: list[str] = []
    start = 0
    while start < len(cleaned):
        end = start + max_chars
        chunk = cleaned[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(cleaned):
            break
        start = end - overlap
    return chunks
