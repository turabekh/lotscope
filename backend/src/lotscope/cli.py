from argparse import ArgumentParser

from lotscope.agent.cli import build_parser as build_agent_parser
from lotscope.agent.cli import main as agent_main
from lotscope.buyers.cli import build_parser as build_buyers_parser
from lotscope.buyers.cli import main as buyers_main
from lotscope.corpus.cli import build_parser as build_corpus_parser
from lotscope.corpus.cli import main as corpus_main
from lotscope.data.cli import build_parser as build_data_parser
from lotscope.data.cli import main as data_main
from lotscope.notifications.cli import build_parser as build_email_parser
from lotscope.notifications.cli import main as email_main

_GROUPS = {
    "agent": (build_agent_parser, agent_main),
    "buyers": (build_buyers_parser, buyers_main),
    "corpus": (build_corpus_parser, corpus_main),
    "data": (build_data_parser, data_main),
    "email": (build_email_parser, email_main),
}


def main(argv: list[str] | None = None) -> None:
    import sys

    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] not in _GROUPS:
        parser = ArgumentParser(prog="lotscope")
        parser.add_argument("group", choices=sorted(_GROUPS), help="Command group.")
        parser.parse_args(args[:1])
        return
    _, group_main = _GROUPS[args[0]]
    group_main(args[1:])


if __name__ == "__main__":
    main()
