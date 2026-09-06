from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.core.config import get_settings
from lotscope.core.errors import ValidationError
from lotscope.core.provenance import calculated
from lotscope.corrections.schemas import CorrectionCreate, CorrectionRead, CorrectionResolve
from lotscope.corrections.service import (
    list_corrections,
    list_own_corrections,
    notify_correction_reporter,
    report_correction,
    resolve_correction,
)
from lotscope.verdict.schemas import VerdictResult

pytestmark = pytest.mark.integration

_COMPUTED_AT = datetime(2026, 7, 1, tzinfo=UTC)


def _verdict() -> VerdictResult:
    return VerdictResult(
        parcel_number="phl:1",
        buildability_score=80.0,
        opportunity_score=70.0,
        summary="RSA-5",
        can_build_by_right=True,
        by_right_units=1,
        max_height_ft=38.0,
        needs_variance=False,
        buildable_area_sqft=490.0,
        value_estimate_low=None,
        value_estimate_high=None,
        value_confidence=None,
        assessment_market_gap=None,
        arv=None,
        est_profit=None,
        est_margin=None,
        max_allowable_offer=None,
        deal_score=None,
        is_underpriced=None,
        risk_score=10.0,
        risk_flags=[],
        sources=[],
        field_trust={"by_right_units": calculated("zoning_district", method_version="adr-0056")},
        computed_at=_COMPUTED_AT,
    )


async def _user(session: AsyncSession) -> int:
    await session.execute(
        text(
            "INSERT INTO app_user (email, hashed_password, role, tier, is_active) "
            "VALUES ('reporter@example.com', 'x', 'user', 'pro', true)"
        )
    )
    await session.flush()
    return int(
        await session.scalar(text("SELECT id FROM app_user WHERE email = 'reporter@example.com'"))
    )


async def _report(session: AsyncSession, user_id: int) -> CorrectionRead:
    request = CorrectionCreate(
        section="buildability",
        field_name="by_right_units",
        description="The district here is RSA-3, not RSA-5.",
    )
    return await report_correction(
        session,
        parcel_number="phl:1",
        market_code="phl",
        reported_by=user_id,
        request=request,
        verdict=_verdict(),
    )


