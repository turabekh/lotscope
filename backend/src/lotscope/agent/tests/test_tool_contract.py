"""Every literal value a tool description names must be a value its schema accepts.

This exists because of a real bug: add_to_pipeline's description told the model to use
stage='watching', which DealCreate rejects. The description is a prompt — the model believes
it — so a description that names an impossible value is an instruction to fail.
"""

import re
from typing import Any, Literal, Union, get_args, get_origin

import pytest
from pydantic import BaseModel, ValidationError

from lotscope.agent.tools import REGISTRY

# 'lead', "under_contract", `sale_status` — the shapes a description uses to name a value.
_QUOTED = re.compile(r"""['"`]([A-Za-z][A-Za-z0-9_.:-]{1,40})['"`]""")


def _literal_options(annotation: Any) -> set[str]:
    """Every string a field will accept as a literal, including through unions and lists."""
    origin = get_origin(annotation)
    if origin is Literal:
        return {value for value in get_args(annotation) if isinstance(value, str)}
    if origin in (Union, list, set, tuple) or origin is not None:
        found: set[str] = set()
        for argument in get_args(annotation):
            found |= _literal_options(argument)
        return found
    return set()


def literal_vocabulary(model: type[BaseModel]) -> set[str]:
    vocabulary: set[str] = set()
    for field in model.model_fields.values():
        vocabulary |= _literal_options(field.annotation)
    return vocabulary


def field_names(model: type[BaseModel]) -> set[str]:
    return set(model.model_fields)


def _placeholder(annotation: Any) -> Any:
    """Something the annotation will plausibly accept, so other fields do not fail first."""
    options = _literal_options(annotation)
    if options:
        return next(iter(sorted(options)))
    args = [a for a in get_args(annotation) if a is not type(None)]
    base = get_origin(annotation) or annotation
    if base in (Union,) and args:
        return _placeholder(args[0])
    if base in (list, set, tuple):
        return []
    if base is bool:
        return True
    if base is int:
        return 1
    if base is float:
        return 1.0
    return "phl:191357500"


def _fill_required(model: type[BaseModel], *, skip: str) -> dict[str, Any]:
    return {
        name: _placeholder(field.annotation)
        for name, field in model.model_fields.items()
        if name != skip and field.is_required()
    }


@pytest.mark.parametrize("name", REGISTRY.names())
def test_description_names_only_values_the_schema_accepts(name: str) -> None:
    registered = REGISTRY.get(name)
    assert registered is not None

    model = registered.input_model
    vocabulary = literal_vocabulary(model)
    if not vocabulary:
        # No constrained field, so no value the description could name wrongly.
        return

    # Tokens that look like a constrained value: they collide with the vocabulary's own
    # namespace. A quoted token that is a field name, a tool name or an example address is
    # not claiming to be an enum member.
    allowed = vocabulary | field_names(model) | set(REGISTRY.names())
    quoted = {match.group(1) for match in _QUOTED.finditer(registered.description)}

    lowered = {value.casefold() for value in vocabulary}
    offenders = sorted(
        token
        for token in quoted - allowed
        # Only judge tokens shaped like an enum member: a bare lowercase identifier.
        if re.fullmatch(r"[a-z][a-z0-9_]*", token) and token.casefold() not in lowered
    )
    assert not offenders, (
        f"{name}'s description names {offenders}, which its input schema does not accept. "
        f"Accepted literals: {sorted(vocabulary)}."
    )


@pytest.mark.parametrize("name", REGISTRY.names())
def test_every_literal_value_actually_validates(name: str) -> None:
    """A Literal member must survive the model's own validators, not just its annotation."""
    registered = REGISTRY.get(name)
    assert registered is not None
    model = registered.input_model

    for field_name, field in model.model_fields.items():
        for option in _literal_options(field.annotation):
            payload = {**_fill_required(model, skip=field_name), field_name: option}
            try:
                model.model_validate(payload)
            except ValidationError as cause:
                # Only the field under test is on trial; a placeholder that another field
                # dislikes is the harness's problem, not the tool's.
                blamed = {str(error["loc"][0]) for error in cause.errors() if error["loc"]}
                if field_name in blamed:
                    pytest.fail(
                        f"{name}.{field_name}={option!r} is declared valid but rejected: {cause}"
                    )
