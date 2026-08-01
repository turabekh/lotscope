import re

from lotscope.accounts.tiers import (
    ASK_DAILY_LIMITS,
    LEAD_LIST_LIMITS,
    PARCEL_VIEW_DAILY_LIMITS,
    PLAN_CATALOG,
    ask_daily_limit,
    export_monthly_limit,
    feed_access,
    lead_list_limit,
    parcel_view_daily_limit,
)

_TIERS = ("free", "pro", "investor", "enterprise")

_UNENFORCEABLE_CLAIMS: frozenset[str] = frozenset(
    {
        "Team seats and support",
        "Bulk export and API access",
    }
)


def _number(text: str) -> int | None:
    match = re.search(r"([\d,]+)", text)
    return int(match.group(1).replace(",", "")) if match else None


def _highlights(tier: str) -> tuple[str, ...]:
    for entry in PLAN_CATALOG:
        if entry.tier == tier:
            return entry.highlights
    raise AssertionError(f"no catalog entry for {tier}")


def test_every_tier_in_the_limit_tables_is_advertised() -> None:
    advertised = {entry.tier for entry in PLAN_CATALOG}

    assert advertised == set(_TIERS)
    assert set(ASK_DAILY_LIMITS) == advertised
    assert set(PARCEL_VIEW_DAILY_LIMITS) == advertised
    assert set(LEAD_LIST_LIMITS) == advertised


def test_advertised_ai_question_counts_match_the_enforced_limit() -> None:
    for tier in _TIERS:
        for line in _highlights(tier):
            if "AI question" not in line:
                continue
            limit = ask_daily_limit(tier)
            if "Unlimited" in line:
                assert limit is None, (
                    f"{tier} advertises unlimited AI questions but enforces {limit}"
                )
            else:
                assert _number(line) == limit, f"{tier} advertises {line!r} but enforces {limit}"


def test_advertised_parcel_verdict_counts_match_the_enforced_limit() -> None:
    for tier in _TIERS:
        for line in _highlights(tier):
            if "parcel verdict" not in line:
                continue
            limit = parcel_view_daily_limit(tier)
            if "Unlimited" in line:
                assert limit is None, f"{tier} advertises unlimited verdicts but enforces {limit}"
            else:
                assert _number(line) == limit, f"{tier} advertises {line!r} but enforces {limit}"


def test_advertised_lead_counts_match_the_enforced_limit() -> None:
    for tier in _TIERS:
        for line in _highlights(tier):
            if "lead" not in line.lower():
                continue
            assert _number(line) == lead_list_limit(tier), (
                f"{tier} advertises {line!r} but enforces {lead_list_limit(tier)}"
            )


def test_a_tier_advertising_export_can_actually_export() -> None:
    for tier in _TIERS:
        for line in _highlights(tier):
            if "export" not in line.lower():
                continue
            limit = export_monthly_limit(tier)
            assert limit is None or limit > 0, f"{tier} advertises export but is capped at {limit}"


def test_a_tier_advertising_the_deal_feed_actually_has_it() -> None:
    for tier in _TIERS:
        for line in _highlights(tier):
            if "deal feed" in line.lower():
                assert feed_access(tier), f"{tier} advertises the deal feed but is not granted it"


def test_claims_with_no_enforcement_are_declared_rather_than_silent() -> None:
    unmapped = {
        line for entry in PLAN_CATALOG for line in entry.highlights if line in _UNENFORCEABLE_CLAIMS
    }

    assert unmapped == _UNENFORCEABLE_CLAIMS, (
        "The unenforceable-claim allowlist has drifted from the catalog. Every entry here is a "
        "capability advertised with nothing in tiers.py behind it; see "
        "docs/launch-readiness/entitlement-audit-2026-08-01.md"
    )