async def test_a_correction_snapshots_the_disputed_result(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    correction = await _report(db_session, user_id)
    assert correction.verdict_computed_at == _COMPUTED_AT
    assert correction.field_status == "calculated"
    assert correction.source_label == "zoning_district"
    assert correction.status == "open"


async def test_the_snapshot_survives_a_later_recompute(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    await _report(db_session, user_id)

    stored = (await list_corrections(db_session))[0]
    assert stored.verdict_computed_at == _COMPUTED_AT
    assert stored.field_status == "calculated"


async def test_a_correction_without_a_verdict_still_records_the_report(
    db_session: AsyncSession,
) -> None:
    user_id = await _user(db_session)
    correction = await report_correction(
        db_session,
        parcel_number="phl:1",
        market_code="phl",
        reported_by=user_id,
        request=CorrectionCreate(section="other", description="Nothing renders on this parcel."),
        verdict=None,
    )
    assert correction.status == "open"


async def test_closing_a_correction_requires_a_resolution(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    correction = await _report(db_session, user_id)

    with pytest.raises(ValidationError):
        await resolve_correction(
            db_session,
            correction.id,
            resolved_by=user_id,
            request=CorrectionResolve(status="resolved"),
        )


async def test_rejection_is_a_first_class_outcome(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    correction = await _report(db_session, user_id)

    rejected = await resolve_correction(
        db_session,
        correction.id,
        resolved_by=user_id,
        request=CorrectionResolve(
            status="rejected", resolution="Verified correct against the map."
        ),
    )
    assert rejected.status == "rejected"
    assert rejected.resolved_at is not None


async def test_a_closed_correction_cannot_be_reclosed(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    correction = await _report(db_session, user_id)
    await resolve_correction(
        db_session,
        correction.id,
        resolved_by=user_id,
        request=CorrectionResolve(status="resolved", resolution="Reingested and corrected."),
    )
    with pytest.raises(ValidationError):
        await resolve_correction(
            db_session,
            correction.id,
            resolved_by=user_id,
            request=CorrectionResolve(status="resolved", resolution="Again."),
        )


async def test_a_blank_description_is_rejected_at_the_boundary() -> None:
    with pytest.raises(ValueError, match="at least 10 characters"):
        CorrectionCreate(section="verdict", description="   ")


class _RecordingSender:
    def __init__(self) -> None:
        self.sent: list[dict[str, str]] = []

    async def send(
        self,
        *,
        to: str,
        subject: str,
        html: str,
        text: str,
        attachment: object | None = None,
        list_unsubscribe: str | None = None,
    ) -> None:
        self.sent.append({"to": to, "subject": subject, "html": html, "text": text})


async def test_a_reporter_sees_only_their_own_corrections(db_session: AsyncSession) -> None:
    reporter = await _user(db_session)
    await _report(db_session, reporter)

    await db_session.execute(
        text(
            "INSERT INTO app_user (email, hashed_password, role, tier, is_active) "
            "VALUES ('other@example.com', 'x', 'user', 'pro', true)"
        )
    )
    await db_session.flush()
    other = int(
        await db_session.scalar(text("SELECT id FROM app_user WHERE email = 'other@example.com'"))
    )

    assert len(await list_own_corrections(db_session, reporter)) == 1
    assert await list_own_corrections(db_session, other) == []


async def test_the_triage_queue_filters_by_status(db_session: AsyncSession) -> None:
    reporter = await _user(db_session)
    first = await _report(db_session, reporter)
    await _report(db_session, reporter)

    await resolve_correction(
        db_session,
        first.id,
        resolved_by=reporter,
        request=CorrectionResolve(status="resolved", resolution="Fixed the district."),
    )

    assert [c.id for c in await list_corrections(db_session, status="resolved")] == [first.id]
    assert len(await list_corrections(db_session, status="open")) == 1


async def test_the_reporter_is_told_the_outcome_and_what_they_reported(
    db_session: AsyncSession,
) -> None:
    reporter = await _user(db_session)
    correction = await _report(db_session, reporter)
    resolved = await resolve_correction(
        db_session,
        correction.id,
        resolved_by=reporter,
        request=CorrectionResolve(status="resolved", resolution="Reseeded the district."),
    )

    sender = _RecordingSender()
    sent = await notify_correction_reporter(
        sender, get_settings(), resolved, to_email="reporter@example.com"
    )

    assert sent is True
    assert sender.sent[0]["to"] == "reporter@example.com"
    assert "Reseeded the district." in sender.sent[0]["text"]
    assert "The district here is RSA-3, not RSA-5." in sender.sent[0]["text"]


async def test_a_rejected_report_does_not_claim_a_change_was_made(
    db_session: AsyncSession,
) -> None:
    reporter = await _user(db_session)
    correction = await _report(db_session, reporter)
    rejected = await resolve_correction(
        db_session,
        correction.id,
        resolved_by=reporter,
        request=CorrectionResolve(status="rejected", resolution="Zoning confirmed as RSA-5."),
    )

    sender = _RecordingSender()
    await notify_correction_reporter(
        sender, get_settings(), rejected, to_email="reporter@example.com"
    )

    assert "did not make a change" in sender.sent[0]["text"]
    assert "corrected this" not in sender.sent[0]["text"]


async def test_an_open_correction_notifies_nobody(db_session: AsyncSession) -> None:
    reporter = await _user(db_session)
    correction = await _report(db_session, reporter)

    sender = _RecordingSender()
    sent = await notify_correction_reporter(
        sender, get_settings(), correction, to_email="reporter@example.com"
    )

    assert sent is False
    assert sender.sent == []
