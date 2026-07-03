import csv
import io
from collections.abc import Iterable, Iterator, Sequence
from typing import Any

EXPORT_DISCLAIMER: tuple[str, ...] = (
    "Informational only — from public city data and modeled assumptions, not legal, tax, "
    "or financial advice.",
    "Owner contact use is subject to Fair Housing, TCPA/DNC (calls and texts), and "
    "CAN-SPAM (email). You are responsible for compliance.",
)


def _csv_line(values: Sequence[Any]) -> str:
    buffer = io.StringIO()
    csv.writer(buffer).writerow(["" if value is None else value for value in values])
    return buffer.getvalue()


def stream_csv(
    header: Sequence[str],
    rows: Iterable[Sequence[Any]],
    footer_lines: Sequence[str] = (),
) -> Iterator[str]:
    yield _csv_line(header)
    for row in rows:
        yield _csv_line(row)
    if footer_lines:
        yield _csv_line([])
        for line in footer_lines:
            yield _csv_line([line])
