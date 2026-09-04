from lotscope.ai.chunking import chunk_text


def test_chunk_text_handles_short_and_empty() -> None:
    assert chunk_text("hello") == ["hello"]
    assert chunk_text("   ") == []


def test_chunk_text_splits_long_text() -> None:
    chunks = chunk_text("x" * 4000, max_chars=1500, overlap=150)
    assert len(chunks) >= 3
    assert all(len(chunk) <= 1500 for chunk in chunks)
