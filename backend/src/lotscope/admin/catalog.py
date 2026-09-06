from dataclasses import dataclass, field
from datetime import date
from typing import Any

from lotscope.core.errors import ValidationError
from lotscope.ingestion.jobs import INGEST_JOBS

INGEST_KIND = "ingest"
RECOMPUTE_KIND = "recompute"
MAINTENANCE_KIND = "maintenance"


@dataclass(frozen=True)
class JobParam:
    name: str
    label: str
    type: str
    required: bool = True


@dataclass(frozen=True)
class JobSpec:
    id: str
    label: str
    kind: str
    description: str
    market: str | None = None
    dataset: str | None = None
    params: tuple[JobParam, ...] = field(default_factory=tuple)


_RECOMPUTE_SPECS: tuple[JobSpec, ...] = (
    JobSpec(
        id="rebuild:screen",
        label="Rebuild the screening index",
        kind=RECOMPUTE_KIND,
        description="Rebuild the nightly screening index over vacant land, which search ranks "
        "on and the buy box pre-filters on. A lot's own verdict is computed when it is read "
        "and needs no job.",
    ),
    JobSpec(
        id="recompute:distress",
        label="Recompute distress index",
        kind=RECOMPUTE_KIND,
        description="Recompute the motivated-seller distress index for every parcel, in one "
        "market or in every market when left blank.",
    ),
    JobSpec(
        id="recompute:vacancy",
        label="Recompute vacancy confidence",
        kind=RECOMPUTE_KIND,
        description="Recompute the vacancy-confidence cross-check for every vacant parcel, in "
        "one market or in every market when left blank.",
    ),
    JobSpec(
        id="recompute:assemblage",
        label="Recompute assemblage Top Plays",
        kind=RECOMPUTE_KIND,
        description="Recompute assemblage Top Plays for every vacant parcel, in one market or in "
        "every market when left blank.",
    ),
    JobSpec(
        id="recompute:buyers",
        label="Recompute buyer intelligence",
        kind=RECOMPUTE_KIND,
        description="Recompute cash-buyer / disposition profiles from recorded arm's-length "
        "vacant-lot sales. Only Philadelphia carries grantee names today.",
        market="phl",
        dataset="buyer_profile",
    ),
)


_MAINTENANCE_SPECS: tuple[JobSpec, ...] = (
    JobSpec(
        id="maintenance:seed_zoning",
        label="Seed zoning standards",
        kind=MAINTENANCE_KIND,
        description="Re-seed Title 14 zoning standards "
        "(permitted uses + dimensional standards) from code.",
    ),
    JobSpec(
        id="maintenance:snapshot_stats",
        label="Snapshot market stats",
        kind=MAINTENANCE_KIND,
        description="Recompute the per-market coverage snapshot (spine, geometry, verdict, "
        "vacant, comp share) that the ops health pages read.",
    ),
)


def ingest_job_id(market: str, dataset: str) -> str:
    return f"{INGEST_KIND}:{market}:{dataset}"


def _build_catalog() -> list[JobSpec]:
    keys = set(INGEST_JOBS)
    ingest = [
        JobSpec(
            id=ingest_job_id(market, dataset),
            label=f"{market.upper()} · {dataset}",
            kind=INGEST_KIND,
            description=f"Ingest the {dataset} dataset for {market.upper()}.",
            market=market,
            dataset=dataset,
        )
        for (market, dataset) in sorted(keys)
    ]
    return ingest + list(_RECOMPUTE_SPECS) + list(_MAINTENANCE_SPECS)


CATALOG: list[JobSpec] = _build_catalog()
CATALOG_BY_ID: dict[str, JobSpec] = {spec.id: spec for spec in CATALOG}


def parse_params(spec: JobSpec, raw: dict[str, Any]) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    for param in spec.params:
        value = raw.get(param.name)
        if value is None or value == "":
            if param.required:
                raise ValidationError(f"Missing required parameter {param.name!r}.")
            continue
        if param.type == "date":
            try:
                parsed[param.name] = date.fromisoformat(str(value))
            except ValueError as error:
                raise ValidationError(
                    f"Parameter {param.name!r} must be an ISO date (YYYY-MM-DD)."
                ) from error
        else:
            parsed[param.name] = str(value)
    return parsed


def storable_params(spec: JobSpec, raw: dict[str, Any]) -> dict[str, str]:
    parsed = parse_params(spec, raw)
    return {
        key: value.isoformat() if isinstance(value, date) else str(value)
        for key, value in parsed.items()
    }
