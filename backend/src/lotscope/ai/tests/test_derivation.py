from lotscope.ai.derivation import (
    SourceProvision,
    build_prefix,
    clean_heading,
    derive,
    is_provenance_note,
)


def _provision(
    provision_id: str,
    *,
    kind: str = "subsection",
    parent: str | None = None,
    ordinal: int = 0,
    path: list[str] | None = None,
    heading: str | None = None,
    text: str | None = None,
    cite: str | None = None,
) -> SourceProvision:
    return SourceProvision(
        id=provision_id,
        cite=cite or provision_id,
        kind=kind,
        title_number="14",
        parent=parent,
        ordinal=ordinal,
        path=path or ["14"],
        heading=heading,
        text=text,
        source_version="May 25, 2026",
    )


def _table_node(
    provision_id: str, *, parent: str, ordinal: int, table: dict[str, object]
) -> SourceProvision:
    return SourceProvision(
        id=provision_id,
        cite=provision_id,
        kind="table",
        title_number="14",
        parent=parent,
        ordinal=ordinal,
        path=["14"],
        heading=None,
        text="rows",
        source_version="May 25, 2026",
        table_data=table,
    )


LONG = (
    "A provision long enough that it stands as its own document rather than folding into "
    "a parent, which needs more than one hundred and twenty characters of body text."
)


def test_a_title_heading_that_only_echoes_its_number_is_dropped() -> None:
    assert clean_heading("Title 14") is None
    assert clean_heading("Dimensional Standards.") == "Dimensional Standards"
    assert clean_heading("PARKING AND LOADING") == "PARKING AND LOADING"
    assert clean_heading(None) is None


def test_provenance_notes_are_recognised_whatever_their_length() -> None:
    assert is_provenance_note("Amended, Bill No. 210740-A (approved July 27, 2022).")
    assert is_provenance_note("Added, 1982 Ordinances, p. 756.")
    assert is_provenance_note("Recent Amendment 355 Amended, 1992 Ordinances, p. 754")
    assert not is_provenance_note(
        "above the lowest level of fire department vehicle access: 1. Basements."
    )


def test_the_prefix_walks_resolvable_ancestors_and_skips_the_rest() -> None:
    ancestors = {
        "14": _provision("14", kind="title", heading="Title 14", path=["14"]),
        "14-800": _provision("14-800", kind="chapter", heading="PARKING AND LOADING"),
        "14-803": _provision("14-803", kind="section", heading="Motor Vehicle Parking Standards."),
    }
    leaf = _provision(
        "14-803(1)(b)",
        path=["14", "14-800", "14-803", "(1)", "(b)"],
        cite="14-803(1)(b)",
    )

    assert build_prefix(leaf, ancestors) == (
        "Philadelphia Code, Title 14 > 14-800 (PARKING AND LOADING) "
        "> 14-803 (Motor Vehicle Parking Standards) > 14-803(1)(b)"
    )


def test_an_unresolvable_path_token_is_skipped_rather_than_printed_bare() -> None:
    ancestors = {"4-F-11": _provision("4-F-11", kind="section", heading=None)}
    node = _provision("4-F-11#716", path=["4", "4-F-11", "#716"], cite="4-F-11#716")

    prefix = build_prefix(node, ancestors)

    assert "#716 >" not in prefix
    assert prefix.endswith("4-F-11 > 4-F-11#716")


def test_a_table_node_embeds_its_linearised_rows() -> None:
    documents, report = derive(
        [
            _provision("14-802", kind="section", heading="Ratios", text=LONG, ordinal=1),
            _table_node(
                "14-802#table1",
                parent="14-802",
                ordinal=2,
                table={
                    "caption": "Table 14-802-3: Required Parking in Industrial Districts",
                    "continuation_of": None,
                    "header_rows": [],
                    "rows": [
                        [None, "IRMX", "ICMX I-1", "I-2/3 I-P"],
                        ["Household Living", "3/10 units", "1/2 units", "1/2 units"],
                    ],
                },
            ),
        ]
    )

    assert report.table_documents == 1
    assert report.skipped_continuations == 0
    table = next(d for d in documents if d.kind == "table")
    assert table.body == (
        "Table 14-802-3: Required Parking in Industrial Districts\n"
        "IRMX | ICMX I-1 | I-2/3 I-P\n"
        "Household Living | 3/10 units | 1/2 units | 1/2 units"
    )
    assert report.reconciles()


