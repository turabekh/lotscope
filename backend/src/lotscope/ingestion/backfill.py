from collections import Counter
from dataclasses import dataclass, field

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.core.logging import get_logger
from lotscope.ingestion.deed_recovery import (
    RESOLVED,
    build_address_index,
    recover_parcel,
    summarise,
)

_logger = get_logger("ingestion.backfill")

DEFAULT_BATCH = 5000
MAX_SHRINK_RATIO = 0.98


class BackfillVerificationError(RuntimeError):
    pass


@dataclass
class BackfillReport:
    scanned: int = 0
    staged: int = 0
    applied: int = 0
    reasons: Counter[str] = field(default_factory=Counter)
    dry_run: bool = False


def verify_no_loss(*, before: int, after: int, label: str) -> None:
    if before == 0:
        return
    if after < before * MAX_SHRINK_RATIO:
        raise BackfillVerificationError(
            f"{label} would shrink from {before:,} to {after:,}; refusing to swap."
        )


_ADDRESS_INDEX_SQL = text(
    "SELECT parcel_number, address FROM parcel WHERE market_code = :market AND address IS NOT NULL"
)

_EXISTING_DOCS_SQL = text("SELECT document_id FROM sale WHERE document_id = ANY(:document_ids)")

_INSERT_SQL = text(
    "INSERT INTO sale (parcel_number, document_id, document_type, sale_date, sale_price, "
    "grantor, grantee, source) "
    "VALUES (:parcel_number, :document_id, :document_type, :sale_date, :sale_price, "
    ":grantor, :grantee, :source) "
    "ON CONFLICT (parcel_number, document_id) DO NOTHING"
)


async def recover_deeds(
    session: AsyncSession,
    candidates: list[dict[str, object]],
    *,
    market: str = "phl",
    dry_run: bool = False,
) -> BackfillReport:
    report = BackfillReport(scanned=len(candidates), dry_run=dry_run)
    if not candidates:
        return report

    rows = (await session.execute(_ADDRESS_INDEX_SQL, {"market": market})).all()
    index = build_address_index([(row[0], row[1]) for row in rows])

    outcomes = [recover_parcel(str(item.get("street_address") or ""), index) for item in candidates]
    report.reasons = summarise(outcomes)

    resolved = [
        {**item, "parcel_number": outcome.parcel_number}
        for item, outcome in zip(candidates, outcomes, strict=True)
        if outcome.reason == RESOLVED
    ]
    report.staged = len(resolved)

    if dry_run:
        _logger.info(
            "deed_recovery_dry_run",
            scanned=report.scanned,
            staged=report.staged,
            reasons=dict(report.reasons),
        )
        return report

    for row in resolved:
        await session.execute(
            _INSERT_SQL,
            {
                "parcel_number": row["parcel_number"],
                "document_id": row["document_id"],
                "document_type": row.get("document_type"),
                "sale_date": row.get("sale_date"),
                "sale_price": row.get("sale_price"),
                "grantor": row.get("grantor"),
                "grantee": row.get("grantee"),
                "source": "rtt_summary_recovered",
            },
        )
    report.applied = len(resolved)
    _logger.info(
        "deed_recovery_applied",
        scanned=report.scanned,
        applied=report.applied,
        reasons=dict(report.reasons),
    )
    return report


_MAILING_COVERAGE_SQL = text(
    "SELECT count(*) AS total, "
    "count(*) FILTER (WHERE mailing_address IS NOT NULL AND btrim(mailing_address) <> '') "
    "AS with_mailing FROM parcel WHERE market_code = :market"
)


@dataclass(frozen=True)
class MailingCoverage:
    total: int
    with_mailing: int

    @property
    def share(self) -> float:
        return self.with_mailing / self.total if self.total else 0.0


async def measure_mailing_coverage(session: AsyncSession, market: str = "phl") -> MailingCoverage:
    row = (await session.execute(_MAILING_COVERAGE_SQL, {"market": market})).one()
    return MailingCoverage(total=int(row.total), with_mailing=int(row.with_mailing))


async def apply_mailing_updates(
    session: AsyncSession,
    updates: list[dict[str, object]],
    *,
    market: str = "phl",
    dry_run: bool = False,
) -> BackfillReport:
    report = BackfillReport(scanned=len(updates), dry_run=dry_run)
    usable = [row for row in updates if row.get("mailing_address")]
    report.staged = len(usable)
    if dry_run or not usable:
        _logger.info("mailing_backfill_dry_run", scanned=report.scanned, staged=report.staged)
        return report

    before = await measure_mailing_coverage(session, market)
    for row in usable:
        await session.execute(
            text(
                "UPDATE parcel SET mailing_address = :mailing, updated_at = now() "
                "WHERE parcel_number = :pn AND market_code = :market"
            ),
            {"mailing": row["mailing_address"], "pn": row["parcel_number"], "market": market},
        )
    after = await measure_mailing_coverage(session, market)
    verify_no_loss(
        before=before.with_mailing, after=after.with_mailing, label="parcel.mailing_address"
    )
    report.applied = len(usable)
    _logger.info(
        "mailing_backfill_applied",
        applied=report.applied,
        coverage_before=round(before.share, 4),
        coverage_after=round(after.share, 4),
    )
    return report
