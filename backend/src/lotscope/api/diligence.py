from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal

from arq import ArqRedis
from fastapi import APIRouter, Depends, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.accounts.models import User
from lotscope.accounts.purchases import DILIGENCE_SKU, SKU_PRICES_CENTS, may_download
from lotscope.api.deps import (
    ParcelKeyDep,
    canonicalize_parcel_key,
    get_arq_pool,
    get_current_user,
    get_session,
)
from lotscope.core.errors import NotFoundError, PaymentRequiredError
from lotscope.core.logging import get_logger
from lotscope.diligence.models import DiligenceRun
from lotscope.diligence.render import diligence_filename
from lotscope.diligence.service import get_run, latest_run, start_run

router = APIRouter(prefix="/diligence", tags=["diligence"])

_logger = get_logger(__name__)

SessionDep = Annotated[AsyncSession, Depends(get_session)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]
ArqDep = Annotated[ArqRedis, Depends(get_arq_pool)]


class DiligenceRequest(BaseModel):
    parcel: str


class DiligenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    parcel_number: str
    status: Literal["pending", "ready", "failed"]
    error: str | None = None
    generated_at: datetime | None = None
    download_url: str | None = None
    price_cents: int = SKU_PRICES_CENTS[DILIGENCE_SKU]


def _to_read(run: DiligenceRun) -> DiligenceRead:
    read = DiligenceRead.model_validate(run)
    if read.status == "ready":
        read.download_url = f"/diligence/{read.id}/download"
    return read


@router.post("", response_model=DiligenceRead, status_code=status.HTTP_202_ACCEPTED)
async def request_diligence(
    data: DiligenceRequest, session: SessionDep, user: CurrentUserDep, arq: ArqDep
) -> DiligenceRead:
    """Start a checklist. It reads two sources live, so the worker builds it."""
    run = await start_run(session, user.id, canonicalize_parcel_key(data.parcel))
    await session.commit()
    await arq.enqueue_job("build_diligence_report", run.id)
    return _to_read(run)


@router.get("/parcel/{parcel_number}", response_model=DiligenceRead | None)
async def read_latest_for_parcel(
    parcel_number: ParcelKeyDep, session: SessionDep, user: CurrentUserDep
) -> DiligenceRead | None:
    run = await latest_run(session, user.id, parcel_number)
    return _to_read(run) if run is not None else None


@router.get("/{run_id}", response_model=DiligenceRead)
async def read_own_diligence(
    run_id: int, session: SessionDep, user: CurrentUserDep
) -> DiligenceRead:
    return _to_read(await get_run(session, run_id, user.id))


@router.get("/{run_id}/download")
async def download_own_diligence(
    run_id: int, session: SessionDep, user: CurrentUserDep
) -> FileResponse:
    run = await get_run(session, run_id, user.id)
    if run.status != "ready" or run.pdf_path is None:
        raise NotFoundError(f"Diligence {run_id} is not ready to download.")
    if not Path(run.pdf_path).exists():
        _logger.error("diligence_pdf_missing", run_id=run.id, path=run.pdf_path)
        raise NotFoundError(
            f"Diligence {run_id} was generated but its PDF is not readable from this "
            "service. Ask for it to be rebuilt."
        )
    # The gate is the parcel, not the run: a buyer who paid for this lot's diligence can
    # download the report they paid for, including a later rebuild of it.
    if not await may_download(session, user, DILIGENCE_SKU, run.parcel_number):
        raise PaymentRequiredError(
            f"Lot Diligence costs ${SKU_PRICES_CENTS[DILIGENCE_SKU] / 100:,.0f}. "
            "Buy it from the lot to download the checklist."
        )
    return FileResponse(
        run.pdf_path,
        media_type="application/pdf",
        filename=diligence_filename(run.parcel_number),
    )
