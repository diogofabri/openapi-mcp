"""CLI: `python -m openapi_mcp serve|inspect`."""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys

from .config import AuthConfig, Config
from .server import load_tools, run_http, run_stdio


def _config(args: argparse.Namespace) -> Config:
    cfg = Config.from_file(args.config) if args.config else Config()
    if args.spec:
        cfg.spec = args.spec
    if args.base_url:
        cfg.base_url = args.base_url
    if args.allow_write:
        cfg.allow_write = True
    if args.include:
        cfg.include = args.include
    if args.exclude:
        cfg.exclude = args.exclude
    if args.auth_type:
        cfg.auth = AuthConfig(type=args.auth_type, env=args.auth_env, header=args.auth_header, query=args.auth_query)
    if not cfg.spec:
        sys.exit("error: pass --spec or a config file with `spec:`")
    return cfg


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="openapi_mcp", description="Expose any OpenAPI 3.x API as MCP tools.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("serve", "inspect"):
        p = sub.add_parser(name)
        p.add_argument("--config", help="YAML or TOML config file")
        p.add_argument("--spec", help="path or URL of the OpenAPI document")
        p.add_argument("--base-url", help="override the API base URL")
        p.add_argument("--allow-write", action="store_true", help="also expose POST/PUT/PATCH/DELETE operations")
        p.add_argument("--include", nargs="*", help="allowlist: operationIds, tool names or tag:<tag>")
        p.add_argument("--exclude", nargs="*", help="denylist: operationIds, tool names or tag:<tag>")
        p.add_argument("--auth-type", choices=["none", "bearer", "api_key"])
        p.add_argument("--auth-env", help="env var holding the secret")
        p.add_argument("--auth-header", help="header for api_key auth")
        p.add_argument("--auth-query", help="query parameter for api_key auth")
        if name == "serve":
            p.add_argument("--transport", choices=["stdio", "http"], default="stdio")
            p.add_argument("--host", default="127.0.0.1")
            p.add_argument("--port", type=int, default=8000)
        else:
            p.add_argument("--json", action="store_true", help="print full tool definitions as JSON")
    args = ap.parse_args(argv)
    # logs go to stderr: stdout belongs to the MCP stdio transport
    logging.basicConfig(level=logging.INFO, stream=sys.stderr, format="%(levelname)s %(name)s: %(message)s")
    cfg = _config(args)

    if args.cmd == "inspect":
        _, tools = load_tools(cfg)
        if args.json:
            print(json.dumps([{"name": t.name, "method": t.method.upper(), "path": t.path,
                               "description": t.description, "input_schema": t.input_schema} for t in tools], indent=2))
        else:
            for t in tools:
                print(f"{t.name:<32} {t.method.upper():<7} {t.path}{'  [write]' if t.is_write else ''}")
            print(f"\n{len(tools)} tools ({'read+write' if cfg.allow_write else 'read-only'})")
    elif args.transport == "stdio":
        asyncio.run(run_stdio(cfg))
    else:
        run_http(cfg, args.host, args.port)


if __name__ == "__main__":
    main()
