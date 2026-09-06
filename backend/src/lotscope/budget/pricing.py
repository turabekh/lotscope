"""What a run costs, in dollars, as closely as we can know it without the invoice.

Anthropic bills per token at a published list price. We know the token counts exactly
— the API returns them and we already store them on `agent_run` — so the only estimate
here is the price, which is why every column and field this feeds is named
`usd_estimate` rather than `usd`. A model we do not have a price for is charged at the
most expensive rate we know, so an unpriced model cannot quietly cost more than the
ceiling allows.
"""

from decimal import ROUND_HALF_UP, Decimal

# USD per million tokens: (input, output). Anthropic list prices.
_PRICES_PER_MTOK: dict[str, tuple[str, str]] = {
    "claude-opus-5": ("15", "75"),
    "claude-sonnet-5": ("3", "15"),
    "claude-sonnet-4-6": ("3", "15"),
    "claude-haiku-4-5-20251001": ("1", "5"),
}

_FALLBACK = ("15", "75")
_MILLION = Decimal(1_000_000)
_CENTS = Decimal("0.0001")


def price_per_mtok(model: str) -> tuple[Decimal, Decimal]:
    inp, out = _PRICES_PER_MTOK.get(model, _FALLBACK)
    return Decimal(inp), Decimal(out)


def usd_estimate(model: str, input_tokens: int, output_tokens: int) -> Decimal:
    """The list-price cost of one run, rounded to a hundredth of a cent."""
    in_price, out_price = price_per_mtok(model)
    total = (Decimal(input_tokens) * in_price + Decimal(output_tokens) * out_price) / _MILLION
    return total.quantize(_CENTS, rounding=ROUND_HALF_UP)


def is_priced(model: str) -> bool:
    return model in _PRICES_PER_MTOK
