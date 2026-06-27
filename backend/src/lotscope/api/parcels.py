from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.ai.client import StructuredGenerator
from lotscope.ai.embeddings import Embedder
from lotscope.ai.schemas import ParcelAnswer
from lotscope.ai.service import ask_the_parcel
from lotscope.api.deps import get_embedder, get_generator, get_session
from lotscope.core.errors import NotFoundError
from lotscope.parcels.schemas import ParcelDetail
from lotscope.parcels.service import get_parcel_detail
from lotscope.valuation.schemas import ValuationResult
from lotscope.valuation.service import value_parcel
from lotscope.verdict.schemas import VerdictResult
from lotscope.verdict.service import compute_verdict, get_verdict

router = APIRouter(prefix="/parcels", tags=["parcels"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)


@router.get("/{parcel_number}", response_model=ParcelDetail)
async def parcel_detail(parcel_number: str, session: SessionDep) -> ParcelDetail:
    detail = await get_parcel_detail(session, parcel_number)
    if detail is None:
        raise NotFoundError(f"Parcel {parcel_number} was not found.")
    return detail


@router.get("/{parcel_number}/verdict", response_model=VerdictResult)
async def parcel_verdict(parcel_number: str, session: SessionDep) -> VerdictResult:
    verdict = await get_verdict(session, parcel_number)
    if verdict is None:
        raise NotFoundError(
            f"No verdict has been computed for parcel {parcel_number}; refresh it first."
        )
    return verdict


@router.post("/{parcel_number}/verdict/refresh", response_model=VerdictResult)
async def refresh_parcel_verdict(parcel_number: str, session: SessionDep) -> VerdictResult:
    verdict = await compute_verdict(session, parcel_number)
    if verdict is None:
        raise NotFoundError(f"Parcel {parcel_number} was not found.")
    await session.commit()
    return verdict


@router.get("/{parcel_number}/comps", response_model=ValuationResult)
async def parcel_comps(
    parcel_number: str,
    session: SessionDep,
    radius_ft: Annotated[float, Query(gt=0, le=10000)] = 1500.0,
    years: Annotated[int, Query(ge=1, le=20)] = 3,
) -> ValuationResult:
    result = await value_parcel(session, parcel_number, radius_ft=radius_ft, years=years)
    if result is None:
        raise NotFoundError(f"Parcel {parcel_number} was not found.")
    return result


@router.post("/{parcel_number}/ask", response_model=ParcelAnswer)
async def ask_parcel(
    parcel_number: str,
    body: AskRequest,
    session: SessionDep,
    embedder: Annotated[Embedder, Depends(get_embedder)],
    generator: Annotated[StructuredGenerator, Depends(get_generator)],
) -> ParcelAnswer:
    answer = await ask_the_parcel(
        session, parcel_number, body.question, embedder=embedder, generator=generator
    )
    if answer is None:
        raise NotFoundError(f"Parcel {parcel_number} was not found.")
    return answer
