"""Read one provision of the Philadelphia code.

The Lot page cites Title 14 wherever a dimensional rule decides something. A citation the
reader cannot open is an assertion, so this returns the text behind it.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.accounts.models import User
from lotscope.api.deps import get_current_user, get_session
from lotscope.core.errors import NotFoundError
from lotscope.core.market import MARKET_CODE
from lotscope.provisions.models import CodeProvision

router = APIRouter(prefix="/provisions", tags=["provisions"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]

_MAX_TEXT = 8000


class ProvisionRead(BaseModel):
    id: str
    cite: str
    heading: str | None
    text: str
    title_number: str
    source_url: str


@router.get("/{provision_id:path}", response_model=ProvisionRead)
async def read_provision(
    provision_id: str, session: SessionDep, user: CurrentUserDep
) -> ProvisionRead:
    provision = (
        await session.execute(
            select(CodeProvision).where(
                CodeProvision.market_code == MARKET_CODE, CodeProvision.id == provision_id
            )
        )
    ).scalar_one_or_none()
    if provision is None:
        raise NotFoundError(f"Provision {provision_id!r} is not in the corpus.")

    body = (provision.text or provision.raw_text or "").strip()
    return ProvisionRead(
        id=provision.id,
        cite=provision.cite,
        heading=provision.heading,
        # A provision with no stored text is a gap in the corpus, and saying so beats an
        # empty popover that looks like the code has nothing to say.
        text=body[:_MAX_TEXT] or "The corpus holds this citation but not its text.",
        title_number=provision.title_number,
        source_url=(
            f"https://codelibrary.amlegal.com/codes/philadelphia/latest/search?q={provision.cite}"
        ),
    )