def test_a_continuation_stub_never_becomes_its_own_document() -> None:
    documents, report = derive(
        [
            _provision("14-802", kind="section", heading="Ratios", text=LONG, ordinal=1),
            _table_node(
                "14-802#table1",
                parent="14-802",
                ordinal=2,
                table={
                    "caption": "T",
                    "continuation_of": None,
                    "header_rows": [],
                    "rows": [["a", "b"]],
                },
            ),
            _table_node(
                "14-802#table2",
                parent="14-802",
                ordinal=3,
                table={
                    "caption": "T",
                    "continuation_of": "14-802#table1",
                    "header_rows": [],
                    "rows": [],
                },
            ),
        ]
    )

    assert report.table_documents == 1
    assert report.skipped_continuations == 1
    assert "14-802#table2" not in {d.provision_id for d in documents}
    assert report.reconciles()


def test_a_table_carrying_no_rows_at_all_is_skipped_not_embedded_empty() -> None:
    _documents, report = derive(
        [
            _provision("14-802", kind="section", heading="Ratios", text=LONG, ordinal=1),
            _table_node(
                "14-802#table1",
                parent="14-802",
                ordinal=2,
                table={"caption": None, "continuation_of": None, "header_rows": [], "rows": []},
            ),
        ]
    )

    assert report.table_documents == 0
    assert report.skipped_continuations == 1
    assert report.reconciles()


def test_figures_and_provenance_notes_are_skipped() -> None:
    documents, report = derive(
        [
            _provision("14-900", kind="section", heading="Signs", text=LONG, ordinal=1),
            _provision(
                "14-900#figure1",
                kind="figure",
                parent="14-900",
                text="For printable PDF version of image, click HERE",
                ordinal=2,
            ),
            _provision(
                "14-900#note1",
                kind="note",
                parent="14-900",
                text="Amended, Bill No. 060447 (approved July 5, 2006), effective August 4, 2006.",
                ordinal=3,
            ),
        ]
    )

    assert report.skipped_figures == 1
    assert report.skipped_notes == 1
    assert [d.provision_id for d in documents] == ["14-900"]
    assert report.reconciles()


def test_a_substantive_note_still_earns_a_document() -> None:
    documents, report = derive(
        [
            _provision("4-F-11", kind="section", heading="Fire", text=LONG, ordinal=1),
            _provision(
                "4-F-11#716",
                kind="note",
                parent="4-F-11",
                ordinal=2,
                text="above the lowest level of fire department vehicle access: 1. Basements. "
                "2. The level of exit discharge. Exceptions: 1. Open parking structures.",
            ),
        ]
    )

    assert report.skipped_notes == 0
    assert {d.provision_id for d in documents} == {"4-F-11", "4-F-11#716"}


def test_a_degenerate_leaf_folds_into_its_nearest_emitting_ancestor() -> None:
    documents, report = derive(
        [
            _provision(
                "14-701", kind="section", heading="Dimensional Standards", text=LONG, ordinal=1
            ),
            _provision(
                "14-701(1)", parent="14-701", ordinal=2, text="Corner lots.", cite="14-701(1)"
            ),
        ]
    )

    assert report.folded_leaves == 1
    assert len(documents) == 1
    assert documents[0].folded_provision_ids == ["14-701(1)"]
    assert "14-701(1) Corner lots." in documents[0].body
    assert report.reconciles()


def test_folding_skips_past_an_ancestor_that_emits_nothing() -> None:
    documents, _report = derive(
        [
            _provision("14-701", kind="section", heading="Dimensional", text=LONG, ordinal=1),
            _provision("14-701(1)", parent="14-701", ordinal=2, text=""),
            _provision("14-701(1)(a)", parent="14-701(1)", ordinal=3, text="Short."),
        ]
    )

    assert len(documents) == 1
    assert documents[0].provision_id == "14-701"
    assert "14-701(1)(a) Short." in documents[0].body


