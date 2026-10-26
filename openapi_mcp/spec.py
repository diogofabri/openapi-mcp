"""Load an OpenAPI 3.x document (file or URL, YAML or JSON) and resolve local $refs."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import httpx
import yaml


class SpecError(ValueError):
    pass


def load_spec(source: str) -> dict[str, Any]:
    """Read a spec from a path or http(s) URL."""
    if source.startswith(("http://", "https://")):
        resp = httpx.get(source, timeout=30, follow_redirects=True)
        resp.raise_for_status()
        text = resp.text
    else:
        text = Path(source).read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError:
        doc = yaml.safe_load(text)
    if not isinstance(doc, dict) or not str(doc.get("openapi", "")).startswith("3."):
        raise SpecError("only OpenAPI 3.x documents are supported")
    return doc


def _lookup(doc: dict[str, Any], ref: str) -> Any:
    if not ref.startswith("#/"):
        raise SpecError(f"external $ref not supported: {ref}")
    node: Any = doc
    for part in ref[2:].split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        if not isinstance(node, dict) or part not in node:
            raise SpecError(f"unresolvable $ref: {ref}")
        node = node[part]
    return node


def resolve(node: Any, doc: dict[str, Any], _stack: tuple[str, ...] = ()) -> Any:
    """Return a copy of `node` with every local $ref inlined.

    Recursive schemas are cut at the second visit and replaced by a permissive
    object, so the result is always finite JSON.
    """
    if isinstance(node, dict):
        if "$ref" in node:
            ref = node["$ref"]
            if ref in _stack:
                return {"type": "object", "description": f"(recursive reference to {ref.rsplit('/', 1)[-1]})"}
            target = resolve(copy.deepcopy(_lookup(doc, ref)), doc, _stack + (ref,))
            siblings = {k: resolve(v, doc, _stack) for k, v in node.items() if k != "$ref"}
            return {**target, **siblings} if isinstance(target, dict) else target
        return {k: resolve(v, doc, _stack) for k, v in node.items()}
    if isinstance(node, list):
        return [resolve(v, doc, _stack) for v in node]
    return node
