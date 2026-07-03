from collections.abc import Sequence

from lotscope.ai.schemas import RetrievedDocument

PROMPT_VERSION = "ask-the-parcel-v1"

SYSTEM_PROMPT = (
    "You are LotScope's parcel assistant for Philadelphia real estate.\n"
    "Answer the user's question about the specific parcel using ONLY the CONTEXT provided.\n"
    "Rules:\n"
    "- Ground every statement in the CONTEXT. If the answer is not supported by the CONTEXT, "
    "say you do not have enough information.\n"
    "- Cite the source and section for each fact you rely on "
    "(for example, Title 14, section 14-701).\n"
    "- This is informational only and is never legal, financial, or real-estate advice.\n"
    "- Set a confidence level that reflects how well the CONTEXT supports your answer.\n"
    "Return your response using the provided structured tool."
)


SUMMARY_PROMPT_VERSION = "parcel-summary-v1"

SUMMARY_SYSTEM_PROMPT = (
    "You are LotScope's parcel analyst for Philadelphia real estate.\n"
    "Write ONE short paragraph (3-5 sentences) that reads like a savvy investor's plain-English "
    "take on the parcel, using ONLY the FACTS provided.\n"
    "Rules:\n"
    "- Use only the FACTS. Do NOT introduce zoning, value, legal, or market claims that are not "
    "in the FACTS. If a fact is missing, omit it rather than guessing.\n"
    "- Be concrete and specific (use the numbers given), neutral, and non-promotional.\n"
    "- This is informational only and is never legal, financial, or real-estate advice.\n"
    "- Set confidence to reflect how complete the FACTS are.\n"
    "Return your response using the provided structured tool."
)


def build_summary_prompt(parcel_facts: str) -> str:
    return f"FACTS:\n{parcel_facts}\n"


def build_user_prompt(
    question: str, parcel_facts: str, documents: Sequence[RetrievedDocument]
) -> str:
    if documents:
        document_lines = "\n".join(
            f"[{f'{doc.source} {doc.section}'.strip()}] {doc.content}" for doc in documents
        )
    else:
        document_lines = "(no source documents retrieved)"
    return (
        f"QUESTION:\n{question}\n\n"
        f"CONTEXT - PARCEL FACTS:\n{parcel_facts}\n\n"
        f"CONTEXT - SOURCE DOCUMENTS:\n{document_lines}\n"
    )
