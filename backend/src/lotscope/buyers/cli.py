import asyncio
import csv
import json
import re
from argparse import ArgumentParser, Namespace
from pathlib import Path

from lotscope.buyers.derivation import REPEAT_MIN_PURCHASES, REPEAT_WINDOW_MONTHS, RepeatBuyer
from lotscope.buyers.repeat import load_repeat_buyers, provenance, top_grantees
from lotscope.core.config import get_settings
from lotscope.core.db import create_engine, create_session_factory
from lotscope.core.logging import configure_logging

_SINCE_RE = re.compile(r"^(\d+)\s*(m|mo|months?)$", re.IGNORECASE)

_CSV_COLUMNS = (
    "buyer_key",
    "display_name",
    "purchase_count",
    "total_consideration",
    "mailing_address",
    "mailing_address_sources",
    "owned_parcels",
    "parcels",
    "source",
    "source_url",
    "computed_at",
)


def parse_since(value: str) -> int:
    match = _SINCE_RE.match(value.strip())
    if match is None:
        raise ValueError(f"--since expects a month count like '24m', got {value!r}.")
    return int(match.group(1))


def _row(buyer: RepeatBuyer, meta: dict[str, object]) -> dict[str, object]:
    return {
        "buyer_key": buyer.buyer_key,
        "display_name": buyer.display_name,
        "purchase_count": buyer.purchase_count,
        "total_consideration": f"{buyer.total_consideration:.2f}",
        "mailing_address": buyer.mailing_address or "",
        "mailing_address_sources": buyer.mailing_address_sources,
        "owned_parcels": buyer.owned_parcels,
        "parcels": " ".join(p.parcel_number for p in buyer.purchases),
        "source": meta["source"],
        "source_url": meta["source_url"],
        "computed_at": meta["computed_at"],
    }


def _json_payload(buyers: list[RepeatBuyer], meta: dict[str, object]) -> dict[str, object]:
    return {
        "provenance": meta,
        "buyers": [
            {
                "buyer_key": buyer.buyer_key,
                "display_name": buyer.display_name,
                "purchase_count": buyer.purchase_count,
                "total_consideration": buyer.total_consideration,
                "mailing_address": buyer.mailing_address,
                "mailing_address_sources": buyer.mailing_address_sources,
                "owned_parcels": buyer.owned_parcels,
                "purchases": [
                    {
                        "parcel_number": p.parcel_number,
                        "address": p.address,
                        "sale_date": p.sale_date.isoformat(),
                        "sale_price": p.sale_price,
                    }
                    for p in buyer.purchases
                ],
            }
            for buyer in buyers
        ],
    }


async def _repeat(args: Namespace) -> int:
    settings = get_settings()
    configure_logging(settings)
    months = parse_since(args.since)
    factory = create_session_factory(create_engine(settings))

    async with factory() as session:
        buyers = await load_repeat_buyers(session, months=months, min_purchases=args.min)
        grantees = await top_grantees(session, months=months, limit=args.top) if args.top else []

    meta = provenance()
    meta["window_months"] = months
    meta["min_purchases"] = args.min

    if args.csv:
        with Path(args.csv).open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=_CSV_COLUMNS)
            writer.writeheader()
            for buyer in buyers:
                writer.writerow(_row(buyer, meta))
        print(f"csv:  {args.csv}  ({len(buyers)} buyers)")

    if args.json:
        Path(args.json).write_text(
            json.dumps(_json_payload(buyers, meta), indent=2), encoding="utf-8"
        )
        print(f"json: {args.json}  ({len(buyers)} buyers)")

    with_address = sum(1 for buyer in buyers if buyer.has_mailing_address)
    print(f"buyers with at least {args.min} purchases in {months} months: {len(buyers)}")
    print(f"with a usable mailing address: {with_address}")
    print(f"without one: {len(buyers) - with_address}")

    if grantees:
        print(f"\ntop {len(grantees)} grantees by deed count:")
        for entry in grantees:
            print(f"  {entry['deeds']:4d}  {entry['grantee']}")

    if not args.csv and not args.json:
        for buyer in buyers[:20]:
            address = buyer.mailing_address or "NO MAILING ADDRESS"
            print(f"  {buyer.purchase_count:3d}  {buyer.display_name[:40]:40s}  {address}")
    return 0


async def _letters(args: Namespace) -> int:
    from lotscope.reports.buyer_letters import build_letter

    settings = get_settings()
    configure_logging(settings)
    months = parse_since(args.since)
    factory = create_session_factory(create_engine(settings))
    out_dir = Path(args.out)

    async with factory() as session:
        buyers = await load_repeat_buyers(session, months=months, min_purchases=args.min)
        if args.limit:
            buyers = buyers[: args.limit]
        for buyer in buyers:
            path = await build_letter(
                session, settings, buyer, out_dir=out_dir, window_months=months
            )
            print(f"{buyer.purchase_count:3d}  {buyer.display_name[:38]:38s}  {path}")
        await session.commit()
    print(f"\n{len(buyers)} letters written to {out_dir}")
    return 0


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(prog="lotscope buyers")
    sub = parser.add_subparsers(dest="command", required=True)

    repeat = sub.add_parser("repeat", help="List repeat vacant-lot sheriff-sale buyers.")
    repeat.add_argument("--since", default=f"{REPEAT_WINDOW_MONTHS}m")
    repeat.add_argument("--min", type=int, default=REPEAT_MIN_PURCHASES)
    repeat.add_argument("--csv")
    repeat.add_argument("--json")
    repeat.add_argument("--top", type=int, default=0, help="Also print the top N grantees.")

    letters = sub.add_parser("letters", help="Write one letter PDF per repeat buyer.")
    letters.add_argument("--since", default=f"{REPEAT_WINDOW_MONTHS}m")
    letters.add_argument("--min", type=int, default=REPEAT_MIN_PURCHASES)
    letters.add_argument("--out", default="data/letters")
    letters.add_argument("--limit", type=int, default=0)
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    runner = _repeat if args.command == "repeat" else _letters
    raise SystemExit(asyncio.run(runner(args)))


if __name__ == "__main__":
    main()
