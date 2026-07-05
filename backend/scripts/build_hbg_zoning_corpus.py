import json
import re
import sys
from pathlib import Path

from pypdf import PdfReader

_PART3_START = "Part 3 (7-300)"
_PART3_END = "Part 5 (7-500)"
_CHAPTER = re.compile(r"\nChapter\s+(7-3\d\d)\s*\n\s*([A-Z][A-Z0-9 &,'./-]{3,70})\n")
_NOISE = re.compile(
    r"^(City of Harrisburg, PA|Downloaded from https?://\S+|HARRISBURG CODE.*|"
    r"§\s*7-3\d\d(?:\.\d+)?\s*(?:§\s*7-3\d\d(?:\.\d+)?)?|\d{1,4})\s*$"
)


def _clean(block: str) -> str:
    lines = [line.rstrip() for line in block.splitlines()]
    kept = [line for line in lines if line.strip() and not _NOISE.match(line.strip())]
    collapsed = re.sub(r"[ \t]+", " ", "\n".join(kept))
    return re.sub(r"\n{3,}", "\n\n", collapsed).strip()


def build(pdf_path: Path, out_path: Path) -> int:
    reader = PdfReader(str(pdf_path))
    full = "\n".join((page.extract_text() or "") for page in reader.pages)
    start = full.find(_PART3_START)
    end = full.find(_PART3_END, start + 100)
    part3 = full[start : end if end > 0 else len(full)]

    matches = list(_CHAPTER.finditer(part3))
    records: list[dict[str, str]] = []
    for pos, match in enumerate(matches):
        section = match.group(1)
        title = match.group(2).strip().title()
        body_start = match.end()
        body_end = matches[pos + 1].start() if pos + 1 < len(matches) else len(part3)
        text = _clean(part3[body_start:body_end])
        if len(text) >= 200:
            records.append({"section": section, "title": title, "text": text})

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return len(records)


if __name__ == "__main__":
    pdf = Path(sys.argv[1])
    out = Path(sys.argv[2])
    count = build(pdf, out)
    print(f"wrote {count} sections to {out}")
