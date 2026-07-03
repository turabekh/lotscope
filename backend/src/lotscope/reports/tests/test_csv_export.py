from lotscope.reports.csv_export import EXPORT_DISCLAIMER, stream_csv


def test_stream_csv_writes_header_then_rows() -> None:
    lines = list(stream_csv(["a", "b"], [(1, 2), (3, 4)]))
    assert lines[0] == "a,b\r\n"
    assert lines[1] == "1,2\r\n"
    assert lines[2] == "3,4\r\n"


def test_stream_csv_quotes_commas_and_blanks_none() -> None:
    (line,) = list(stream_csv(["x"], [("a, b",)]))[1:]
    assert line == '"a, b"\r\n'
    row = list(stream_csv(["x", "y"], [(1, None)]))[1]
    assert row == "1,\r\n"


def test_stream_csv_appends_footer_after_blank_separator() -> None:
    lines = list(stream_csv(["a"], [(1,)], EXPORT_DISCLAIMER))
    assert lines[1] == "1\r\n"
    assert lines[2] == "\r\n"
    assert len(lines) == 2 + 1 + len(EXPORT_DISCLAIMER)
    assert "Fair Housing" in lines[-1]
