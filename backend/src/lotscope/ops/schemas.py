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
    row_count: int | None


class CapabilityNote(BaseModel):
    category: str
    state: str
    detail: str


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


class GateItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ordinal: int
    title: str
    status: str
    satisfied: bool
    qualifier: str | None
    threshold: str | None
    measured: str | None
    owner: str | None
    evidence: str | None
    spec_ref: str | None
    as_of: date | None


class GateSummary(BaseModel):
    gate_type: str
    satisfied: int
    total: int
    items: list[GateItem]


class MarketGates(BaseModel):
    market_code: str
    name: str
    launch_status: str
    gates: list[GateSummary]


class GateBoard(BaseModel):
    markets: list[MarketGates]
    generated_at: datetime


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
    capabilities: list[CapabilityNote]
    verdict_versions: list[VerdictVersionCount]
    gates: list[GateSummary]
    recent_jobs: list[JobRunRow]
    generated_at: datetime
