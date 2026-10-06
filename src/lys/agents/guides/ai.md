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
    "since":     {"type": "date", "writable": true},
    "search":    {"type": "text", "writable": true}
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
| `text` | free text. The page declares the TYPE only — how much prose it may carry is the framework's |

`"multiple": true` on any type takes a list instead of a scalar, capped by
`max_items` (framework default 50). One invalid item invalidates the whole list —
a silently shortened filter would read to the model as a narrower selection than
the user's screen shows.

`text` is the one type able to carry prose into the prompt, so **a page does not
state its length**: the cap is injected into every text declaration ONCE as the
routes manifest is cached, and a `max_length` the page writes is ignored (and
logged). Declared per page, the number lived in two places — the schema, and
whatever bounds the input that fills it — and one of the two eventually gets
forgotten.

The cap is 200 characters — `MAX_SEARCH_LENGTH`, what the platform already
accepts for the same kind of string. It bounds PROMPT VOLUME, re-rendered every
turn, and nothing else; a lower number would be worse than arbitrary, because a
param over the cap is dropped and the model would then read a screen state the
user is not looking at. Raised for a whole deployment through
`chatbot.options.page_params.max_text_length` — one visible decision instead of
a value per page nobody re-reads. Two refusals at load, both logged:

| Configured value | Applied |
|------------------|---------|
| absent | 200 (`MAX_SEARCH_LENGTH`) |
| not a positive integer (`"200"`, `0`, `-1`, `true`) | the default — injected as is it would make every `text` param of every page fail validation silently |
| above 2000 (`MAX_CONFIGURABLE_TEXT_LENGTH`) | 2000 — a deployment does not get to unbound what every turn re-renders |

**Whatever fills a `text` param must be bounded to the same number or less** —
the input, the URL writer, the tool that sets it. Above it the filter works on
screen and vanishes from the model's view, which is the one failure the declared
schema cannot report.

**A `text` param may not be `multiple`.** One that says it is gets DROPPED and
logged as an error naming the page and the param: a list multiplies the prose it
brings, and what legitimately comes in several — tags, companies, statuses — is a
closed type. The param then arrives undeclared, which is how the runtime already
fails closed.

The cap is not a protection: an instruction fits in thirty characters, so what
makes a param safe to render is its TYPE — closed for every type but this one —
and `text` stays the exception.

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

### A continued navigation ends the turn

`navigate` with `continue_action: true` (confirmed through `confirm_action`)
schedules the move AND asks the client to resume the exchange on the new page.
The server ends the turn as soon as the tools of that iteration have run: no
further model call, `done` goes out with the actions (and the voice tail, if
any), so `done` can follow a turn whose only text is the sentence the model
wrote before the call — an empty text is possible. Anything the model would
write after the tool result belongs to the page it is leaving.

