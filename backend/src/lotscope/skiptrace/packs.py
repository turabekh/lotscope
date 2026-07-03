from dataclasses import dataclass

from lotscope.core.config import Settings

INVESTOR_MONTHLY_CREDITS = 100


@dataclass(frozen=True)
class CreditPack:
    key: str
    credits: int
    price_cents: int


CREDIT_PACKS: dict[str, CreditPack] = {
    "small": CreditPack("small", 25, 1250),
    "medium": CreditPack("medium", 100, 4000),
    "large": CreditPack("large", 500, 17500),
}


def pack_price_id(settings: Settings, pack_key: str) -> str | None:
    return {
        "small": settings.stripe_price_credits_25,
        "medium": settings.stripe_price_credits_100,
        "large": settings.stripe_price_credits_500,
    }.get(pack_key)
