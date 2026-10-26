# Video script: "I turned a REST API into an MCP server in one afternoon" (8–10 min)

Channel: Vínculo (@vinculohq). Master language: EN, then PT and ES audio tracks with localized title and description. Format: screen recording + voice; no slideshow.

| Time | Segment | On screen | Hook / line |
|---|---|---|---|
| 0:00–0:20 | **Cold open** | Claude Desktop answering "which pets are still available?" by calling the API live | "This chatbot just queried a real API. No plugin, no custom code: just the OpenAPI spec the API already had." |
| 0:20–1:00 | Problem | A SaaS docs page next to a chat window | "Your users are moving into AI assistants. If your API isn't reachable from there, you're invisible." |
| 1:00–2:00 | What MCP is (60 s) | Simple diagram: client → MCP server → API | "MCP is to agents what REST was to web apps: a standard way to list and call tools." |
| 2:00–3:30 | The spec | `examples/petstore.yaml`: operations, `$ref`, params | "Everything an agent needs is already in here: names, descriptions, parameters." |
| 3:30–5:00 | `inspect` | `python -m openapi_mcp inspect --spec ...` then `--json` | "One tool per operation, with input schemas generated from the spec." |
| 5:00–6:30 | **Safety** (the differentiator) | Write op hidden → `--allow-write` → `--exclude tag:admin`; secret redacted in the output | "Read-only by default. Your agent can look, not touch, until you say so." |
| 6:30–8:00 | Live demo | `claude mcp add ...` → ask Claude Code questions that chain two tools | "Watch it pick the right operation and fill the parameters by itself." |
| 8:00–9:00 | Tests + limits | `pytest -q` (20 passed), the limitations list | "Here's what it doesn't do yet. Honesty builds trust." |
| 9:00–9:40 | CTA | Repo + "Vínculo builds MCP servers for SaaS" | "If you want this for your product, with auth, rate limits and evals, link below." |

## Cuts (5–8 vertical, 30–45 s each)

1. Cold open: chatbot calling the real API (hook: "no plugin, no code")
2. "Read-only by default": the write operation disappears
3. Secret redaction: the token never shows up in the output
4. `inspect`: spec → tools in one command
5. "MCP in 30 seconds": the diagram
6. Claude Code chaining two tools

## Checks before publishing

- [ ] Fictitious data only (Petstore demo), no client or employer API
- [ ] Localized title, description and subtitles (EN/PT/ES)
- [ ] Link to the repo and the offer (MCP Server Sprint)
