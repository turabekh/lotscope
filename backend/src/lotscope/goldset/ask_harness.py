import time
from typing import Any

from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.ai.client import StructuredGenerator
from lotscope.ai.embeddings import Embedder
from lotscope.ai.scope import PHILLYCODE_SOURCE, TITLE_14_SOURCE
from lotscope.ai.service import ask_the_parcel
from lotscope.goldset.ask_loader import (
    UNREACHABLE_GROUND_TRUTH,
    AskSetError,
    ground_truth_cites,
)
from lotscope.goldset.ask_metrics import (
    CaseScore,
    citation_precision,
    context_sections,
    primary_hit,
    refusal_correct,
    retrieval_position,
)
from lotscope.goldset.ask_schemas import AskCase

ARMS = (TITLE_14_SOURCE, PHILLYCODE_SOURCE)

_REACHABLE_SQL = text(
    "SELECT section FROM document WHERE source = :source AND section = ANY(:cites) "
    "AND length(trim(content)) > 0"
)


class ArmRun(BaseModel):
    arm: str
    question_id: str
    answer: str
    citations: list[dict[str, str]]
    context: list[str]
    latency_seconds: float
    error: str | None = None


class RunReport(BaseModel):
    run_id: str
    cases: int
    runs: list[ArmRun]
    scores: list[CaseScore]


class PromptCapturingGenerator:
    def __init__(self, inner: StructuredGenerator) -> None:
        self._inner = inner
        self.last_prompt = ""

    async def generate(self, *, system: str, user: str, schema: type) -> dict[str, Any]:
        self.last_prompt = user
        return await self._inner.generate(system=system, user=user, schema=schema)


async def assert_ground_truth_reachable(session: AsyncSession, cases: list[AskCase]) -> None:
    wanted = ground_truth_cites(cases)
    if not wanted:
        return
    found = set(
        (
            await session.execute(_REACHABLE_SQL, {"source": PHILLYCODE_SOURCE, "cites": wanted})
        ).scalars()
    )
    missing = sorted(set(wanted) - found)
    if missing:
        raise AskSetError(UNREACHABLE_GROUND_TRUTH.format(cites=missing))


async def run_case(
    session: AsyncSession,
    embedder: Embedder,
    generator: StructuredGenerator,
    case: AskCase,
    *,
    arm: str,
) -> ArmRun:
    capturing = PromptCapturingGenerator(generator)
    started = time.monotonic()
    answer_text = ""
    citations: list[dict[str, str]] = []
    error: str | None = None
    try:
        answer = await ask_the_parcel(
            session,
            case.parcel_number,
            case.question,
            embedder=embedder,
            generator=capturing,
            source_override=arm,
        )
        if answer is not None:
            answer_text = answer.answer
            citations = [
                {"source": citation.source, "section": citation.section}
                for citation in answer.citations
            ]
    except Exception as failure:
        error = f"{type(failure).__name__}: {failure}"[:300]
    return ArmRun(
        arm=arm,
        question_id=case.question_id,
        answer=answer_text,
        citations=citations,
        context=context_sections(capturing.last_prompt),
        latency_seconds=round(time.monotonic() - started, 3),
        error=error,
    )


def score_run(case: AskCase, run: ArmRun) -> CaseScore:
    position = retrieval_position(case, run.context)
    return CaseScore(
        question_id=case.question_id,
        arm=run.arm,
        primary_hit=primary_hit(case, run.citations),
        citation_precision=citation_precision(case, run.citations),
        retrieval_present=position is not None,
        retrieval_position=position,
        refusal_expected=case.expects_refusal,
        refusal_correct=(
            refusal_correct(run.answer, run.citations) if case.expects_refusal else None
        ),
        latency_seconds=run.latency_seconds,
        context_documents=len(run.context),
    )


async def run_evaluation(
    session: AsyncSession,
    embedder: Embedder,
    generator: StructuredGenerator,
    cases: list[AskCase],
    *,
    run_id: str,
    arms: tuple[str, ...] = ARMS,
) -> RunReport:
    await assert_ground_truth_reachable(session, cases)
    runs: list[ArmRun] = []
    scores: list[CaseScore] = []
    for case in cases:
        for arm in arms:
            run = await run_case(session, embedder, generator, case, arm=arm)
            runs.append(run)
            scores.append(score_run(case, run))
    return RunReport(run_id=run_id, cases=len(cases), runs=runs, scores=scores)
