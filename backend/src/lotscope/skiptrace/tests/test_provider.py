from lotscope.core.config import Settings
from lotscope.skiptrace.provider import (
    BatchDataSkipTraceProvider,
    NullSkipTraceProvider,
    get_skiptrace_provider,
    parse_batchdata_contacts,
)


def _settings(**overrides: object) -> Settings:
    return Settings(_env_file=None, **overrides)  # type: ignore[arg-type]


def test_get_provider_null() -> None:
    provider = get_skiptrace_provider(_settings(skiptrace_provider="null"))
    assert isinstance(provider, NullSkipTraceProvider)


def test_get_provider_batchdata_requires_key() -> None:
    assert get_skiptrace_provider(_settings(skiptrace_provider="batchdata")) is None
    provider = get_skiptrace_provider(
        _settings(skiptrace_provider="batchdata", skiptrace_api_key="sk_test")
    )
    assert isinstance(provider, BatchDataSkipTraceProvider)


def test_get_provider_unconfigured_is_none() -> None:
    assert get_skiptrace_provider(_settings()) is None


def test_parse_batchdata_extracts_and_dedupes() -> None:
    payload = {
        "results": {
            "persons": [
                {
                    "phoneNumbers": [{"number": "215-555-0100"}, {"number": "215-555-0100"}],
                    "emails": [{"email": "jane@example.com"}],
                },
                {"phoneNumbers": [{"number": "267-555-0199"}], "emails": []},
            ]
        }
    }
    contacts = parse_batchdata_contacts(payload)
    assert contacts.phones == ["215-555-0100", "267-555-0199"]
    assert contacts.emails == ["jane@example.com"]


def test_parse_batchdata_empty_on_no_persons() -> None:
    assert parse_batchdata_contacts({"results": {"persons": []}}).phones == []
    assert parse_batchdata_contacts({}).emails == []
