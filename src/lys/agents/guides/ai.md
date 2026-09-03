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

## Conversation search (`search_conversation`)

Past the compaction threshold the older turns leave the prompt and survive only as the
summary. `search_conversation` reaches back into the messages themselves. It is offered to
the model **only once a completed summary exists** — before that the whole exchange is
still in the prompt — and it is bound to the current conversation, so no id travels and no
other conversation can be reached.

- **Indexing is periodic, not per message.** `lys.apps.ai.tasks.index_pending_messages`
  fills whatever carries no vector yet: schedule it in the worker's `beat_schedule`
  (~10 min). It also picks up messages that predate the feature, so no backfill is needed.
- **Three sources, merged by reciprocal rank**: full-text (stemmed words), trigram
  (accents, typos — needs `pg_trgm` and `unaccent`, both trusted, so a migration may create
  them) and semantic (`pgvector` + an `embedding` purpose). Each degrades on its own: with
  no embedding endpoint configured the search runs on the other two.
- **`vector` is NOT a trusted extension.** Only a superuser may create it, and the
  application user is usually not one on a deployed cluster. Install it per environment
  before the migration adding the `embedding` column runs; creating it from a migration
  works locally, where the container user happens to be superuser, and fails once deployed.
- **⚠️ Overriding `chatbot.summary_header` drops the tool's mention.** The default header
  tells the model the summary is not the whole story and that `search_conversation`
  retrieves the messages. A project that replaces the header — to translate it, typically —
  must carry that sentence over, or the model is never told the tool exists beyond its own
  description.

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
