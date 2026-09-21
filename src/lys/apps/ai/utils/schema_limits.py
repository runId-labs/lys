"""
Detection of string fields cut by a JSON-schema ``maxLength``.

Providers that enforce the response schema at decoding time (constrained decoding)
stop a string the moment it reaches its ``maxLength``: the result is still valid JSON
and passes validation, but the text is cut mid-word. A value whose length reaches its
declared ``maxLength`` is therefore treated as truncated, not as a legitimate answer.
"""

from functools import lru_cache
from typing import Any, Dict, List, Type

from pydantic import BaseModel


@lru_cache(maxsize=None)
def _json_schema(model: Type[BaseModel]) -> Dict[str, Any]:
    """JSON schema of a model, computed once per class (the result is never mutated)."""
    return model.model_json_schema()


def find_fields_at_max_length(instance: BaseModel) -> List[str]:
    """
    Return the paths of the string fields whose length reaches their schema ``maxLength``.

    The walk follows the JSON schema the provider received (``$ref``, ``anyOf`` / ``oneOf``,
    arrays, ``dict`` values), so a bound declared through ``json_schema_extra`` is honoured
    as well as one declared through ``max_length``. Tuples (``prefixItems``) and ``allOf``
    are not walked. Union branches that share a field without a
    ``Literal`` to tell them apart are all applied to the value.

    Args:
        instance: Validated structured response.

    Returns:
        Dotted paths of the offending fields (list indexes in brackets), empty when none.
    """
    schema = _json_schema(type(instance))
    hits: List[str] = []
    _walk(instance.model_dump(mode="json", by_alias=True), schema, schema.get("$defs", {}), "", hits)
    # An anyOf / oneOf may list several object branches: report each path once.
    return list(dict.fromkeys(hits))


def _branch_matches(value: Any, branch: Dict[str, Any], defs: Dict[str, Any]) -> bool:
    """
    Tell whether an object value can belong to a union branch, judging by its constants.

    A ``Literal`` field (``const`` / ``enum``, typically the discriminator) that disagrees with
    the value rules the branch out; without it, two branches declaring the same field with
    different bounds would both be applied to the value. Non-object values and branches
    without constants always match.
    """
    if not isinstance(value, dict):
        return True
    ref = branch.get("$ref")
    if ref:
        branch = defs.get(ref.rsplit("/", 1)[-1], {})
    for key, prop in branch.get("properties", {}).items():
        if key not in value:
            continue
        if "const" in prop and value[key] != prop["const"]:
            return False
        if "enum" in prop and value[key] not in prop["enum"]:
            return False
    return True


def _walk(value: Any, node: Dict[str, Any], defs: Dict[str, Any], path: str, hits: List[str]) -> None:
    ref = node.get("$ref")
    if ref:
        node = defs.get(ref.rsplit("/", 1)[-1], {})

    if isinstance(value, str):
        # The bound may sit on the node itself or on a string branch of an anyOf.
        bounds = [node.get("maxLength")] + [
            branch.get("maxLength") for branch in node.get("anyOf", []) if branch.get("type") == "string"
        ]
        max_length = min((bound for bound in bounds if bound), default=None)
        if max_length is not None and len(value) >= max_length:
            hits.append(path)
        return

    for branch in node.get("anyOf", []) + node.get("oneOf", []):
        if _branch_matches(value, branch, defs):
            _walk(value, branch, defs, path, hits)

    if isinstance(value, dict):
        properties = node.get("properties", {})
        additional = node.get("additionalProperties")
        for key, item in value.items():
            child_path = f"{path}.{key}" if path else key
            if key in properties:
                _walk(item, properties[key], defs, child_path, hits)
            elif isinstance(additional, dict):
                _walk(item, additional, defs, child_path, hits)
    elif isinstance(value, list):
        items = node.get("items")
        if isinstance(items, dict):
            for index, item in enumerate(value):
                _walk(item, items, defs, f"{path}[{index}]", hits)
