from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.core.config import Settings
from lotscope.core.errors import NotFoundError, ValidationError
from lotscope.corrections.models import ParcelCorrection
from lotscope.corrections.schemas import (
    _OPEN_STATES,
    _TERMINAL_STATES,
    CorrectionCreate,
    CorrectionRead,
    CorrectionResolve,
)
from lotscope.notifications.email import EmailSender
from lotscope.verdict.schemas import VerdictResult


def _snapshot(verdict: VerdictResult | None, field_name: str | None) -> dict[str, object | None]:
    if verdict is None:
        return {}
    provenance = verdict.field_trust.get(field_name) if field_name else None
    return {
        "verdict_version": verdict.verdict_version,
        "verdict_computed_at": verdict.computed_at,
        "field_status": provenance.status if provenance else None,
        "source_label": provenance.source_label if provenance else None,
        "source_as_of": provenance.as_of if provenance else None,
    }


async def report_correction(
    session: AsyncSession,
    *,
    parcel_number: str,
    market_code: str,
    reported_by: int,
    request: CorrectionCreate,
    verdict: VerdictResult | None,
) -> CorrectionRead:
    correction = ParcelCorrection(
        parcel_number=parcel_number,
        market_code=market_code,
        reported_by=reported_by,
        section=request.section,
        field_name=request.field_name,
        description=request.description,
        attachment_ref=request.attachment_ref,
        status="open",
        **_snapshot(verdict, request.field_name),
    )
    session.add(correction)
    await session.flush()
    return CorrectionRead.model_validate(correction)


async def list_corrections(
    session: AsyncSession, *, status: str | None = None, limit: int = 100
) -> list[CorrectionRead]:
    statement = select(ParcelCorrection).order_by(ParcelCorrection.id.desc()).limit(limit)
    if status is not None:
        statement = statement.where(ParcelCorrection.status == status)
    rows = (await session.execute(statement)).scalars().all()
    return [CorrectionRead.model_validate(row) for row in rows]


async def resolve_correction(
    session: AsyncSession, correction_id: int, *, resolved_by: int, request: CorrectionResolve
) -> CorrectionRead:
    correction = await session.get(ParcelCorrection, correction_id)
    if correction is None:
        raise NotFoundError(f"Correction {correction_id} was not found.")
    if correction.status in _TERMINAL_STATES:
        raise ValidationError(f"Correction {correction_id} is already {correction.status}.")
    if request.status not in _OPEN_STATES | _TERMINAL_STATES:
        raise ValidationError(f"Unknown correction status {request.status!r}.")
    if request.status in _TERMINAL_STATES and not (request.resolution or "").strip():
        raise ValidationError("Closing a correction requires a resolution note.")

    correction.status = request.status
    correction.resolution = request.resolution
    if request.status in _TERMINAL_STATES:
        correction.resolved_at = datetime.now(UTC)
        correction.resolved_by = resolved_by
    await session.flush()
    return CorrectionRead.model_validate(correction)


async def list_own_corrections(
    session: AsyncSession, owner_id: int, *, limit: int = 100
) -> list[CorrectionRead]:
    rows = (
        await session.execute(
            select(ParcelCorrection)
            .where(ParcelCorrection.reported_by == owner_id)
            .order_by(ParcelCorrection.id.desc())
            .limit(limit)
        )
    ).scalars()
    return [CorrectionRead.model_validate(row) for row in rows]


def _resolution_lines(correction: CorrectionRead) -> tuple[str, str]:
    outcome = (
        "We have corrected this and the parcel now reflects the change."
        if correction.status == "resolved"
        else "We reviewed this and did not make a change."
    )
    note = (correction.resolution or "").strip() or "No further detail was recorded."
    return outcome, note


async def notify_correction_reporter(
    sender: EmailSender,
    settings: Settings,
    correction: CorrectionRead,
    *,
    to_email: str,
) -> bool:
    if correction.status not in _TERMINAL_STATES:
        return False

    outcome, note = _resolution_lines(correction)
    parcel_url = (
        f"{settings.app_base_url.rstrip('/')}/parcel/"
        f"{correction.market_code}/{correction.parcel_number}"
    )
    subject = f"Your report on {correction.parcel_number} was {correction.status}"
    text = (
        f"{outcome}\n\n"
        f"What you reported: {correction.description}\n\n"
        f"What we found: {note}\n\n"
        f"View the parcel: {parcel_url}\n"
    )
    html = (
        f"<p>{outcome}</p>"
        f"<p><strong>What you reported:</strong> {correction.description}</p>"
        f"<p><strong>What we found:</strong> {note}</p>"
        f'<p><a href="{parcel_url}">View the parcel</a></p>'
    )
    await sender.send(to=to_email, subject=subject, html=html, text=text)
    return True
