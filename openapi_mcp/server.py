"""Build the MCP server (low-level API of the official `mcp` SDK) from a spec and a config."""
from __future__ import annotations

import logging
from typing import Any

import httpx
import mcp_types as types
from mcp.server.lowlevel import Server

from .config import Config
from .executor import call_tool
from .spec import load_spec
from .tools import ToolDef, build_tools

log = logging.getLogger("openapi_mcp")


def resolve_base_url(doc: dict[str, Any], cfg: Config) -> str:
    if cfg.base_url:
        return cfg.base_url
    servers = doc.get("servers") or []
    if servers and servers[0].get("url", "").startswith(("http://", "https://")):
        return servers[0]["url"]
    raise ValueError("no absolute server URL in the spec; set base_url in the config or --base-url")


def load_tools(cfg: Config) -> tuple[dict[str, Any], list[ToolDef]]:
    doc = load_spec(cfg.spec)
    return doc, cfg.select(build_tools(doc))


def build_server(cfg: Config, transport: httpx.AsyncBaseTransport | None = None) -> Server:
    doc, tools = load_tools(cfg)
    base_url = resolve_base_url(doc, cfg)
    cfg.auth.secret()  # fail fast if the auth env var is missing
    by_name = {t.name: t for t in tools}
    info = doc.get("info", {})
    log.info("serving %d tools from %s (%s)", len(tools), info.get("title", cfg.spec), "read+write" if cfg.allow_write else "read-only")

    async def on_list_tools(ctx, params) -> types.ListToolsResult:
        return types.ListToolsResult(tools=[
            types.Tool(
                name=t.name,
                description=t.description,
                input_schema=t.input_schema,
                annotations=types.ToolAnnotations(read_only_hint=not t.is_write, destructive_hint=t.method == "delete"),
            )
            for t in tools
        ])

    async def on_call_tool(ctx, params: types.CallToolRequestParams) -> types.CallToolResult:
        tool = by_name.get(params.name)
        if tool is None:
            return types.CallToolResult(content=[types.TextContent(type="text", text=f"unknown tool: {params.name}")], is_error=True)
        result = await call_tool(tool, dict(params.arguments or {}), cfg, base_url, transport)
        return types.CallToolResult(content=[types.TextContent(type="text", text=result.text)], is_error=result.is_error)

    return Server(
        cfg.server_name,
        version="0.1.0",
        instructions=f"Tools generated from the OpenAPI spec '{info.get('title', 'API')}'. Each tool is one API operation.",
        on_list_tools=on_list_tools,
        on_call_tool=on_call_tool,
    )


async def run_stdio(cfg: Config) -> None:
    from mcp.server.stdio import stdio_server

    server = build_server(cfg)
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


def run_http(cfg: Config, host: str, port: int) -> None:
    import uvicorn

    app = build_server(cfg).streamable_http_app(host=host)
    uvicorn.run(app, host=host, port=port, log_level="info")
