from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class HealthRollup(BaseModel):
    status: str
    red: int
    amber: int
    green: int


class CoverageStats(BaseModel):
    parcel_count: int | None
    geometry_pct: float | None
    verdict_pct: float | None
    vacant_count: int | None
    vacant_with_comp_pct: float | None
    computed_at: datetime | None


class SheriffCoverage(BaseModel):
    market_code: str
    total_listings: int
    with_opa: int
    without_opa: int
    unique_parcels: int
    reconciled: int
    unreconciled: int
    coverage_pct: float | None
    sample_unreconciled: list[str]
    checked_at: datetime


class FleetMarketRow(BaseModel):
    market_code: str
    name: str
    launch_status: str
    health: HealthRollup
    coverage: CoverageStats
    last_ingest_at: datetime | None
    zoning_standard_count: int


class FleetOverview(BaseModel):
    markets: list[FleetMarketRow]
    git_sha: str
    generated_at: datetime


class DatasetHealth(BaseModel):
    dataset: str
    cadence: str
    freshness: str
    reason: str
    ingest_status: str
    last_success_at: datetime | None
    last_attempt_at: datetime | None
    data_vintage: date | None = None
    vintage_reason: str | None = None
    row_count: int | None


class VerdictVersionCount(BaseModel):
    verdict_version: str | None
    count: int


class JobRunRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: str
    label: str
    kind: str
    market_code: str | None
    status: str
    started_at: datetime | None
    finished_at: datetime | None
    result_count: int | None
    error: str | None
    created_at: datetime


class MarketHealthDetail(BaseModel):
    market_code: str
    name: str
    launch_status: str
    coverage_note: str | None
    health: HealthRollup
    datasets: list[DatasetHealth]
    coverage: CoverageStats
    zoning_standard_count: int
    zoning_district_count: int
    verdict_versions: list[VerdictVersionCount]
    recent_jobs: list[JobRunRow]
    generated_at: datetime
