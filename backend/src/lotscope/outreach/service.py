from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.distress.schemas import MailRecipient
from lotscope.distress.service import list_mail_recipients
from lotscope.outreach.schemas import MailMergeRequest
from lotscope.reports.mailer import Letter, render_letters_pdf

DEFAULT_MESSAGE = (
    "Dear {owner},\n\n"
    "I am a local real-estate investor interested in purchasing the property at "
    "{property_address} (parcel {parcel_number}). I am prepared to make a fair cash offer "
    "and can close quickly, with no agent commissions or repairs required on your part.\n\n"
    "If you have any interest in selling, I would welcome the chance to talk. Please reach me "
    "using the contact information above at your convenience.\n\n"
    "Thank you for your time and consideration."
)

LETTER_DISCLAIMER = (
    "This letter is an informational, good-faith expression of interest to purchase real "
    "property and is not an offer, contract, or solicitation of a regulated transaction. The "
    "named sender is solely responsible for this mailing and for compliance with applicable "
    "direct-mail, Fair Housing, and Do-Not-Mail requirements. Property and owner data is sourced "
    "from public City of Philadelphia records and provided as-is."
)


def merge_message(
    template: str, *, owner: str, property_address: str | None, parcel_number: str
) -> str:
    return (
        template.replace("{owner}", owner)
        .replace("{property_address}", property_address or "the property")
        .replace("{parcel_number}", parcel_number)
    )


def _letter_for(recipient: MailRecipient, template: str) -> Letter:
    body = merge_message(
        template,
        owner=recipient.owner,
        property_address=recipient.property_address,
        parcel_number=recipient.parcel_number,
    )
    return Letter(owner=recipient.owner, mailing_address=recipient.mailing_address, body=body)


async def render_letter_campaign(
    session: AsyncSession, request: MailMergeRequest, *, row_limit: int
) -> bytes | None:
    recipients = await list_mail_recipients(
        session,
        row_limit=row_limit,
        min_score=request.min_score,
        vacant_only=request.vacant_only,
        zip_code=request.zip_code,
    )
    if not recipients:
        return None

    template = request.message or DEFAULT_MESSAGE
    letters = [_letter_for(recipient, template) for recipient in recipients]
    return render_letters_pdf(
        sender_name=request.from_name,
        sender_contact=request.from_contact,
        letters=letters,
        generated_at=datetime.now(UTC),
        disclaimer=LETTER_DISCLAIMER,
    )
