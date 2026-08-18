import asyncio
import sys
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.core.config import get_settings
from lotscope.core.db import create_engine, create_session_factory
from lotscope.distress.service import find_leads

MARKET = "phl"
AUDITED_PARCEL = "phl:201133900"
CONTROL_PARCEL = "phl:491313100"
EXPECTED_VERDICT_VERSION = "v11"
PRIOR_VERDICT_VERSION = "v10"
EXPECTED_DISTRESS_PROFILE = "philly-distress-v2"


@dataclass(frozen=True)
class Check:
    name: str
    passed: bool
    detail: str


async def _scalar(session: AsyncSession, sql: str, **params: object) -> object:
    return await session.scalar(text(sql), params)


async def _sweep_is_complete(session: AsyncSession) -> Check:
    missing = await _scalar(
        session,
        "SELECT count(*) FROM parcel p LEFT JOIN parcel_verdict v "
        "ON v.parcel_number = p.parcel_number AND v.verdict_version = CAST(:version AS text) "
        "WHERE p.market_code = CAST(:market AS text) AND v.parcel_number IS NULL",
        version=EXPECTED_VERDICT_VERSION,
        market=MARKET,
    )
    return Check(
        "every phl parcel carries a v11 verdict",
        missing == 0,
        f"{missing} parcels without a {EXPECTED_VERDICT_VERSION} verdict",
    )


async def _no_incomplete_verdicts(session: AsyncSession) -> Check:
    incomplete = await _scalar(
        session,
        "SELECT count(*) FROM parcel_verdict "
        "WHERE verdict_version = CAST(:version AS text) "
        "AND (risk_score IS NULL OR recommendation IS NULL)",
        version=EXPECTED_VERDICT_VERSION,
    )
    return Check(
        "no v11 verdict is missing a risk score or recommendation",
        incomplete == 0,
        f"{incomplete} incomplete rows",
    )


async def _distress_profile_is_current(session: AsyncSession) -> Check:
    stale = await _scalar(
        session,
        "SELECT count(*) FROM parcel_distress pd JOIN parcel p "
        "ON p.parcel_number = pd.parcel_number "
        "WHERE p.market_code = CAST(:market AS text) "
        "AND pd.profile_id IS DISTINCT FROM CAST(:profile AS text)",
        market=MARKET,
        profile=EXPECTED_DISTRESS_PROFILE,
    )
    return Check(
        "every phl parcel is scored under philly-distress-v2",
        stale == 0,
        f"{stale} parcels not on {EXPECTED_DISTRESS_PROFILE}",
    )


async def _risk_never_rose(session: AsyncSession) -> Check:
    row = (
        await session.execute(
            text(
                "SELECT count(*) AS compared, "
                "  count(*) FILTER (WHERE v.risk_score > s.risk_score) AS rose "
                "FROM parcel_verdict v JOIN pre_v11_verdict s "
                "ON s.parcel_number = v.parcel_number "
                "WHERE v.verdict_version = CAST(:version AS text) "
                "AND s.verdict_version = CAST(:baseline AS text)"
            ),
            {"version": EXPECTED_VERDICT_VERSION, "baseline": PRIOR_VERDICT_VERSION},
        )
    ).one()
    return Check(
        "v11 only removes risk weight, never adds it (against the v10 baseline)",
        row.rose == 0 and row.compared > 0,
        f"{row.rose} of {row.compared} v10-baseline parcels gained risk",
    )


async def _audited_parcel_fell(session: AsyncSession) -> Check:
    row = (
        await session.execute(
            text(
                "SELECT v.risk_score AS risk_now, s.risk_score AS risk_before, "
                "  pd.score AS distress_now, ps.score AS distress_before, "
                "  pd.tier AS tier_now, ps.tier AS tier_before, v.verdict_version "
                "FROM parcel_verdict v "
                "LEFT JOIN pre_v11_verdict s ON s.parcel_number = v.parcel_number "
                "LEFT JOIN parcel_distress pd ON pd.parcel_number = v.parcel_number "
                "LEFT JOIN pre_v11_distress ps ON ps.parcel_number = v.parcel_number "
                "WHERE v.parcel_number = CAST(:parcel AS text)"
            ),
            {"parcel": AUDITED_PARCEL},
        )
    ).first()
    if row is None:
        return Check("the audited parcel loses its borrowed distress", False, "no verdict row")
    passed = (
        row.verdict_version == EXPECTED_VERDICT_VERSION
        and row.risk_now < row.risk_before
        and row.distress_now < row.distress_before
    )
    return Check(
        "the audited parcel loses its borrowed distress",
        passed,
        f"risk {row.risk_before}->{row.risk_now}, distress {row.distress_before}->"
        f"{row.distress_now}, tier {row.tier_before}->{row.tier_now}",
    )


async def _control_held(session: AsyncSession) -> Check:
    row = (
        await session.execute(
            text(
                "SELECT v.risk_score AS risk_now, s.risk_score AS risk_before, "
                "  pd.score AS distress_now, ps.score AS distress_before, v.verdict_version "
                "FROM parcel_verdict v "
                "LEFT JOIN pre_v11_verdict s ON s.parcel_number = v.parcel_number "
                "LEFT JOIN parcel_distress pd ON pd.parcel_number = v.parcel_number "
                "LEFT JOIN pre_v11_distress ps ON ps.parcel_number = v.parcel_number "
                "WHERE v.parcel_number = CAST(:parcel AS text)"
            ),
            {"parcel": CONTROL_PARCEL},
        )
    ).first()
    if row is None:
        return Check("the control parcel is unchanged on every axis", False, "no verdict row")
    passed = (
        row.verdict_version == EXPECTED_VERDICT_VERSION
        and row.risk_now == row.risk_before
        and row.distress_now == row.distress_before
    )
    return Check(
        "the control parcel is unchanged on every axis",
        passed,
        f"version {row.verdict_version}, risk {row.risk_before}->{row.risk_now}, "
        f"distress {row.distress_before}->{row.distress_now}",
    )


async def _leads_carry_no_borrowed_debt(session: AsyncSession) -> Check:
    leads = await find_leads(session, market_code=MARKET, limit=500, min_score=30)
    if not leads:
        return Check("no lead shows a debt its owner does not owe", False, "no leads returned")
    with_amount = [lead for lead in leads if lead.total_due]
    counts = dict(
        (
            await session.execute(
                text(
                    "SELECT parcel_number, debt_counts FROM parcel_distress "
                    "WHERE parcel_number = ANY(:parcels)"
                ),
                {"parcels": [lead.parcel_number for lead in with_amount]},
            )
        ).all()
    )
    borrowed = [lead for lead in with_amount if counts.get(lead.parcel_number) is not True]
    return Check(
        "no lead shows a debt its owner does not owe",
        not borrowed,
        f"{len(with_amount)} of {len(leads)} leads show an amount, "
        f"{len(borrowed)} of those unattributed",
    )


async def run() -> int:
    settings = get_settings()
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    try:
        async with session_factory() as session:
            checks = [
                await _sweep_is_complete(session),
                await _no_incomplete_verdicts(session),
                await _distress_profile_is_current(session),
                await _risk_never_rose(session),
                await _audited_parcel_fell(session),
                await _control_held(session),
                await _leads_carry_no_borrowed_debt(session),
            ]
    finally:
        await engine.dispose()

    for check in checks:
        marker = "PASS" if check.passed else "FAIL"
        print(f"[{marker}] {check.name} — {check.detail}")
    failures = [check for check in checks if not check.passed]
    print(f"\n{len(checks) - len(failures)}/{len(checks)} checks passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(run()))