def test_an_empty_section_still_gets_a_heading_only_document() -> None:
    documents, report = derive(
        [
            _provision("14-500", kind="chapter", heading="OVERLAYS", text="", ordinal=1),
            _provision(
                "14-501", kind="section", parent="14-500", heading="Purpose.", text="", ordinal=2
            ),
            _provision("14-501(1)", parent="14-501", ordinal=3, text=LONG),
        ]
    )

    assert report.skipped_containers == 0
    assert {d.provision_id for d in documents} == {"14-500", "14-501", "14-501(1)"}
    assert next(d for d in documents if d.provision_id == "14-501").body == "Purpose"


def test_a_container_with_neither_text_nor_heading_is_skipped() -> None:
    documents, report = derive(
        [
            _provision("14-600", kind="chapter", heading=None, text="", ordinal=1),
            _provision(
                "14-601", kind="section", parent="14-600", heading="Real", text=LONG, ordinal=2
            ),
        ]
    )

    assert report.skipped_containers == 1
    assert [d.provision_id for d in documents] == ["14-601"]
    assert report.reconciles()


def test_content_is_the_prefix_then_the_body() -> None:
    documents, _report = derive(
        [_provision("14-802", kind="section", heading="Ratios.", text=LONG, ordinal=1)]
    )

    content = documents[0].content
    assert content.startswith("Philadelphia Code, Title 14 > 14-802")
    assert content.endswith(LONG)
    assert "\n\n" in content


def test_every_provision_lands_in_exactly_one_bucket() -> None:
    provisions = [
        _provision("14", kind="title", heading="Title 14", text="", ordinal=1),
        _provision("14-800", kind="chapter", parent="14", heading="PARKING", text="", ordinal=2),
        _provision(
            "14-802", kind="section", parent="14-800", heading="Ratios", text=LONG, ordinal=3
        ),
        _provision("14-802(1)", parent="14-802", text="Short.", ordinal=4),
        _table_node(
            "14-802#table1",
            parent="14-802",
            ordinal=5,
            table={
                "caption": "T",
                "continuation_of": None,
                "header_rows": [],
                "rows": [["a", "b"]],
            },
        ),
        _provision("14-802#figure1", kind="figure", parent="14-802", text="click HERE", ordinal=6),
    ]

    _documents, report = derive(provisions)

    assert report.provisions_seen == 6
    assert report.reconciles()
    assert report.unresolved_folds == []


def test_batches_respect_both_the_item_and_character_budget() -> None:
    from lotscope.ai.phillycode import batch_documents

    documents, _report = derive(
        [
            _provision(
                f"14-80{index}", kind="section", heading=f"S{index}", text=LONG, ordinal=index
            )
            for index in range(1, 7)
        ]
    )

    by_chars = batch_documents(documents, max_items=96, max_chars=500)
    by_items = batch_documents(documents, max_items=2, max_chars=10**9)

    assert sum(len(batch) for batch in by_chars) == len(documents)
    assert sum(len(batch) for batch in by_items) == len(documents)
    assert all(len(batch) <= 2 for batch in by_items)
    assert all(len(batch) == 1 or sum(len(d.content) for d in batch) <= 500 for batch in by_chars)


def test_a_single_oversized_document_still_gets_its_own_batch() -> None:
    from lotscope.ai.phillycode import batch_documents

    documents, _report = derive(
        [_provision("14-802", kind="section", heading="Ratios", text=LONG * 20, ordinal=1)]
    )

    batches = batch_documents(documents, max_chars=10)

    assert len(batches) == 1
    assert len(batches[0]) == 1


def test_a_heading_loses_its_trailing_footnote_marker() -> None:
    assert clean_heading("Penalties. 9") == "Penalties"
    assert clean_heading("SERVICE UTILITIES 142") == "SERVICE UTILITIES"
    assert clean_heading("Ninth District Commercial Business Hour Restriction. 965.5") == (
        "Ninth District Commercial Business Hour Restriction"
    )
    assert clean_heading("Fixing and Regulating Rates and Charges. 2") == (
        "Fixing and Regulating Rates and Charges"
    )
    assert clean_heading("Title 14") is None
