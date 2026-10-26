# openapi-mcp: make your API usable by Claude, ChatGPT and Cursor

*A [Vínculo](https://github.com/diogofabri) demo (@vinculohq): the link between your product and AI agents.*

Your customers are starting to work through AI assistants. If your SaaS has a REST API, those assistants can already use it. They just need an **MCP server** (Model Context Protocol), the standard way Claude, ChatGPT, Cursor and other agents discover and call tools.

`openapi-mcp` reads your **OpenAPI 3.x** spec and serves **one MCP tool per API operation**, with input schemas, descriptions and auth generated from the spec. It is **read-only by default**, so you can put your API in front of an agent without handing it the keys to delete things.

```
┌───────────────┐   MCP (stdio / HTTP)   ┌─────────────────────────┐   HTTPS   ┌──────────────┐
│ Claude, Cursor│ ─────────────────────▶ │ openapi-mcp             │ ────────▶ │ Your REST API│
│ ChatGPT, ...  │ ◀───────────────────── │ spec → tools · policy · │ ◀──────── │              │
└───────────────┘   tools/list, call     │ auth · limits           │           └──────────────┘
                                         └─────────────────────────┘
```

## What it does

- **One tool per operation.** Names come from `operationId` (or `method_path`), descriptions from `summary`/`description`, and the input schema from path, query and header parameters plus the JSON request body.
- **`$ref` resolution.** Local refs are inlined (`#/components/schemas`, `parameters`, ...). Recursive schemas are cut safely.
- **Safe by default:**
  - only `GET`/`HEAD` are exposed; `POST/PUT/PATCH/DELETE` require `--allow-write`;
  - allowlist and denylist by `operationId`, tool name or `tag:<tag>`;
  - tools carry MCP `readOnlyHint` / `destructiveHint` annotations;
  - arguments are validated (missing or unknown arguments are rejected before any HTTP call);
  - timeouts, and large responses truncated with a notice so the agent's context isn't flooded.
- **Auth from the environment only:** Bearer token or API key (header or query). The secret is redacted from every tool output and never written to logs.
- **Transports:** stdio (desktop clients) and Streamable HTTP (remote or hosted).

## Quickstart

```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[test]"

# See which tools your spec produces
.venv/bin/python -m openapi_mcp inspect --spec examples/petstore.yaml
#   listPets   GET  /pets
#   getPet     GET  /pets/{petId}
#   get_stats  GET  /stats
#   3 tools (read-only)

# Serve over stdio (for Claude Desktop / Claude Code / Cursor)
export PETSTORE_TOKEN=...      # only if your API needs auth
.venv/bin/python -m openapi_mcp serve --config examples/petstore.config.yaml

# Or over Streamable HTTP
.venv/bin/python -m openapi_mcp serve --spec https://api.example.com/openapi.json --transport http --port 8000
```

### Config file (YAML or TOML)

```yaml
spec: openapi.yaml            # path or URL
base_url: https://api.example.com/v1
allow_write: false
include: ["tag:customers"]    # optional allowlist
exclude: ["deleteCustomer"]   # optional denylist
timeout: 15
max_response_chars: 20000
auth:
  type: bearer                # none | bearer | api_key
  env: EXAMPLE_API_TOKEN      # the secret stays in the environment
```

CLI flags (`--spec`, `--base-url`, `--allow-write`, `--include`, `--exclude`, `--auth-type`, `--auth-env`, `--auth-header`, `--auth-query`) override the file.

### Connect a client

**Claude Code**

```bash
claude mcp add petstore -e PETSTORE_TOKEN=... -- \
  /path/to/.venv/bin/python -m openapi_mcp serve --config /path/to/examples/petstore.config.yaml
```

**Claude Desktop** (`claude_desktop_config.json`)

```json
{
  "mcpServers": {
    "petstore": {
      "command": "/path/to/.venv/bin/python",
      "args": ["-m", "openapi_mcp", "serve", "--config", "/path/to/examples/petstore.config.yaml"],
      "env": { "PETSTORE_TOKEN": "..." }
    }
  }
}
```

Remote clients that speak Streamable HTTP connect to `http://<host>:<port>/mcp`.

## Security notes

- **Least privilege first.** Start read-only and allowlist the operations an agent actually needs. Enable writes only for the specific tags you trust.
- Use a **dedicated, scoped API token** for the agent, not an admin key.
- The HTTP transport binds to `127.0.0.1` with DNS-rebinding protection by default. For public deployment, put it behind TLS and your own authentication.
- Tool descriptions come from your spec. Treat the spec as part of the prompt the agent sees, and keep it accurate.

## Tests

```bash
.venv/bin/python -m pytest -q      # 20 tests, no external network
```

The tests cover tool generation from a local spec, schema validity, `$ref` and recursion handling, calls against a local fake API (path, query, header and body), the write block, Bearer and API-key injection and redaction, input validation, truncation, errors and timeouts, and **end-to-end over stdio** with the official MCP client (list and call).

## License

MIT. See [LICENSE](LICENSE).

## Limitations (v0.1)

- OpenAPI 3.x only (no Swagger 2.0). Local `$ref`s only.
- JSON request bodies only; `multipart/form-data` and file uploads are not mapped yet.
- Cookie parameters are ignored. OAuth2 flows are not handled: provide a token through the environment.
- Responses are returned as text, with no output schema.

## Need this for your product?

Vínculo builds production MCP servers and AI agents for SaaS teams: tool design, auth, rate limits, evals and deployment. → Contact via Upwork or @vinculohq.
