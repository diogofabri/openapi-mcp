"""Turn OpenAPI operations into MCP tool definitions (one tool per operation)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .spec import resolve

HTTP_METHODS = ("get", "head", "post", "put", "patch", "delete", "options")
READ_METHODS = {"get", "head", "options"}
MAX_NAME = 64


@dataclass
class ArgBinding:
    """Where a tool argument goes in the HTTP request."""
    location: str  # path | query | header | body
    name: str      # original parameter name


@dataclass
class ToolDef:
    name: str
    description: str
    method: str
    path: str
    input_schema: dict[str, Any]
    bindings: dict[str, ArgBinding] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    operation_id: str | None = None
    body_content_type: str | None = None

    @property
    def is_write(self) -> bool:
        return self.method not in READ_METHODS


def _slug(text: str) -> str:
    text = re.sub(r"[{}]", "", text)
    text = re.sub(r"[^A-Za-z0-9_-]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "op"


def _tool_name(method: str, path: str, operation_id: str | None) -> str:
    base = _slug(operation_id) if operation_id else _slug(f"{method}_{path}")
    return base[:MAX_NAME]


def _description(op: dict[str, Any], method: str, path: str) -> str:
    parts = [op.get("summary"), op.get("description")]
    text = "\n\n".join(p.strip() for p in parts if isinstance(p, str) and p.strip())
    return f"{text}\n\nHTTP {method.upper()} {path}".strip()


def _merge_params(path_item: dict[str, Any], op: dict[str, Any]) -> list[dict[str, Any]]:
    """Operation-level parameters override path-level ones with the same (name, in)."""
    merged: dict[tuple[str, str], dict[str, Any]] = {}
    for p in list(path_item.get("parameters", [])) + list(op.get("parameters", [])):
        merged[(p["name"], p["in"])] = p
    return list(merged.values())


def build_tool(doc: dict[str, Any], method: str, path: str, path_item: dict[str, Any], op: dict[str, Any]) -> ToolDef:
    path_item = resolve(path_item, doc)
    op = resolve(op, doc)
    properties: dict[str, Any] = {}
    required: list[str] = []
    bindings: dict[str, ArgBinding] = {}

    for p in _merge_params(path_item, op):
        loc = p["in"]
        if loc == "cookie":
            continue
        arg = p["name"] if p["name"] not in properties else f"{loc}_{p['name']}"
        arg = _slug(arg)
        schema = dict(p.get("schema") or {"type": "string"})
        if p.get("description"):
            schema.setdefault("description", p["description"])
        properties[arg] = schema
        bindings[arg] = ArgBinding(loc, p["name"])
        if p.get("required") or loc == "path":
            required.append(arg)

    body_type = None
    body = op.get("requestBody")
    if body:
        content = body.get("content", {})
        body_type = next((ct for ct in content if "json" in ct), next(iter(content), None))
        if body_type:
            schema = dict(content[body_type].get("schema") or {"type": "object"})
            if body.get("description"):
                schema.setdefault("description", body["description"])
            properties["body"] = schema
            bindings["body"] = ArgBinding("body", "body")
            if body.get("required"):
                required.append("body")

    input_schema: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        input_schema["required"] = required
    return ToolDef(
        name=_tool_name(method, path, op.get("operationId")),
        description=_description(op, method, path),
        method=method,
        path=path,
        input_schema=input_schema,
        bindings=bindings,
        tags=list(op.get("tags", [])),
        operation_id=op.get("operationId"),
        body_content_type=body_type,
    )


def build_tools(doc: dict[str, Any]) -> list[ToolDef]:
    tools: list[ToolDef] = []
    seen: dict[str, int] = {}
    for path, path_item in (doc.get("paths") or {}).items():
        for method in HTTP_METHODS:
            op = path_item.get(method)
            if not isinstance(op, dict) or op.get("deprecated"):
                continue
            tool = build_tool(doc, method, path, path_item, op)
            if tool.name in seen:  # duplicate operationIds or slug collisions
                seen[tool.name] += 1
                tool.name = f"{tool.name[:MAX_NAME - 4]}_{seen[tool.name]}"
            else:
                seen[tool.name] = 1
            tools.append(tool)
    return tools
