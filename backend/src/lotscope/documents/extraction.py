from pydantic import ValidationError

from lotscope.ai.client import StructuredGenerator
from lotscope.ai.errors import GenerationError
from lotscope.documents.schemas import DeedExtraction

EXTRACTION_PROMPT_VERSION = "deed-extraction-v1"

EXTRACTION_SYSTEM_PROMPT = (
    "You extract recorded-deed restrictions for Philadelphia parcels.\n"
    "From the DEED TEXT provided, identify every explicit restriction, easement, covenant, "
    "condition, or access limitation that would constrain what can be built or done on the lot.\n"
    "Rules:\n"
    "- Use ONLY the deed text. Do not infer restrictions that are not written.\n"
    "- Quote or reference the clause each restriction comes from in the citation field.\n"
    "- If the text contains no restrictions, return has_restrictions=false and an empty list.\n"
    "- This is informational only and is never legal advice; set confidence honestly.\n"
    "Return your response using the provided structured tool."
)

_MAX_TEXT_CHARS = 12000


def build_extraction_prompt(deed_text: str) -> str:
    return f"DEED TEXT:\n{deed_text[:_MAX_TEXT_CHARS]}\n"


async def extract_restrictions(generator: StructuredGenerator, deed_text: str) -> DeedExtraction:
    raw = await generator.generate(
        system=EXTRACTION_SYSTEM_PROMPT,
        user=build_extraction_prompt(deed_text),
        schema=DeedExtraction,
    )
    try:
        return DeedExtraction.model_validate(raw)
    except ValidationError as error:
        raise GenerationError(f"The model returned an invalid deed extraction: {error}") from error
