"""A test that needs the database must say so, or CI never runs it.

CI splits the suite: the unit job runs `-m "not integration"` and the integration job runs
`-m integration`. A database test with no marker falls between them and is executed by
neither — it passes locally, where `make test` runs everything, and silently never runs in
CI. Three tests had been in that gap, one of them checking that anonymous callers cannot
read owner names.
"""

import ast
import pathlib

DB_FIXTURES = frozenset({"db_session", "db_connection", "migrated_database", "database_url"})
_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _module_is_marked(tree: ast.Module) -> bool:
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and any(getattr(target, "id", "") == "pytestmark" for target in node.targets)
            and "integration" in ast.unparse(node.value)
        ):
            return True
    return False


def unmarked_database_tests() -> list[str]:
    found: list[str] = []
    for path in sorted(_ROOT.rglob("test_*.py")):
        tree = ast.parse(path.read_text())
        module_marked = _module_is_marked(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            if not node.name.startswith("test_"):
                continue
            if not (DB_FIXTURES & {arg.arg for arg in node.args.args}):
                continue
            if module_marked or any(
                "integration" in ast.unparse(decorator) for decorator in node.decorator_list
            ):
                continue
            found.append(f"{path.relative_to(_ROOT)}::{node.name}")
    return found


def test_every_database_test_is_marked_integration() -> None:
    unmarked = unmarked_database_tests()
    assert not unmarked, (
        "These tests take a database fixture but carry no integration marker, so neither "
        "CI job runs them:\n  " + "\n  ".join(unmarked)
    )
