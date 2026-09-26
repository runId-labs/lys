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
- **Prompt versioning**: at boot, each endpoint's `system_prompt` and the
  routes manifest are versioned into `ai_prompt_version`. Other prompt text
  kept in an endpoint's config (e.g. `summary_header`,
  `dynamic_context_header`) is versioned only if the endpoint lists its key
  under `prompt_segments` (stored as `"<purpose>:<key>"`); tuning keys must
  not be listed. A listed key that is missing or not a string logs a warning
  at boot. Read a segment with `AIService.get_prompt_segment(purpose, key)`.
  The boot hook runs in the api lifespan and in every Celery worker.
- **Structured output** (`chat_json` / `chat_json_sync`) walks the endpoint's
  `fallback` chain. When the caller stores which model authored a result, use
  `chat_json_with_metadata(_sync)`: it returns `data` plus the `model` /
  `provider` that actually answered — `config.model` still names the primary
  after a fallback.
- **`maxLength` is a safety net, not a target**: a string field that reaches
  its schema `maxLength` counts as truncated (constrained decoding cut it) and
  triggers the fallback. Size each bound well above the length the prompt asks
  for; on an `Optional[str]`, declare it on the string branch
  (`Optional[Annotated[str, Field(json_schema_extra={"maxLength": N})]]`),
  otherwise the decoder ignores it. Detection walks objects, lists, `dict`
  values and `anyOf` / `oneOf` unions; tuples (`prefixItems`) and `allOf` are
  not checked.

## Dynamic context (stable / volatile hooks)

Two consumer hooks shape what the model knows about the session state:

- `_get_stable_context` — cacheable, byte-deterministic, injected BEFORE the
  page prompt (the prompt-cache breakpoint sits after it).
- `_get_volatile_context` — non-cacheable, re-sent in full every turn
  (current date, focus record...). Keep it small by design.

