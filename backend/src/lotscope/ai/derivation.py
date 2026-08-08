import re
from dataclasses import dataclass, field
from typing import Any

PHILLYCODE_SOURCE = "phillycode"
DERIVATION_VERSION = "d2"

TABLE_KIND = "table"
SKIPPED_KINDS = frozenset({"figure"})
FOLDABLE_KINDS = frozenset({"subsection"})
FOLD_UNDER_CHARS = 120
NOTE_MINIMUM_CHARS = 60

_PROVENANCE_NOTE_RE = re.compile(
    r"(Amended|Added|Repealed|Renumbered|Deleted)[, ].{0,40}?(Bill No\.|\d{4} Ordinances)",
    re.IGNORECASE,
)
_RECENT_AMENDMENT_PREFIX = "Recent Amendment"
_TRAILING_PERIOD_RE = re.compile(r"\.\s*$")
_HEADING_MARKER_RE = re.compile(r"\s+\d{1,4}(?:\.\d{1,2})?\s*$")
_TITLE_ECHO_RE = re.compile(r"^Title\s+[\d.]+$", re.IGNORECASE)


@dataclass(frozen=True)
class SourceProvision:
    id: str
    cite: str
    kind: str
    title_number: str
    parent: str | None
    ordinal: int
    path: list[str]
    heading: str | None
    text: str | None
    source_version: str
    table_data: dict[str, Any] | None = None


@dataclass(frozen=True)
class DerivedDocument:
    provision_id: str
    cite: str
    kind: str
    title_number: str
    path: list[str]
    heading: str | None
    prefix: str
    body: str
    folded_provision_ids: list[str]
    source_version: str

    @property
    def content(self) -> str:
        return f"{self.prefix}\n\n{self.body}"


@dataclass
class DerivationReport:
    table_documents: int = 0
    skipped_continuations: int = 0
    skipped_figures: int = 0
    skipped_notes: int = 0
    skipped_containers: int = 0
    folded_leaves: int = 0
    documents: int = 0
    provisions_seen: int = 0
    unresolved_folds: list[str] = field(default_factory=list)

    @property
    def accounted(self) -> int:
        return (
            self.skipped_continuations
            + self.skipped_figures
            + self.skipped_notes
            + self.skipped_containers
            + self.folded_leaves
            + self.documents
        )

    def reconciles(self) -> bool:
        return self.accounted == self.provisions_seen


def is_provenance_note(text: str) -> bool:
    stripped = text.strip()
    if stripped.startswith(_RECENT_AMENDMENT_PREFIX):
        return True
    return bool(_PROVENANCE_NOTE_RE.search(stripped))


def clean_heading(heading: str | None) -> str | None:
    if heading is None:
        return None
    stripped = heading.strip()
    if _TITLE_ECHO_RE.match(stripped):
        return None
    stripped = _TRAILING_PERIOD_RE.sub("", _HEADING_MARKER_RE.sub("", stripped))
    return stripped or None


def build_prefix(provision: SourceProvision, ancestors: dict[str, SourceProvision]) -> str:
    parts = [f"Philadelphia Code, Title {provision.title_number}"]
    for token in provision.path[1:]:
        ancestor = ancestors.get(token)
        if ancestor is None:
            continue
        heading = clean_heading(ancestor.heading)
        parts.append(f"{ancestor.cite} ({heading})" if heading else ancestor.cite)
    parts.append(provision.cite)
    return " > ".join(parts)


def linearise_table(table: dict[str, Any]) -> str:
    def render(row: list[str | None]) -> str:
        return " | ".join((cell or "").strip() for cell in row).strip(" |")

    lines: list[str] = []
    caption = table.get("caption")
    if caption:
        lines.append(str(caption).strip())
    for row in list(table.get("header_rows") or []) + list(table.get("rows") or []):
        rendered = render(row)
        if rendered:
            lines.append(rendered)
    return "\n".join(lines)


def body_for(provision: SourceProvision, folded: list[SourceProvision]) -> str:
    if provision.kind == TABLE_KIND:
        return linearise_table(provision.table_data or {})
    pieces: list[str] = []
    heading = clean_heading(provision.heading)
    if heading:
        pieces.append(heading)
    if provision.text and provision.text.strip():
        pieces.append(provision.text.strip())
    for child in folded:
        fragment = (child.text or "").strip()
        if fragment:
            pieces.append(f"{child.cite} {fragment}")
    return "\n".join(pieces)


def _emits_document(provision: SourceProvision, is_leaf: bool, report: DerivationReport) -> bool:
    if provision.kind == TABLE_KIND:
        table = provision.table_data or {}
        if table.get("continuation_of") or not linearise_table(table):
            report.skipped_continuations += 1
            return False
        report.table_documents += 1
        return True
    if provision.kind in SKIPPED_KINDS:
        report.skipped_figures += 1
        return False
    text = (provision.text or "").strip()
    if provision.kind == "note" and (len(text) < NOTE_MINIMUM_CHARS or is_provenance_note(text)):
        report.skipped_notes += 1
        return False
    if provision.kind in FOLDABLE_KINDS and is_leaf and len(text) < FOLD_UNDER_CHARS:
        report.folded_leaves += 1
        return False
    if not is_leaf and not text and not clean_heading(provision.heading):
        report.skipped_containers += 1
        return False
    return True


def derive(provisions: list[SourceProvision]) -> tuple[list[DerivedDocument], DerivationReport]:
    report = DerivationReport(provisions_seen=len(provisions))
    by_id = {provision.id: provision for provision in provisions}
    children: dict[str, list[str]] = {}
    for provision in provisions:
        if provision.parent is not None:
            children.setdefault(provision.parent, []).append(provision.id)

    ordered = sorted(provisions, key=lambda item: item.ordinal)
    emitting = {
        provision.id: _emits_document(provision, provision.id not in children, report)
        for provision in ordered
    }

    folded_onto: dict[str, list[SourceProvision]] = {}
    for provision in ordered:
        if emitting[provision.id]:
            continue
        if provision.kind == TABLE_KIND or provision.kind in SKIPPED_KINDS:
            continue
        if provision.id in children:
            continue
        if provision.kind not in FOLDABLE_KINDS:
            continue
        host = provision.parent
        while host is not None and not emitting.get(host, False):
            host = by_id[host].parent if host in by_id else None
        if host is None:
            report.unresolved_folds.append(provision.id)
            continue
        folded_onto.setdefault(host, []).append(provision)

    documents: list[DerivedDocument] = []
    for provision in ordered:
        if not emitting[provision.id]:
            continue
        folded = folded_onto.get(provision.id, [])
        documents.append(
            DerivedDocument(
                provision_id=provision.id,
                cite=provision.cite,
                kind=provision.kind,
                title_number=provision.title_number,
                path=provision.path,
                heading=provision.heading,
                prefix=build_prefix(provision, by_id),
                body=body_for(provision, folded),
                folded_provision_ids=[child.id for child in folded],
                source_version=provision.source_version,
            )
        )
    report.documents = len(documents)
    return documents, report
