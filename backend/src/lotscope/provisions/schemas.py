from typing import Any

from pydantic import BaseModel, ConfigDict, Field

REQUIRED_GATES: tuple[str, ...] = (
    "1_toc_reconciliation",
    "2_coverage",
    "3_numbering_sanity",
)


class Provision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    cite: str
    doc: str
    kind: str
    parent: str | None
    order: int
    path: list[str]
    heading: str | None
    text: str | None
    raw_text: str | None
    history: str | None
    refs: list[str]
    note_refs: list[str]
    pages: list[int] = Field(min_length=2, max_length=2)
    table: dict[str, Any] | None
    source_file: str
    source_version: str


class TitleGate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    passed: bool
    value: str
    detail: str | None = None


class TitleAnomaly(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str
    page: int | None
    text: str
    detail: str


class TocException(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title_number: str
    cite: str
    bill_number: str
    approved_date: str
    footnotes: list[str]
    toc_page: int
    body_page: int
    reason: str


class TitleQa(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title_number: str
    passed: bool
    gates: list[TitleGate]
    anomalies: list[TitleAnomaly] = Field(default_factory=list)
    exceptions_applied: list[TocException] = Field(default_factory=list)

    def failing_gate(self) -> TitleGate | None:
        by_name = {gate.name: gate for gate in self.gates}
        for name in REQUIRED_GATES:
            gate = by_name.get(name)
            if gate is None:
                return TitleGate(name=name, passed=False, value="gate absent from the QA file")
            if not gate.passed:
                return gate
        return None


class SummaryTitleQa(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    passed: bool
    gates: dict[str, bool]
    gate_values: dict[str, str]
    anomalies: dict[str, int] = Field(default_factory=dict)
    error: str | None = None


class QaSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total: int
    passed_count: int
    failed: list[str]
    titles: list[SummaryTitleQa]

    def title_numbers(self) -> list[str]:
        return [entry.title for entry in self.titles]


class TitleLoadResult(BaseModel):
    title_number: str
    loaded: bool
    provision_count: int = 0
    pruned_count: int = 0
    exceptions: list[TocException] = Field(default_factory=list)
    excluded_gate: str | None = None
    excluded_value: str | None = None
    excluded_detail: str | None = None


class LoadReport(BaseModel):
    source_version: str | None
    market_code: str
    titles_expected: int
    results: list[TitleLoadResult]

    @property
    def loaded_titles(self) -> list[str]:
        return [result.title_number for result in self.results if result.loaded]

    @property
    def excluded_titles(self) -> list[str]:
        return [result.title_number for result in self.results if not result.loaded]

    @property
    def total_provisions(self) -> int:
        return sum(result.provision_count for result in self.results)
