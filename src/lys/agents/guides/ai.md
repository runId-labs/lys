# AI / chatbot integration (back)

The lys `ai` app provides a chatbot (SSE streaming, tools, conversation
persistence). The boilerplate wires it end-to-end; this guide covers what a
project changes.

## Configuration (api/worker `settings.py` → `configure_ai`)

- **Endpoints are per-purpose**: `{PURPOSE}_PROVIDER` / `{PURPOSE}_MODEL` env
  (PURPOSE = CHATBOT, TEXT_IMPROVEMENT…) — no code change to switch.
- **Chatbot system prompt** = project content: identity, style, tools
  description, constraints. Rewrite the placeholder prompt in
  `api/settings.py`; keep it explicit about what the assistant may/may not
  claim.
- **Compaction** (`token_threshold`, `window_messages`) and
  `routes_manifest_path` (navigation tool — resolved from the front manifest)
  are already wired.
- Keys in `_keys` (mistral/anthropic); never hardcode a key.

## Exposing a webservice as a chatbot TOOL

Any `lys_getter` / `lys_connection` / `lys_creation` query can become a tool
the LLM calls. Opt in with `options`:

```python
@lys_connection(
    ProductNode,
    description="Get the yearly sales figures of a company, aligned across years.",
    options={"generate_tool": True},
)
async def get_yearly_figures(self, info, …) -> select:
    …
```

RULES:

- **R1 — The `description` IS the tool prompt.** Write it for the LLM: what
  the data means, when to call it, units. A vague description = a misused tool.
- **R2 — Tools are read-mostly**: getters/connections. A mutating tool runs
  with the user's session — think twice before letting the LLM write.
- **R3 — Front activity labels**: tool names surface as chat activities —
  map them in `ChatbotRestricted`'s `activityLabelKeys` prop +
  translations (see the front guides), or users see a raw technical name.
- **R4 — Don't leak internals**: the system prompt must forbid naming tools
  or the model/provider (mirror the boilerplate placeholder).

## Frontend proposals (chatbot-initiated actions)

The framework's `FrontendAction` stream lets the LLM propose actions
(navigate, refresh, or project-specific proposals). The boilerplate ships the
generic handler; project proposal types (mutation + messages per type) are
registered through the `proposalConfigs` prop of `ChatbotRestricted` — see
`agents/guides/front/restricted-feature.md` and the ChatbotRestricted types.

## SSE endpoints (already wired in `api/src/app.py`)

`POST /sse/chat` (streaming conversation, page context, message limits) and
`GET /sse/signals` (user channel). Custom endpoints are exceptional — extend
through services and tools instead.
