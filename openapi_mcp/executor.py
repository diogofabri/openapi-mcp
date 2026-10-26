"""Execute a tool call as an HTTP request against the target API."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import httpx

from .config import Config
from .tools import ToolDef


class ToolInputError(ValueError):
    pass


@dataclass
class CallResult:
    status: int
    text: str
    is_error: bool


def _redact(text: str, secret: str | None) -> str:
    return text.replace(secret, "***") if secret else text


def build_request(tool: ToolDef, args: dict[str, Any], cfg: Config, base_url: str) -> httpx.Request:
    missing = [r for r in tool.input_schema.get("required", []) if r not in args]
    if missing:
        raise ToolInputError(f"missing required argument(s): {', '.join(missing)}")
    unknown = [a for a in args if a not in tool.bindings]
    if unknown:
        raise ToolInputError(f"unknown argument(s): {', '.join(unknown)}")

    path = tool.path
    query: dict[str, Any] = {}
    headers: dict[str, str] = {"Accept": "application/json"}
    body = None
    for arg, value in args.items():
        b = tool.bindings[arg]
        if b.location == "path":
            path = path.replace("{" + b.name + "}", quote(str(value), safe=""))
        elif b.location == "query":
            query[b.name] = value if not isinstance(value, bool) else str(value).lower()
        elif b.location == "header":
            headers[b.name] = str(value)
        elif b.location == "body":
            body = value

    secret = cfg.auth.secret()
    if cfg.auth.type == "bearer":
        headers["Authorization"] = f"Bearer {secret}"
    elif cfg.auth.type == "api_key":
        if cfg.auth.header:
            headers[cfg.auth.header] = secret
        elif cfg.auth.query:
            query[cfg.auth.query] = secret
        else:
            raise ValueError("auth.type api_key needs auth.header or auth.query")

    content = None
    if body is not None:
        headers["Content-Type"] = tool.body_content_type or "application/json"
        content = json.dumps(body).encode()
    return httpx.Request(tool.method.upper(), base_url.rstrip("/") + path, params=query, headers=headers, content=content)


async def call_tool(tool: ToolDef, args: dict[str, Any], cfg: Config, base_url: str,
                    transport: httpx.AsyncBaseTransport | None = None) -> CallResult:
    if tool.is_write and not cfg.allow_write:  # defence in depth: never execute writes without the flag
        return CallResult(0, f"{tool.name} is a write operation and the server runs read-only", True)
    secret = cfg.auth.secret()
    try:
        request = build_request(tool, args or {}, cfg, base_url)
    except (ToolInputError, ValueError) as e:
        return CallResult(0, str(e), True)
    try:
        async with httpx.AsyncClient(timeout=cfg.timeout, transport=transport) as client:
            resp = await client.send(request)
    except httpx.HTTPError as e:
        return CallResult(0, _redact(f"request failed: {type(e).__name__}: {e}", secret), True)

    text = resp.text
    if len(text) > cfg.max_response_chars:
        text = text[: cfg.max_response_chars] + f"\n\n[truncated: response had {len(resp.text)} characters, limit {cfg.max_response_chars}]"
    return CallResult(resp.status_code, _redact(f"HTTP {resp.status_code}\n{text}", secret), resp.status_code >= 400)
