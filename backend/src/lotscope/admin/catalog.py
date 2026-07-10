from dataclasses import dataclass

from lotscope.ingestion.jobs import INGEST_JOBS

INGEST_KIND = "ingest"
RECOMPUTE_KIND = "recompute"


@dataclass(frozen=True)
class JobSpec:
    id: str
    label: str
    kind: str
    description: str
    market: str | None = None
    dataset: str | None = None


_RECOMPUTE_SPECS: tuple[JobSpec, ...] = (
    JobSpec(
        id="recompute:verdicts",
        label="Recompute verdicts (all parcels)",
        kind=RECOMPUTE_KIND,
        description="Recompute the Parcel Verdict for every parcel in every market.",
    ),
    JobSpec(
        id="recompute:vacant_verdicts",
        label="Recompute verdicts (vacant only)",
        kind=RECOMPUTE_KIND,
        description="Recompute the Parcel Verdict for vacant parcels only.",
    ),
    JobSpec(
        id="recompute:distress",
        label="Recompute distress index",
        kind=RECOMPUTE_KIND,
        description="Recompute the motivated-seller distress index for every parcel.",
    ),
    JobSpec(
        id="recompute:vacancy",
        label="Recompute vacancy confidence",
        kind=RECOMPUTE_KIND,
        description="Recompute the vacancy-confidence cross-check for every vacant parcel.",
    ),
    JobSpec(
        id="recompute:assemblage",
        label="Recompute assemblage Top Plays",
        kind=RECOMPUTE_KIND,
        description="Recompute assemblage Top Plays for every vacant parcel.",
    ),
)


def ingest_job_id(market: str, dataset: str) -> str:
    return f"{INGEST_KIND}:{market}:{dataset}"


def _build_catalog() -> list[JobSpec]:
    ingest = [
        JobSpec(
            id=ingest_job_id(market, dataset),
            label=f"{market.upper()} · {dataset}",
            kind=INGEST_KIND,
            description=f"Ingest the {dataset} dataset for {market.upper()}.",
            market=market,
            dataset=dataset,
        )
        for (market, dataset) in sorted(INGEST_JOBS)
    ]
    return ingest + list(_RECOMPUTE_SPECS)


CATALOG: list[JobSpec] = _build_catalog()
CATALOG_BY_ID: dict[str, JobSpec] = {spec.id: spec for spec in CATALOG}
