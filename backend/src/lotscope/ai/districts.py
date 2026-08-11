from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.provisions.service import find_mentioning
from lotscope.zoning.service import is_known_district

DIMENSIONAL_STANDARDS_CITE = "14-701"
USE_TABLES_CITE = "14-602"
GOVERNING_CITES = (DIMENSIONAL_STANDARDS_CITE, USE_TABLES_CITE)
SUPPLEMENT_LIMIT = 4


async def district_anchor_cites(
    session: AsyncSession,
    district_code: str,
    *,
    market_code: str,
    titles: list[str] | None = None,
    supplement_limit: int = SUPPLEMENT_LIMIT,
) -> list[str]:
    if not await is_known_district(session, district_code, market_code):
        return []

    cites = list(GOVERNING_CITES)
    supplements = await find_mentioning(
        session,
        market_code,
        [district_code],
        title_numbers=titles,
        limit=supplement_limit,
    )
    for provision in supplements:
        if provision.cite not in cites:
            cites.append(provision.cite)
    return cites
