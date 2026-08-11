import re

from pydantic import BaseModel

from lotscope.goldset.ask_schemas import AskCase

_CONTEXT_HEADER = "CONTEXT - SOURCE DOCUMENTS:"
_DOCUMENT_LINE = re.compile(r"^\[(\S+)\s+(.+?)(?:\s+·\s+referenced by\s+.+?)?\]\s")
_REFUSAL_MARKERS = (
    "not in the provided context",
    "no information",
    "cannot answer",
    "does not appear",
    "not covered",
    "outside",
    "no source",
    "unable to",
)


class CaseScore(BaseModel):
    question_id: str
    arm: str
    primary_hit: bool
    citation_precision: float | None
    retrieval_present: bool
    retrieval_position: int | None
    refusal_expected: bool
    refusal_correct: bool | None
    latency_seconds: float
    context_documents: int


class Scorecard(BaseModel):
    arm: str
    cases: int
    primary_hit_rate: float
    citation_precision: float | None
    refusal_correct_rate: float | None
    retrieval_presence_rate: float
    latency_p50: float
    latency_p95: float


def context_sections(prompt: str) -> list[str]:
    if _CONTEXT_HEADER not in prompt:
        return []
    body = prompt.split(_CONTEXT_HEADER, 1)[1]
    sections: list[str] = []
    for line in body.splitlines():
        match = _DOCUMENT_LINE.match(line.strip())
        if match is not None:
            sections.append(match.group(2).strip())
    return sections


def cited_sections(citations: list[dict[str, str]]) -> list[str]:
    return [str(citation.get("section", "")).strip() for citation in citations]


def _matches(expected: str, cited: str) -> bool:
    return expected == cited or expected in cited


def primary_hit(case: AskCase, citations: list[dict[str, str]]) -> bool:
    cited = cited_sections(citations)
    return any(_matches(expected, one) for expected in case.primary_cites for one in cited if one)


def citation_precision(case: AskCase, citations: list[dict[str, str]]) -> float | None:
    cited = [one for one in cited_sections(citations) if one]
    if not cited:
        return None
    allowed = [*case.primary_cites, *case.acceptable_cites]
    relevant = sum(1 for one in cited if any(_matches(expected, one) for expected in allowed))
    return relevant / len(cited)


def refusal_correct(answer_text: str, citations: list[dict[str, str]]) -> bool:
    lowered = answer_text.lower()
    declined = any(marker in lowered for marker in _REFUSAL_MARKERS)
    return declined and not citations


def retrieval_position(case: AskCase, sections: list[str]) -> int | None:
    for index, section in enumerate(sections, start=1):
        if any(_matches(expected, section) for expected in case.primary_cites):
            return index
    return None


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, round(fraction * (len(ordered) - 1)))
    return ordered[index]


def summarize(arm: str, scores: list[CaseScore]) -> Scorecard:
    answerable = [score for score in scores if not score.refusal_expected]
    refusals = [score for score in scores if score.refusal_expected]
    precisions = [
        score.citation_precision for score in answerable if score.citation_precision is not None
    ]
    latencies = [score.latency_seconds for score in scores]
    return Scorecard(
        arm=arm,
        cases=len(scores),
        primary_hit_rate=(
            sum(1 for score in answerable if score.primary_hit) / len(answerable)
            if answerable
            else 0.0
        ),
        citation_precision=(sum(precisions) / len(precisions) if precisions else None),
        refusal_correct_rate=(
            sum(1 for score in refusals if score.refusal_correct) / len(refusals)
            if refusals
            else None
        ),
        retrieval_presence_rate=(
            sum(1 for score in answerable if score.retrieval_present) / len(answerable)
            if answerable
            else 0.0
        ),
        latency_p50=percentile(latencies, 0.5),
        latency_p95=percentile(latencies, 0.95),
    )


def divergences(scores: list[CaseScore]) -> dict[str, list[str]]:
    return {
        "retrieved_but_uncited": [
            score.question_id
            for score in scores
            if score.retrieval_present and not score.primary_hit and not score.refusal_expected
        ],
        "cited_without_retrieval": [
            score.question_id
            for score in scores
            if score.primary_hit and not score.retrieval_present
        ],
    }
