import json
from pathlib import Path

from pydantic import ValidationError

from lotscope.goldset.ask_schemas import AskCase, AskCoverage

DEFAULT_ASK_SET = Path("src/lotscope/goldset/data/ask_eval_v1.jsonl")


class AskSetError(ValueError):
    pass


def load_ask_cases(path: Path = DEFAULT_ASK_SET) -> list[AskCase]:
    if not path.exists():
        raise AskSetError(f"Ask evaluation set {path} does not exist.")
    cases: list[AskCase] = []
    seen: set[str] = set()
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        try:
            case = AskCase.model_validate(json.loads(stripped))
        except (json.JSONDecodeError, ValidationError) as error:
            raise AskSetError(f"{path}:{number} is not a valid case: {error}") from error
        if case.question_id in seen:
            raise AskSetError(f"{path}:{number} repeats question_id {case.question_id}.")
        seen.add(case.question_id)
        if case.coverage is AskCoverage.OUT_OF_CORPUS:
            if case.primary_cites:
                raise AskSetError(f"{path}:{number} expects a refusal but names primary cites.")
        elif not case.primary_cites:
            raise AskSetError(f"{path}:{number} names no primary cite to be judged against.")
        cases.append(case)
    return cases


def shared_cases(cases: list[AskCase]) -> list[AskCase]:
    return [case for case in cases if case.coverage is AskCoverage.SHARED]


UNREACHABLE_GROUND_TRUTH = (
    "These ground-truth cites resolve to no phillycode document with content, so no "
    "answer could cite them and every metric derived from them would be meaningless: {cites}"
)


def ground_truth_cites(cases: list[AskCase]) -> list[str]:
    return sorted({cite for case in cases for cite in case.primary_cites})
