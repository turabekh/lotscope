import json
from pathlib import Path

from lotscope.goldset.schemas import GoldCase


class GoldSetError(ValueError):
    pass


def load_cases(path: Path) -> list[GoldCase]:
    if not path.exists():
        raise GoldSetError(f"Gold-set file {path} does not exist.")
    cases: list[GoldCase] = []
    seen: set[str] = set()
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        try:
            case = GoldCase.model_validate(json.loads(stripped))
        except Exception as error:
            raise GoldSetError(f"{path}:{number} is not a valid gold case: {error}") from error
        if case.parcel_number in seen:
            raise GoldSetError(f"{path}:{number} repeats parcel {case.parcel_number}.")
        seen.add(case.parcel_number)
        cases.append(case)
    return cases
