import asyncio
from argparse import ArgumentParser, Namespace

from redis.asyncio import Redis
from sqlalchemy import text

import lotscope.models  # noqa: F401  (registers every table for the ORM)
from lotscope.agent.client import AnthropicToolClient
from lotscope.agent.evals import baseline as baseline_store
from lotscope.agent.evals.runner import TaskResult, estimate_cost, run_suite
from lotscope.core.config import get_settings
from lotscope.core.db import create_engine, create_session_factory
from lotscope.core.logging import configure_logging

DEFAULT_SPEND_CAP = 2.00
EVAL_USER_EMAIL = "agent-eval@lotscope.test"


def _mark(result: TaskResult) -> str:
    # An error is not a failure. Reporting an outage as a behaviour regression is how a
    # broken run gets mistaken for a broken model.
    if result.errored:
        return "ERROR"
    return "PASS" if result.passed else "FAIL"


def _print_table(results: list[TaskResult]) -> None:
    width = max(len(result.task_id) for result in results)
    print(f"\n{'task':<{width}}  {'result':<7} {'tools':<5} {'in':>7} {'out':>6} {'ms':>7}")
    print("-" * (width + 38))
    for result in results:
        if result.skipped:
            print(f"{result.task_id:<{width}}  {'SKIP':<7} {'-':<5} {'-':>7} {'-':>6} {'-':>7}")
            continue
        print(
            f"{result.task_id:<{width}}  {_mark(result):<7} "
            f"{len(result.tools_called):<5} {result.input_tokens:>7} "
            f"{result.output_tokens:>6} {result.duration_ms:>7}"
        )

    print("\nassertions:")
    for result in results:
        if result.skipped:
            print(f"  {result.task_id}: skipped — {result.error}")
            continue
        if result.error:
            print(f"  {result.task_id}: ERROR {result.error}")
        for assertion in result.assertions:
            flag = "ok  " if assertion.passed else "FAIL"
            print(f"  {flag} {result.task_id}: {assertion.kind}={assertion.value!r}")
            if not assertion.passed and assertion.why:
                print(f"        why it matters: {assertion.why}")
            if not assertion.passed:
                print(f"        tools called: {result.tools_called}")
        if any(not assertion.passed for assertion in result.assertions):
            # Without the answer in front of you, a failing assertion is a guess about
            # whether the model was wrong or the assertion was.
            print(f"        answer: {result.answer.strip()}")

    ran = [r for r in results if not r.skipped]
    graded = [r for r in ran if not r.errored]
    errored = [r for r in ran if r.errored]
    total_in = sum(r.input_tokens for r in ran)
    total_out = sum(r.output_tokens for r in ran)
    passed = sum(1 for r in graded if r.passed)
    checks = [a for r in graded for a in r.assertions]
    print(
        f"\ntasks {passed}/{len(graded)} passed"
        f"   assertions {sum(1 for a in checks if a.passed)}/{len(checks)} passed"
        f"   skipped {len(results) - len(ran)}"
        f"   errored {len(errored)}"
    )
    if errored:
        print(
            f"{len(errored)} task(s) could not run and were not graded: "
            f"{', '.join(r.task_id for r in errored)}"
        )
    print(
        f"tokens in {total_in:,} out {total_out:,}"
        f"   estimated spend ${estimate_cost(total_in, total_out):.2f}"
    )


async def _eval(args: Namespace) -> int:
    settings = get_settings()
    configure_logging(settings)
    if not settings.anthropic_api_key:
        print("ANTHROPIC_API_KEY is not configured; nothing was run.")
        return 1

    factory = create_session_factory(create_engine(settings))
    async with factory() as session:
        user_id = await session.scalar(
            text("SELECT id FROM app_user WHERE email = :e"), {"e": EVAL_USER_EMAIL}
        )
        if user_id is None:
            await session.execute(
                text(
                    "INSERT INTO app_user (email, hashed_password, role, tier, is_active, "
                    "email_verified_at) VALUES (:e, 'x', 'user', 'user', true, now())"
                ),
                {"e": EVAL_USER_EMAIL},
            )
            await session.commit()
            user_id = await session.scalar(
                text("SELECT id FROM app_user WHERE email = :e"), {"e": EVAL_USER_EMAIL}
            )

    model = args.model or settings.analyst_model
    print(f"model {model}   spend cap ${args.spend_cap:.2f}   eval user {user_id}")

    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        results = await run_suite(
            factory,
            AnthropicToolClient(settings),
            user_id=int(user_id),
            model=model,
            spend_cap_usd=args.spend_cap,
            only=args.only,
            first=args.first,
            redis=redis,
            allow_mutation=not args.no_mutate,
        )
    finally:
        await redis.aclose()
    _print_table(results)
    ran = [r for r in results if not r.skipped]

    graded = [r for r in ran if not r.errored]
    if graded:
        current = baseline_store.snapshot(graded, model=model)
        previous = baseline_store.read()
        print("\n" + baseline_store.report(previous, current))
        if args.record:
            try:
                written = baseline_store.write(ran, model=model)
                print(f"baseline written to {written}")
            except baseline_store.BrokenRunError as cause:
                print(f"baseline NOT written: {cause}")
                return 1

    if any(r.errored for r in ran):
        return 1
    return 0 if graded and all(r.passed for r in graded) else 1


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(prog="lotscope agent")
    sub = parser.add_subparsers(dest="command", required=True)
    evaluate = sub.add_parser("eval", help="Run the analyst eval suite against the real model.")
    evaluate.add_argument("--spend-cap", type=float, default=DEFAULT_SPEND_CAP)
    evaluate.add_argument("--model", default=None)
    evaluate.add_argument("--only", default=None, help="Run one task by id.")
    evaluate.add_argument(
        "--first",
        type=int,
        default=None,
        help="Run only the first N tasks, for a cheap subset in CI.",
    )
    evaluate.add_argument(
        "--no-mutate",
        action="store_true",
        help="Skip tasks that edit stored data. Required when pointing at production.",
    )
    evaluate.add_argument(
        "--record",
        action="store_true",
        help="Overwrite evals/baseline.json with this run.",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    raise SystemExit(asyncio.run(_eval(args)))


if __name__ == "__main__":
    main()
