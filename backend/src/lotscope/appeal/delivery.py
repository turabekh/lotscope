from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.notifications.email import EmailAttachment, EmailSender
from lotscope.reports.appeal_packet import appeal_packet_filename
from lotscope.reports.service import build_appeal_packet


async def email_appeal_packet(
    session: AsyncSession,
    sender: EmailSender,
    *,
    to: str,
    parcel_number: str,
) -> bool:
    pdf = await build_appeal_packet(session, parcel_number)
    if pdf is None:
        return False
    await sender.send(
        to=to,
        subject="Your LotScope Assessment Review Packet",
        html=(
            f"<p>Your Assessment Review Packet for parcel {parcel_number} is attached as a PDF.</p>"
            "<p>It is informational only and is not tax or legal advice.</p>"
        ),
        text=(
            f"Your Assessment Review Packet for parcel {parcel_number} is attached. "
            "It is informational only and is not tax or legal advice."
        ),
        attachment=EmailAttachment(filename=appeal_packet_filename(parcel_number), content=pdf),
    )
    return True