The CLIENT is responsible for the continuation: once the route has changed
and its page context names the new page, it sends the continuation message
(with that page's prompt and tools in play). Sending it before the page
context has moved makes the model answer with the old page. A `navigate`
without `continue_action` triggers no continuation.

### Writing params: `writable`, `set_page_params`, `navigate` arrival filters

Reading a param and writing one are different grants. Every declared param is
rendered to the model; only the ones marked `"writable": true` may the model SET:

- **`set_page_params`** — change the filters of the page the user is on. The
  framework exposes the tool only on pages declaring at least one writable
  param (handler and definition under the same condition, like every special
  tool), validates against the page's declared schema, and emits a
  `update_page_params` frontend action — the front applies it to the URL, the
  screen refilters, no review card: view state is reversible and the filter bar
  shows the change. Apply all-or-nothing on any refusal — a partial filter set
  must never land silently. `null` removes a writable filter (the front drops
  the key, the page falls back to its default — `{"companyId": null}` is back
  to the whole perimeter); it still needs the `writable` grant.
- **`navigate` arrival filters** — `navigate({path, params})` validates `params`
  against the TARGET page's declared schema (the route entry carries it) and
  lands the user directly on the state described. The target's writable params
  are listed in the tool description, so the model knows what it may set.
  `null` is refused there: an arrival state has nothing to remove.

A frontend action leaves the server TWICE on the streaming path, and the client
must handle it once. It is streamed in a `frontend_actions` event as soon as the
tool that produced it returns, with `fromIndex` — its position in the full list
the `done` event still carries. Applied on the event, the screen moves before
the answer that comments on it; applied only from `done`, it moves after the
written and the spoken answer, and the user is told about a page, a card or a
form that is not on screen yet. A client that handles the event skips those
indexes in `done`; one that ignores it applies everything from `done`, as
before.
- **`writable` is opt-in per param, default off.** The dossier the user works on
  (`clientId`) typically stays user-driven: the model reads it, never changes it.
- **`internal: true` marks component state, not a URL filter.** Its value travels
  through the page context (`updatePageParams` on the front), never the URL, and
  a model write routes to the page context (`internalParams` on the action)
  instead of the URL: an internal flag never lands in the URL, a filter never
  gets lost in the page context. The component syncs its state from the param
  both ways — the user's toggle reaches the model, the model's write reaches the
  screen.
- Writing params never widens rights: filters change what the user LOOKS at;
  every query still runs under the connected user's own permissions.

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

## Speech synthesis and the spoken answer

`AIService.synthesize(text, config, voice, response_format="mp3")` (plus
`synthesize_sync` and `synthesize_stream`, which yields raw PCM) is an optional
provider capability like transcription: the fallback chain walks on
`NotImplementedError`. The `voice` argument is never defaulted — the Mistral
speech API rejects a request without one — so the caller resolves it from the
endpoint's `options["voice"]`. `synthesize_stream` does NOT retry a provider that
already yielded a chunk: the caller has played that audio, and restarting the
sentence elsewhere would splice two voices mid-word.

The model writes ONE answer and the synthesizer reads it as it stands. There is
no second rendition, no tag convention and no repair call: what is written is
what is said, passed through `normalize_speech` — a deterministic pass that
strips the markdown and spells what a synthesizer cannot read honestly.

```python
"ai": {
    "chatbot": {
        "spoken_block": {
            "enabled": True,     # absent or False = the feature does not exist
            "language": "fr",    # optional: the spoken vocabulary to apply
        },
    },
    "tts": {"provider": "mistral", "model": "...", "options": {"voice": "Nova"}},
}
```

RULES:

- **The spoken form is never persisted.** `AIMessage.content` holds the answer
  exactly as written; nothing derived from it is stored. The spoken text is a
  pure function of that content, recomputed wherever a voice needs it.
- **`voice=True` on `chat_with_tools_streaming` is per turn and stateless.** The
  server keeps no voice session. A voice the deployment cannot serve
  (no `tts` purpose, no resolvable API key, no voice in its `options`) is dropped
  and logged — no `voice` event is emitted and the text stream never fails.
  `voice` events may arrive AFTER `done`: the text is complete, the reading is not.
- **No `voice_token` event exists.** The written stream IS the speech: the client
  bubble follows `token`, and `voice` carries the audio for the same text.
- **The spoken vocabulary is opt-in per language.** `spoken_block.language`
  selects a `SpeechVocabulary` (figures said in words via the optional
  `num2words`, currency symbols, scale prefixes, abbreviated months, layout
  glyphs). Declare none and the answer gets the markdown strip alone — the
  framework speaks no language by default and never applies another language's
  words. `fr` is the vocabulary shipped today; adding one is one table in
  `lys.apps.ai.modules.conversation.spoken_block`, never another branch.
- **Normalization strips marks, never content.** A bare URL, a time (`14:30`), a
  ratio (`3:1`), a date (`2024-01-01`) and a range (`10-15`) keep their
  punctuation: only a `+`/`-` OPENING a figure is spoken as a sign, and only a
  colon that is not part of a token becomes a pause.

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
- **R5 — Left out vs null are two intents.** An `Optional` argument of a
  query is declared nullable in the generated schema; a mutation's is not
  (left out, the field stays as it is). Left out, it takes the page
  param of the same name (`companyId` → `company_id`); a JSON null is an
  explicit "no value" kept over that default — on a query it is sent as
  null (no filter), on a mutation the argument is dropped (null never clears
  a field: an edit that clears goes through an explicit flag, like
  `clear_<field>`).

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
- `draw_on_whiteboard` commits the board in a transaction of its own, so it reaches the
  browser while the answer is still streaming. On a single-writer backend (SQLite) it
  falls back to the turn's session — correct, but the board appears at the end of the
  turn.
- The update signal tells the editor what to look at: `focus`, the names a patch drew, or
  the ones the caller passed in `focus`. `draw_on_whiteboard` with `focus` alone writes
  nothing and only moves the owner's view (`WhiteboardService.show`); it never opens a
  board. An editor save sends no `focus`.
- A drawing reports what it left on top of something else: the tool result carries
  `overlaps` (`element`, `with`, overlapping `width` and `height`) for the elements the
  patch drew, largest first, capped. The patch is applied regardless - the model places
  before sizes exist and fixes with an update. Links and elements inside a frame are not
  reported.
- A link (`from`/`to`) is routed by the server: straight, or round the elements standing
  between its ends along a free lane (`scene._route_between`). The whole patch is routed
  once applied, so the order it names things in does not matter.
- A named element's position is its top-left corner whatever it is made of
  (`scene._box`): a bar chart, anchored on its baseline, records its box.
- `read_whiteboard` never opens a board: one opened in the turn's session would be
  invisible to that separate transaction, which would then open a second one. With no
  board yet it returns `NO_WHITEBOARD`, and drawing is what opens one.

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
