from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.ai.client import StructuredGenerator
from lotscope.ai.embeddings import Embedder
from lotscope.ai.errors import GenerationError, UngroundedAnswerError
from lotscope.ai.prompts import SYSTEM_PROMPT, build_user_prompt
from lotscope.ai.retrieval import embed_and_search, fetch_district_documents
from lotscope.ai.schemas import ParcelAnswer
from lotscope.parcels.schemas import ParcelDetail
from lotscope.parcels.service import get_parcel_detail
from lotscope.verdict.schemas import VerdictResult
from lotscope.verdict.service import get_verdict

TITLE_14_SOURCE = "title14"


def _parcel_facts(detail: ParcelDetail, verdict: VerdictResult | None) -> str:
    lines = [
        f"Parcel {detail.parcel_number}; address {detail.address}; "
        f"zoning {detail.base_zoning_code}; lot area {detail.lot_area_sqft} sqft; "
        f"vacant={detail.is_vacant}; city-owned={detail.is_city_owned}."
    ]
    if verdict is not None:
        lines.append(
            f"Verdict ({verdict.verdict_version}): {verdict.summary}. "
            f"can_build_by_right={verdict.can_build_by_right}; "
            f"by_right_units={verdict.by_right_units}; risk_score={verdict.risk_score}."
        )
    return "\n".join(lines)


async def ask_the_parcel(
    session: AsyncSession,
    parcel_number: str,
    question: str,
    *,
    embedder: Embedder,
    generator: StructuredGenerator,
    document_limit: int = 5,
) -> ParcelAnswer | None:
    detail = await get_parcel_detail(session, parcel_number)
    if detail is None:
        return None

    verdict = await get_verdict(session, parcel_number)
    documents = await embed_and_search(
        session, embedder, question, limit=document_limit, source=TITLE_14_SOURCE
    )
    if detail.base_zoning_code:
        pinned = await fetch_district_documents(
            session, detail.base_zoning_code, source=TITLE_14_SOURCE
        )
        if pinned:
            seen = {document.id for document in pinned}
            documents = (pinned + [d for d in documents if d.id not in seen])[
                : max(document_limit, len(pinned))
            ]
    user_prompt = build_user_prompt(question, _parcel_facts(detail, verdict), documents)

    raw = await generator.generate(system=SYSTEM_PROMPT, user=user_prompt, schema=ParcelAnswer)
    try:
        answer = ParcelAnswer.model_validate(raw)
    except ValidationError as error:
        raise GenerationError(f"The model returned an invalid answer: {error}") from error

    if not answer.citations:
        raise UngroundedAnswerError
    return answer
