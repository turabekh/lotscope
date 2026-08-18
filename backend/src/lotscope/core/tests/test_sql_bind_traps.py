import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[2]

_CAST_BIND = re.compile(r"CAST\s*\(\s*:\w+\s+AS\s+(date|timestamp)", re.IGNORECASE)

_ALLOWED: frozenset[str] = frozenset()


def _sql_bearing_files() -> list[Path]:
    return [path for path in SRC.rglob("*.py") if "tests" not in path.parts]


def test_no_query_casts_a_bound_parameter_to_a_date() -> None:
    offenders: list[str] = []
    for path in _sql_bearing_files():
        relative = str(path.relative_to(SRC))
        if relative in _ALLOWED:
            continue
        for number, line in enumerate(path.read_text().splitlines(), start=1):
            if _CAST_BIND.search(line):
                offenders.append(f"{relative}:{number} {line.strip()}")

    assert offenders == [], (
        "asyncpg binds parameters before the SQL cast is applied, so CAST(:param AS date) "
        "raises 'str object has no attribute toordinal' at runtime rather than converting. "
        "Pass a datetime.date object instead:\n  " + "\n  ".join(offenders)
    )


def test_the_guard_recognises_the_shape_it_exists_to_catch() -> None:
    assert _CAST_BIND.search("VALUES (:pn, CAST(:sd AS date), :sp)")
    assert _CAST_BIND.search("cast( :when as TIMESTAMP )")
    assert not _CAST_BIND.search("CAST(:market AS text)")
    assert not _CAST_BIND.search("CAST(:limit AS integer)")
    assert not _CAST_BIND.search("to_date(ts.snapshot_period, 'YYYYMM')")
