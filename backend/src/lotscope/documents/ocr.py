from typing import Protocol


class OcrEngine(Protocol):
    async def extract_text(self, data: bytes) -> str: ...


class PaddleOcrEngine:
    def __init__(self, *, lang: str = "en") -> None:
        self._lang = lang
        self._reader: object | None = None

    def _ensure_reader(self) -> object:
        if self._reader is None:
            from paddleocr import PaddleOCR

            self._reader = PaddleOCR(use_angle_cls=True, lang=self._lang, show_log=False)
        return self._reader

    async def extract_text(self, data: bytes) -> str:
        import asyncio

        return await asyncio.to_thread(self._run, data)

    def _run(self, data: bytes) -> str:
        import io

        import numpy as np
        from PIL import Image

        reader = self._ensure_reader()
        image = Image.open(io.BytesIO(data)).convert("RGB")
        result = reader.ocr(np.array(image), cls=True)  # type: ignore[attr-defined]
        lines: list[str] = []
        for page in result or []:
            for entry in page or []:
                text = entry[1][0] if len(entry) > 1 and entry[1] else None
                if text:
                    lines.append(str(text))
        return "\n".join(lines)
