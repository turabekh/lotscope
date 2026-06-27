from lotscope.ai.prompts import SYSTEM_PROMPT, build_user_prompt
from lotscope.ai.schemas import RetrievedDocument


def _doc() -> RetrievedDocument:
    return RetrievedDocument(
        id=1,
        source="title14",
        section="14-701",
        title=None,
        content="RSA-5 minimum lot area is 1,440 sqft.",
        distance=0.1,
    )


def test_build_user_prompt_includes_question_facts_and_sources() -> None:
    prompt = build_user_prompt("Can I build a house?", "Parcel facts here", [_doc()])
    assert "Can I build a house?" in prompt
    assert "Parcel facts here" in prompt
    assert "[title14 14-701] RSA-5 minimum lot area is 1,440 sqft." in prompt


def test_build_user_prompt_handles_no_documents() -> None:
    prompt = build_user_prompt("Q", "facts", [])
    assert "no source documents retrieved" in prompt


def test_system_prompt_frames_informational_and_grounded() -> None:
    lowered = SYSTEM_PROMPT.lower()
    assert "informational" in lowered
    assert "context" in lowered
    assert "cite" in lowered