The page's URL params are NOT the consumer's to render: the base emits them
generically as a JSON segment (`_page_params_context`) ahead of the consumer's
prose, via `_composed_volatile_context` — an override cannot lose them. Only
what the URL carries is shown (an absent key is the page's documented default),
and each key's MEANING lives in the page prompt — an undocumented key is
unreadable to the model. A consumer that renders the params itself duplicates
the base.

## Page params are declared in the routes manifest

The params are the only part of the system prompt the CLIENT controls. A param
arriving as free prose reaches the model among its instructions, and a crafted
deep link sent to another user runs with THAT user's privileges. So the boundary
is a declaration, not a filter: **each page declares its params under the route's
`params` key, and only what matches a declaration is rendered.**

```json
{
  "name": "dossierDetail",
  "path": "/dossiers/:id",
  "webservices": ["dossierById"],
  "params": {
    "dossierId": {"type": "global_id"},
    "statuses":  {"type": "enum", "values": ["draft", "sent", "paid"], "multiple": true},
    "since":     {"type": "date"},
    "search":    {"type": "text", "max_length": 80}
  }
}
```

| Type | Accepts |
|------|---------|
| `global_id` | a Relay GlobalID, unchanged — the rule for entity refs |
| `uuid` | a raw uuid, normalised. Legacy front routes only; `global_id` is the rule |
| `int` | an integer, or the digits a URL carries as a string |
| `bool` | a boolean, or `"true"` / `"false"` / `"1"` / `"0"` |
| `date` | an ISO date, normalised to `YYYY-MM-DD` |
| `enum` | one of `values`, exactly. No `values` → accepts nothing |
| `text` | free text up to `max_length`. **No default cap**: no `max_length` → accepts nothing |

`"multiple": true` on any type takes a list instead of a scalar, capped by
`max_items` (framework default 50). One invalid item invalidates the whole list —
a silently shortened filter would read to the model as a narrower selection than
the user's screen shows.

RULES:

- **Fails closed, everywhere.** No `params` on the route, an undeclared key, an
  unknown type, a value that does not parse: nothing is rendered. A page that
  forgets its declaration loses the segment and says so in the logs
  (`[PageParams]`) — it never falls back to sending raw client input.
- **Prefer a closed type.** `global_id`, `enum`, `date`, `int`, `bool` are
  structurally incapable of carrying prose. `text` is the only opening, and it
  costs an explicit cap — declare it only for a genuine free-text control
  (a search box), sized to what the page produces.
- **Never widen the declaration to make a param appear.** A param the model needs
  but that does not fit a closed type is a signal the value belongs in a tool
  result, not in the prompt.
- **The `## Page params` header is not configurable.** It frames the segment as
  data, not instructions: a safety control, not a voice choice. `json.dumps`
  keeps every value inside its own JSON string, so a value cannot forge a section
  heading of its own.
- The declaration bounds what the model READS. What a tool DOES with a param is
  the webservice's permission chain — an injection cannot exceed the connected
  user's own rights, and mutations still pass `CONFIRM_ACTION_TOOL`.

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

## Speech transcription

`AIService.transcribe(content, filename, config, language=None)` (and
`transcribe_sync`) turns raw audio bytes into text through the provider that
supports the capability — Mistral's `/audio/transcriptions` endpoint, whose
response is OpenAI-shaped (`{"text": "..."}`). Like OCR, it is an optional
provider capability and the fallback chain walks on `NotImplementedError`.

Configure a purpose as usual — e.g. `TRANSCRIPTION_PROVIDER` /
`TRANSCRIPTION_MODEL` (`voxtral-mini-latest`) — and resolve it with
`get_endpoint("transcription")`. An explicit `language` argument (ISO code)
improves accuracy when the language is known; endpoint `options` may carry
`diarize`, `context_bias`, `timestamp_granularities` or `language` (the
argument wins over the option). A 200 response without a `text` key
transcribes to `""` — the same result as silence, and guessing between the
two would invent an error.

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

## Special tools (handlers that do not go through GraphQL)

A tool can run locally instead of resolving to a GraphQL operation:
`executor.register_special_tool(name, handler)`, with
`handler(arguments, context) -> dict` (sync or async). Register from your
`_get_tool_executor` override, after `super()`.

The `context` carries `session`, `info` and `conversation_id`. Read the
conversation from `conversation_id` rather than closing a handler over one:
the factory consumers override runs once per turn but does not receive the
conversation, and a handler bound to a single conversation cannot be
registered there at all.

RULES:

- **R1 — Gate what must be gated.** A tool the model may call from anywhere is
  registered unconditionally; one that only makes sense on a given screen is
  gated on the page's `special_tools` (routes manifest). Register the handler
  **and** expose the definition under the same condition — a handler left
  registered is reachable by a model pattern-matching on earlier turns.
- **R2 — Errors belong to the model.** A tool naming something that does not
  exist is a miss the model can act on, not an incident: return it, do not
  raise through the turn.
- **R3 — Entity id arguments are GlobalIDs.** The ids a handler receives are
  the opaque GlobalIDs the tool results and the page context carry (see
  `rules.md` — "Entity ids at the API boundary"). Validate them at the handler
  entry and return an error dict on a raw uuid — never wrap, never rewrite.

### Whiteboard app (`lys.apps.ai_whiteboard`)

Optional app: the chatbot draws on an Excalidraw board with `draw_on_whiteboard` /
`read_whiteboard` (semantic patches, elements addressed by name), the user edits it by
hand. Load it after `lys.apps.ai`; a consumer override of `AIConversationService` must
inherit from the app's, or the tools are silently absent.

- Writes go through `WhiteboardService` only: it locks the row, checks `expected_revision`
  on editor saves, validates the scene and bumps `revision`.
- The scene size limit is the `ai_whiteboard.max_scene_bytes` plugin setting.
- A named `whiteboard_id` that is not the user's is refused (`WHITEBOARD_NOT_FOUND`), never
  redirected to the conversation's own board.

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
