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
- **`chatbot.max_tool_iterations`** (default 10): the model calls one chat turn
  may make. The last one is made with tool calls refused (`tool_choice` none, the
  tools still declared) and a turn-scoped instruction to answer from what the tools
  returned and say what it could not read: a turn that reads a lot ends on an
  answer, never on the `MAX_ITERATIONS` error that threw its reading away. That
  error remains only when the last call writes nothing. Size it on what the app's
  tools make a turn read (measure the rounds per turn in `ai_message`), not on a
  guess: every round is a model call the user waits for.
- Keys in `_keys` (mistral/anthropic); never hardcode a key.
- **A chat stream refused before its first chunk is retried**
  (`AIService.chat_stream_with_purpose`): a rate limit (429) with waits of 2 s
  then 8 s, or the provider's `Retry-After` up to 30 s; a server error (5xx);
  then the endpoint's `fallback`, as on a connection error or a timeout. Once a
  chunk was yielded nothing is retried. Without a `fallback`, the chat has no
  other model to answer: configure one on the chatbot endpoint.
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

App-wide context — what holds on every page (a panel beside the chat, a shared
menu, an export) — is not a hook. The front declares it as `globalPrompt` in
`chatbot.config.ts`; the routes manifest carries it at its root, and
`AIService.get_global_chatbot_prompt()` reads it. It is the first segment of the
leading system block (cacheable, ahead of the stable layer). A page prompt
describes its own screen only.

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
  "main_webservices": ["dossierById"],
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

### Messages the client writes on its own: `client_generated`

A continuation, a briefing requested at login: any message the client sends
without the user typing it is sent with `client_generated: true`
(`AIMessageInputModel`, `chat_with_tools[_streaming](client_generated=...)`).
The model reads it as any user turn; the row is stored with
`AIMessage.is_client_generated`, and everything that reads the conversation as
the user's words skips it:

- **Titling** fires on the first message the USER wrote, and titles from it —
  never from the instruction, which a titling model tends to carry out instead
  of summarizing.
- **`displayTitle`** falls back to that same message, and is null while the
  user has not written yet: the client shows its own label for a conversation
  it opened.
- **`search_conversation`** never returns it, and the row is neither indexed
  nor embedded: returned as a result, the instruction would read as something
  the user said.
- **History replay** exposes `isClientGenerated` on each message, so the thread
  hides the row without recognizing it by its content.

The flag is the client's word and grants nothing: set on a real message, it
only costs that conversation its title. It qualifies a written message only:
set on `tool_answers`, the turn is refused (`INVALID_CHAT_INPUT`).

A consumer overriding `_prepare_chat_context` must accept and forward
`client_generated` to `super()`.

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

### Where something is: `advise_navigation`

`navigate` lists each page by one line, and the chatbot knows the screen of the
page it is on only. `advise_navigation(question)` answers « where is… / how do
I… » for the other pages: one structured call on its own endpoint
(`navigation_advice` purpose) that reads the pages the user may open — the
routes already filtered for `navigate`, each with its description, writable
filters and the sections of its prompt titled with the consumer's headings
(`chatbot.navigation_advice.sections`; the whole prompt when unset) — and the
manifest's global prompt. It returns `page`, `params`, `message`, `current`.

- **The model designates, the code checks** (`checked_advice`): a page outside
  the user's routes and filters that `writable_page_params` refuses are dropped
  and listed in `dropped`, never forwarded. It navigates nothing: the chatbot
  calls `navigate` with the advice.
- **Offered on the same condition as it is registered**: routes to open AND the
  endpoint configured. A consumer that configures no endpoint sees no tool.
- A failed call is an `error` for the chatbot, never a raise through the turn.
- One cache key per set of routes: the same rights send the same prefix.
- Fine rights (a button the role hides) are read from the screen sections as
  written; the adviser does not check them.

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

## Exact arithmetic (`calculate`)

A model gets a single operation right and loses the thread of a chain: a projection carried
over several steps, an intermediate result reused later. `calculate` evaluates the chain
instead. It is offered on every turn, on every page (it reads nothing and changes nothing).

- **Named steps, evaluated in order.** `steps: [{name, expression}]`; a step uses the names of
  the steps before it. The first failing step stops the chain and is named in the error.
- **Parsed, never executed.** `utils/calculator.py` walks the Python AST against a whitelist:
  numbers, `+ - * / **`, parentheses, earlier step names, `round` (half up), `min`, `max`,
  `abs`, `sum`. Everything else is refused with an error the model can act on (special
  tools R2). Every input is bounded: 20 steps, 300 characters and 200 nodes per expression,
  exponent ≤ 1000, magnitude 1e±30.
- **Decimal arithmetic.** A literal is read from its text (0.1 stays 0.1), results come back
  as plain decimal text with at most 10 decimals.
- **The project prompt says when.** The tool's description asks for it on every derived
  figure; a project whose tools already return computed values (changes, totals) says in its
  prompt that those are quoted, not recomputed.
- **Provenance of the figures (chat turns).** Two right figures can give a wrong result: an
  amount of one source minus a different amount of another means nothing, and the formula
  does not say so. A tool that shows figures states where each comes from under
  `PROVENANCE_KEY` in its result (`utils/provenance.py`: `figure(value, measure, label,
  source, unit)` per figure, the value as its text shows it). The key is stored with the
  result and never sent to the model nor the client (`model_result`); the history and each
  result of the turn fill the turn's `Provenance`, which the chat's `calculate` reads. A step
  setting two figures against each other by `+`, `-` or `/` — same unit, different `measure`,
  different `source` — is computed and comes back with a `warnings` entry naming both. The
  same measure in two sources (a gap: actual against budget), one source's own arithmetic, a
  rate or a count applied to an amount raise none, nor does a number no tool stated or too
  short to tell (fewer than 3 digits written). It costs no model call: the model reads the
  warning in the same round. An agent's `calculate` reads the provenance of what its run's tools
  returned (`_RunState.provenance`); a follow-up starts from none: the readings of the run it
  continues are in its transcript without their provenance. A webservice tool
  states it through its node: a `figures_provenance` JSON field (`PROVENANCE_FIELD`), which the
  GraphQL executor moves under `PROVENANCE_KEY` (`from_webservice`).

## Agents (`AIAgentService`): an agent as a tool

An agent works one task through tools on its own endpoint and returns its analysis — and, when
its definition asks for one, a validated report formatted from it.
It is the specialist of the orchestrator / specialist pattern: the chatbot calls it from a
special tool, the agent reads in its own context, and only its result comes back — the
reading never fills the conversation.

```python
REVIEW = AgentDefinition(
    purpose="plan_review",                 # an endpoint: its system_prompt, model, fallback
    webservices=frozenset({"business_plan_rows", "all_regulatory_changes"}),
    report_schema=PlanReviewReport,        # optional: a Pydantic model the analysis is formatted into
    max_iterations=15,
    report_purpose="plan_review_report",   # a fast endpoint for the formatting
)
result = await app_manager.get_service("ai_agent_run").run(
    REVIEW, task, info, client_id=client_id, tool_defaults={"clientId": client_gid},
)
# result.succeeded: result.analysis (as written) and result.report (validated, when a schema is
# given) — else result.error (a sentence for the model); result.run_id
```

**Figures checked against the run (`figures_check=True`).** Every number the analysis writes is
looked for in what the run read — the task, the tools' results, its `calculate` steps
(`utils/sourced_figures.py`): within the rounding its digits allow, at the scale it is written in
(`750 k€` is 750 000), a percentage also as the ratio a calculation returned. A figure found
nowhere opens the correction round like any issue of the caller's check. Years, dates and numbers
of fewer than three significant digits are not checked. It catches a figure invented, rounded from
memory or computed in the head; not a figure read but attached to the wrong thing (a balance of
the wrong month called the low): that is the reading's to state, or the caller's check.

The run: its tools are the declared webservices the user may call, plus `calculate`; a tool
loop under the user's token, the last call with tool calls refused
(`AGENT_FINAL_ROUND_INSTRUCTION`), ending on a written analysis; then, when the definition has
a `report_schema`, one structured call turning that analysis into the report
(`AGENT_REPORT_INSTRUCTION`) on `report_purpose` — reason, then format, so the tool history
never crosses a structured call; formatting decides nothing, a fast model without reasoning
does it. Each run is traced in `ai_agent_run` (task, transcript, report
or error, totals, and `calls`: one entry per model call — kind, latency, tokens, tools asked),
apart from the conversations: a run is neither listed in the user's history nor indexed for the
conversation search. The trace is written in transactions of its own, opened at the start and
closed at the end whatever the end (shielded, bounded by `AGENT_TRACE_CLOSE_TIMEOUT`): it never
depends on the caller's transaction, and a trace that cannot be written never fails the run.

A specialist that runs no agent loop - one structured call (`advise_navigation`), a loop of its
own (the whiteboard drafter) - is traced in the same table with `AIAgentService.record`: one row
written closed, its calls built with `traced_call` (`lys.apps.ai.utils.tracing`, the same entries
as an agent's), so what a turn cost reads in one place. A structured call gets its tokens from
`chat_json_with_metadata` (`AIJsonResponse.usage`, filled by the providers' `chat_json_with_usage`;
a provider that does not implement it answers None) - an agent's report call included.

RULES:

- **R1 — Read only.** Declared webservices are queries; a mutation, or a name that is not a
  tool, raises at the run. What an agent reads (a legal text, a document) may carry
  instructions: an agent that cannot write cannot act on them.
- **R2 — The user's rights, never more.** A run needs the user's token
  (`AGENT_REQUIRES_USER_TOKEN`): there is no service identity to fall back on. Its tools are
  the intersection of the declared ones and the user's — an agent reads what the user may.
  A declared tool whose audience leaves the agent out (TOOL R8) raises at the run: the
  definition lists what the agent reads, the audience who may be offered it, and the two agree.
- **R3 — A failure is a result.** A provider error or a report that does not validate ends
  the run FAILED with the error kept on the trace; the caller gets a generic `error` to hand
  to its model, never the provider's message. A tool that fails is the agent's to read, as
  for the chatbot.
- **R4 — The caller decides the scope.** What the caller already checked (the client, the
  version read) is passed as `tool_defaults`, injected like page params and PINNED: its ids
  override the model's (`GraphQLToolExecutor(pin_ids=True)`). Left free, a model invents a
  client id from another entity's uuid. Name the scope in the task too, so the model reads it.
- **R5 — What the agent returns is the contract.** The chatbot repeats the figures of the
  agent's result, never its own: a figure the specialist did not return is not said. A report is
  the definition's choice, not the library's: with a `report_schema` the analysis is formatted
  into it — fields a program reads, at the cost of one more model call that copies the whole
  analysis (measured as long as writing it, or longer) —; without one (`report_schema=None`),
  the run returns `result.analysis` as written, which is enough when the caller is a model
  reading prose. `result.report` is then None on success too: test `result.succeeded`, never
  `result.report is None`, to tell a failure. The analysis check (R6) bears on the analysis in
  both cases.
- **R5b — A report may be written from the readings, and checked field by field.**
  `report_source=AGENT_REPORT_FROM_READINGS` writes the report from the run's transcript — what
  the tools returned — on the agent's own endpoint and instructions, instead of copying the
  analysis: its fields come straight from the sources, and nothing is written twice (the agent's
  last message may then be one line saying it has read what it needs). The provider must accept
  tool messages beside a response schema — check it on the endpoint's models, fallback included;
  it needs a `report_schema` and no `report_purpose`. `run(..., report_check=...)` then takes an
  async callable reading the REPORT and returning `AnalysisIssue`s: each value is read back where
  its field says it was read. Prefer it to citations searched in prose whenever the figures
  matter — a field is either checked or absent from the report, while a citation worded another
  way is never seen by the check. Issues open ONE correction round (the issues as a user message,
  `revision_iterations` model calls to read again), the report is written again and checked
  again; what is still wrong comes back in `result.issues`, after the analysis check's. Give the
  schema no free-text field that could hold the figures: a model fills it and leaves the checked
  fields empty.
- **R6 — Check the analysis against its sources.** `run(..., analysis_check=...)` takes an async
  callable reading the analysis text and returning `AnalysisIssue(location, message)`s — the caller
  knows the sources (a plan's cells, a text's articles) and reads them back, never the model. It
  checks the ANALYSIS, the source of truth, not the formatted report: a formatter dropping a field
  must never look like an analysis error. Issues open ONE correction round (`revision_iterations`
  model calls, the issues sent as a user message): the evaluator / optimizer pattern; the
  corrected analysis is checked again, then formatted once. What is still wrong comes back in
  `AgentRunResult.issues`; the caller decides what to show. A check that cannot run (its source
  refused the request) flags the analysis unchecked: it never fails the run, opens no correction,
  and must never read a refused request as data ("every cell empty"). Each check's findings are
  traced on the call that wrote the analysis (`calls[].issues`).
- **R7 — Mind the caller's timeouts.** A run takes minutes; a special tool awaits it within
  the chat turn (bounded by `executor.turn_token_ttl`), a GraphQL webservice does not —
  expose a run to a client as a job (start, then read the report), not as a blocking query.
- **R7b — The tool calls of a round run together.** The model may ask several tools in one round:
  they run concurrently and their results come back in the order asked, so a round lasts as long as
  its slowest call. Safe because an agent's tools only read and each call is its own request; a
  failing call fails alone. Tell the agent, in its prompt, to send independent readings in the SAME
  round rather than one reading that asks for everything (slower) or one per round (their sum).
  The chatbot does the same for the GraphQL queries it asks in a row (`runs_alongside`): a special
  tool (the turn's session, the client's actions) and a mutation run alone, in their place, and no
  read asked after them runs before them. Results are still saved and streamed in the order asked.
  At most `executor.max_parallel_calls` calls (default 8) run at once (`ToolExecutor.run_together`):
  a model may ask for dozens of reads in a round, each a request to the API. A custom
  `ToolExecutor` runs every call alone unless it overrides `runs_alongside`.
- **R8 — A run may be followed up, by its own caller only.** The caller asks again on a run
  instead of starting over: `continuation = await service.continuation(DEFINITION, run_id, info,
  client_id)`, then `run(DEFINITION, follow_up, info, continuation=continuation, analysis_check=...)`.
  `continuation` refuses what is not the caller's to continue with ONE answer
  (`AGENT_RUN_NOT_FOUND`: unknown, malformed, another user's, agent's or client's — nothing told of
  a run that is not theirs), and the caller's run that did not succeed or ended past
  `AgentDefinition.continuation_ttl` (`AGENT_RUN_NOT_CONTINUABLE`, 24 h by default: what the run
  read was read under the rights of the time, on data that moves). The follow-up runs on the
  continued run's scope (its `client_id` and `tool_defaults`, stored on the trace) — passing a
  scope of the caller's with a continuation raises: a follow-up never changes client or version
  midway. It reads the run's transcript with each tool result cleared
  (`AGENT_CLEARED_TOOL_RESULT`, call ids kept: the tool-result clearing of context editing — a run
  reads up to a million characters), then the follow-up; the agent calls again what it needs. It is
  a run of its own (`continued_from_id`): a run is never rewritten once it ended. Its report answers
  the follow-up. At the API boundary its `run_id` is the caller's to type (a GlobalID).

## Batch jobs (structured JSON, asynchronous)

`AIService.submit_json_batch(requests, config, schema, metadata=None, timeout_hours=None)`
(and `_sync`) sends many `chat_json` calls as one job, answered later — on Mistral at
half the price. Each `AIBatchRequest(custom_id, messages)` becomes the exact request
`chat_json` would send: the endpoint's system prompt first, its options, its strict
response schema. An optional provider capability, like OCR: a provider without batch
jobs raises `NotImplementedError`.

- **Polled, never called back**: `get_batch(job_id, config)` returns an `AIBatchJob`
  whose `state` is provider-neutral (`AIBatchState`: PENDING, COMPLETED, FAILED,
  EXPIRED, CANCELLED); read the results once `state.is_final` — reading them before
  raises `ValueError`, since an empty list would pass for requests never processed.
  Mistral exposes them only when the whole job has finished.
- **Stateless**: lys stores nothing. The caller keeps the job id and polls and reads
  it with the same endpoint config (its key and base URL).
- **One endpoint, no fallback chain**: a batch runs on one model.
  `get_json_batch_results` returns one `AIBatchResult` per processed request — its
  `data`, validated like a `chat_json` answer (a text field cut at its `maxLength` is
  an error), or its `error`. A request absent from the results was not processed (the
  job expired, failed or was cancelled first). Send the failed and missing ones again
  through `chat_json_with_metadata`, which walks the fallback chain.
- **Bounds**: `custom_id` unique within a job. On Mistral the requests are uploaded as a
  JSONL file and the job created on it — inline requests were refused past ~10 MB (500
  structured requests, measured) —, up to `MistralProvider.MAX_BATCH_REQUESTS` (100,000)
  and `MAX_BATCH_FILE_BYTES` (512 MB) per job, both checked before any upload
  (`ValueError`: split the set). The results are read from the job's output and error files.
- **Files kept by the provider**: the input file and the result files stay in the
  Mistral workspace — lys deletes on its own only the input file of a job the API
  refused. They hold the prompts and answers: once the results are recorded (never
  before — they cannot be read again), call `delete_batch_files(job_id, config)` (and
  `_sync`) per the project's retention rules. It refuses a job not final (`ValueError`),
  deletes best-effort (a failure is logged, not raised) and returns the number of the
  job's files gone — a file already deleted counts, so a retry is safe.
  `timeout_hours` defaults to the provider's (24 h on Mistral, under 7 days); keep
  jobs to a size whose results are worth waiting for together.
- `usage` on each result is the provider's token count, to compare the cost billed.

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
- **R6 — A heavy field is read on request.** A tool selects every field of its
  node (one level of scalar subfields), and every round of the turn sends the
  result again. A field the model rarely needs and that weighs (a text's full
  wording) is declared on request: `options={"generate_tool": True,
  "tool_on_request": {"flag": "with_article_text", "fields": ["articles.content"],
  "description": "..."}}`. The tool gets a boolean argument `flag` — never sent to
  GraphQL —, its selection leaves the fields out unless the call sets it. The
  description says when to ask (to quote a text word for word), and what the
  light result already holds. A path the tool does not select refuses the tool.
- **R7 — A connection tool pages.** The generator declares a connection's
  `first` and `after` (added to the field by its extension, after the tool is
  generated) and selects `page_info { has_next_page end_cursor }` beside the
  rows. Left out, `first` is `DEFAULT_TOOL_PAGE_SIZE` (25), never the server's
  `relay_max_results`: every row is sent again with each round of the turn. A
  resolver must not name an argument `first` or `after`. There is no `limit`
  argument: `first` is the page size, capped by `relay_max_results`.
- **R8 — A tool may name its audience.** `options={"generate_tool": ["review_agent"]}`
  instead of `True` offers the tool to the AI endpoint purposes listed only — the chatbot's
  (`AI_PURPOSE_CHATBOT`), an agent's (its `AgentDefinition.purpose`) —, the others never see it.
  Use it to keep a specialist's reading out of the chatbot: the chatbot calls the specialist,
  not its tools. `True` stays "every consumer". The audience is stored on the webservice
  (`ai_tool_consumers`, NULL for every consumer) and applied by
  `AIToolService.get_accessible_tools(connected_user, consumer=...)`: a caller naming no
  consumer gets the unrestricted tools only. It decides which model sees a tool, never what the
  user may do: the token still filters first, super users included. An empty list or anything
  but a bool or a list of strings raises at registration.
- **R9 — A slow tool names its wait.** `options={"generate_tool": True, "tool_timeout": 180}`:
  a call of that tool waits 180 s for the API, in place of `executor.timeout` (30 s by default) —
  the chatbot's and the agents' alike. It bounds the caller's wait, never the webservice: the
  webservice runs unbounded for every caller, and one cut short by the caller still runs to its
  end. Raise it for a reading measured slow, not as a margin; a run of minutes is a job (agents
  R7). Stored with the definition (`_graphql.timeout`): a change applies once the webservices
  are registered again (a restart). Anything but a positive integer raises at registration.

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
  raise through the turn. Say it as a wrong id, never as an empty result: the
  model reports an empty result to the user as missing data. The GraphQL
  executor does it for `NOT_FOUND`; a handler whose query swallows the error
  checks the entity before answering "nothing found".
- **R3 — Entity id arguments are GlobalIDs.** The ids a handler receives are
  the opaque GlobalIDs the tool results and the page context carry (see
  `rules.md` — "Entity ids at the API boundary"). Validate them at the handler
  entry and return an error dict on a raw uuid — never wrap, never rewrite.
- **R4 — Call the API back with the turn's token.** A handler that queries the
  API uses `info.context.access_token`, read inside the turn (in
  `_get_tool_executor` or when the handler runs). A chat turn runs on a
  delegated token of its own (`_turn_access_token`): same claims as the
  user, minted when the turn starts, revoked when it ends, bounded by
  `executor.turn_token_ttl` (default 1800 s). The browser's token lives a few
  minutes and every refresh revokes it — a handler holding it fails with
  `ACCESS_DENIED_ERROR` mid-turn.

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
- The tools speak GlobalIDs (`WhiteboardNode`): `whiteboard_id` and `copy_from` take one —
  a raw uuid or another type's id is refused (`INVALID_WHITEBOARD_ID`) — and results
  return one, with `conversation_board` telling the conversation's own board from a board
  reached by id. The service behind keeps raw ids.
- A board named by `whiteboard_id` is edited in place and never attached to the
  conversation (no pointer, no flag sync): it stays the user's. `copy_from` opens a new
  board as an exact copy (`WhiteboardService.copy_for_user`, flags not copied), attached
  to the conversation; the call's patch lands on the copy. `duplicateWhiteboard` (OWNER)
  makes the same copy from the UI, attached to no conversation. `updateWhiteboardTitle`
  (OWNER) renames a board from the UI; the model has no rename tool.
- Pinning, archiving or restoring never moves a board's `updated_at` (its last edit):
  flags are written through `_set_flag`.
- The model names a board it opens (`title` on `draw_on_whiteboard`, read only when the
  call opens one). It falls back to the conversation title, which is written in the
  background and may not exist yet on the turn of the user's first message - so never
  rely on that fallback to name a board.
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
- A patch item carries only the fields the tool declares for its operation
  (`consts.ADD_ITEM_FIELDS` / `UPDATE_ITEM_FIELDS`, kept equal to the tool schema by a
  test): an undeclared field refuses the whole patch (`WHITEBOARD_INVALID_OPERATION`)
  rather than being skipped. A `kind` on an existing element (update, or add under a
  taken name) must repeat its current kind - changing kind is a delete then an add.
- A named element's position is its top-left corner whatever it is made of
  (`scene._box`): a bar chart, anchored on its baseline, records its box.
- Frames are the deck: the consumer's editor may present a board frame by frame, in
  reading order on the canvas (rows top to bottom, left to right) - no order is stored.
  The tool description tells the model to draw a story as one frame per step, speaker notes
  as a `notes-<frame>` sticky note beside (outside) the frame. `frame` on
  an update moves an element and its parts into a frame (empty string: out of any);
  without `x`/`y` it lands in the frame's grid. Moving by coordinates alone leaves
  `frameId` behind, and the editor clips the element to the frame it still names.
  Frames do not nest (`WHITEBOARD_INVALID_OPERATION`).
- Editor contract (consumer side): order slides by the same rule as `scene.slides`
  (`consts.SLIDE_ROW_OVERLAP_SHARE`), and persist `appState.whiteboardStroke`
  (`THEME_STROKE_KEY`) when saving the scene - Excalidraw's `restoreAppState` drops
  unknown keys, which silently resets the board's stroke to `clean`. The theme keys the
  editor saves are not validated on write: `scene.theme` reads them back with a fallback
  on the default (`clean`, `#ffffff`) for any value no name or colour covers.
- Inside a frame, `x`/`y` count from the frame's corner (add, update, read-back), and an
  unplaced element lands in the frame's own grid. Text size is named (`size`:
  small/normal/large/title, `consts.TEXT_SIZES`) and defaults to `large` in a frame. The
  board has a `theme` (`background`, `stroke` clean/sketch) kept in the scene's `appState`
  (`THEME_STROKE_KEY`); elements take named looks (`stroke`, `corners`, `thickness`) on
  every drawn part, refused on a bare text; `align` (left/center/right) on texts, boxes
  and tables. `read_whiteboard` returns `theme` and reports
  a look only where it departs from it.
- A table or chart is redrawn (not patched) on new data or a new `size`/`align`; the
  redraw keeps its frame, colours, look and layout (`customData.whiteboardLayout`:
  resolved size, align, given width/height), kept apart from its data
  (`whiteboardSpec`, read back as `data`).
- A chart's figures are bounded by `consts.MAX_CHART_VALUE`, never by `MAX_COORDINATE`: a
  figure is no place on the board, and a revenue in euros runs past a hundred thousand. A
  line chart may carry `references` (up to `MAX_CHART_REFERENCES`, `{label, value}`): a
  threshold or a target, kept in the spec and drawn dashed by the consumer's renderer; refused
  on another chart type.
- A labelled shape keeps `consts.LABEL_MARGIN` between its edge and its label. The editor
  cannot be told a padding wider than its own (`BOUND_TEXT_PADDING`), so the label's `text`
  is broken that much narrower - the editor keeps lines that fit - and the shape sized with
  the margin all around; `originalText` keeps what it says, which the editor re-wraps from
  when the user resizes or edits, and which `read_whiteboard` reports. A figure is never
  broken at its digit groups or before its unit (`scene._words`). A width or height given to a
  labelled shape grows to hold its label - never narrower than its widest word -, at creation
  and on a resize; `unfit_labels` then only finds a box sized in the editor.
- A link is measured from its points (`scene._footprint`): the editor stores its origin where it
  starts, so a link running left or up spreads the other way. A detour between two elements of a
  slide takes a lane inside it.
- `read_whiteboard` never opens a board: one opened in the turn's session would be
  invisible to that separate transaction, which would then open a second one. With no
  board yet it returns `NO_WHITEBOARD`, and drawing is what opens one.
- **Drafted drawings** (`conversation/drafting.py`): once the consumer configures the
  `whiteboard_drafting` endpoint, `draw_on_whiteboard` takes a `request` instead of a patch
  (`DRAFT_ON_WHITEBOARD_TOOL`, same name, handler and definition chosen together): the
  chatbot says what to show, with its figures and arrows, and a drafter on that endpoint
  lays it out with `apply_patch` (`DRAFT_PATCH_TOOL`: the layout rules and the patch
  vocabulary, the same text as the direct tool's). Its patches are applied to the scene in
  memory (`scene.apply_operations`, the same rules), each read back with places, sizes and
  `overlaps`, for at most `MAX_DRAFT_ROUNDS` calls. What the checks (`review`) find goes back
  once, for a pass on a budget of its own (`MAX_CORRECTION_ROUNDS`): shared, a drafter patching
  to its last call never had its checks sent back. A pixel measure the request quotes is
  layout, not a figure the drawing must show. Each drafting is traced
  (`AIAgentService.record`). The patches are then written in one revision, in order
  (`WhiteboardService.draw(patches=...)` → `apply_patches`), on the board as it stands
  then. The chatbot reads back `drawn` (what this call drew) and the drafter's `note`,
  never the whole board. A drafter that fails on its first pass or draws nothing writes
  nothing (`DRAFT_FAILED`); one that stops answering during the correction pass keeps what it
  drew, returned with the `issues` left. `focus` alone, `copy_from` and `whiteboard_id` behave as for a direct
  drawing; a copy is drafted on its source's scene. Without the endpoint the chatbot draws
  itself, as before.
- **Meaning over values.** Colours are named by what they mean (`tone`: accent, positive,
  risk, watch, neutral), resolved to a line and a fill from the board's palette before
  anything is drawn - a `color`/`background` given too wins. What a drawing leaves unsaid
  follows the consumer's style (`scene.BoardStyle`, read by `WhiteboardService.style` from the
  plugin settings `palette` - the tones recoloured, the set of tones fixed -, `corners` - the
  default corners of a shape, never of a link or a table - and `note_background`); without
  them lys draws plain (`consts.TONES`, square, yellow post-it). A tone given without a
  colour of the element's own is kept on it like a class (`whiteboardTone`): the editor is
  handed the scene with the palette applied (`WhiteboardService.scene_for_editor` →
  `scene.restyled`, nothing written), so a palette changed later recolours what was drawn
  in a tone. A colour of its own - given by a caller, or set by hand in the editor - wins:
  the class is dropped (`scene.unclassed`, on every editor save). A
  line is `pattern`ed solid, dashed or dotted (a look, on any drawn part). A link runs along
  a `path` (straight; elbow - the editor's own elbow arrow, `elbowed` with its ends pinned by
  `fixedPoint`, kept orthogonal by the editor when an end moves; curved - `roundness` type 2)
  remembered in its customData and routed again when an end moves, and ends with a `head`.
- **Components** (`kpi`, `callout`, `steps`) are drawn from what they say, like a table: one
  name over several parts, the data in `whiteboardSpec`, the layout and colours in
  `whiteboardLayout`, redrawn whole on an update of their data, size or colours. A kpi
  writes its `value` and `delta` as given - nothing is computed.
- **Slide zones.** In a frame, `zone` (title, full, left/right, top/bottom, quarters) and
  `slot` ("k/n" equal columns) give an element its place and - a table aside - its width,
  as shares of the frame (`scene._zone_box`): a slide is laid out without coordinates.
- **A drafted drawing is checked** (`drafting.review`), on the elements the drafting drew
  only: overlaps (`scene.overlaps`), an element sticking out of its frame - cut off the
  slide when presented (`scene.outside_frames`) -, a label its box does not hold, measured
  with the font's advance widths (`scene.unfit_labels`), a link the chatbot asked for in
  `links` (by the texts of its two ends, accents and case aside) that no bound arrow draws
  (`scene.missing_links`), a figure the request does not give (`unsourced_figures`, as
  for an agent's `figures_check`) - and what was asked and left out: a figure of the request
  the drawing never shows (the same check the other way round), a slide holding its title
  alone (`scene.empty_frames`). What they find goes back to the drafter once; what is
  left reaches the chatbot as `issues`. A figure the chatbot computed in its head and wrote
  in the request is not caught here: the request is the source.

## Frontend proposals (chatbot-initiated actions)

The framework's `FrontendAction` stream lets the LLM propose actions
(navigate, refresh, or project-specific proposals). The boilerplate ships the
generic handler; project proposal types (mutation + messages per type) are
registered through the `proposalConfigs` prop of `ChatbotRestricted` — see
`agents/guides/front/restricted-feature.md` and the ChatbotRestricted types.

### A proposal is answered by the user (`user_answered_tools`)

A special tool that only puts a proposal in front of the user (a form to
review, a draft to validate) must not answer its own call: a result such as
"sent for validation" lets the model carry on as if the user had decided.
Declare it on the conversation service:

```python
class AIConversationService(BaseAIConversationService):
    user_answered_tools = frozenset({"propose_thing"})
```

A call of such a tool that produced a frontend action is LEFT OPEN:

- its actions carry `toolCallId` (tagged before they are streamed);
- no result is written, and the turn ends after that tool batch — no further
  model call, `done` goes out with the actions, as for a continued navigation;
- the client posts the user's answers, one per open call and all at once, as
  `tool_answers` (`AIToolAnswerModel`: `tool_call_id`, `result` — a JSON
  object, bounded by `MAX_TOOL_ANSWER_LENGTH`; at most `MAX_TOOL_ANSWERS` per
  request) with no message content, on the conversation id — `toolAnswers`
  on the `sendAiMessage` mutation, the same field on an SSE endpoint. A turn
  carrying both or neither is refused (`INVALID_CHAT_INPUT`). The service
  checks the answers against the calls it left open (latest assistant
  message, user-answered tool, no result yet; the conversation row locked)
  and refuses any other set (`INVALID_TOOL_ANSWERS`); the answers become the
  calls' results and the model resumes on them. A resume writes no user
  message.
- an accepted answer is durable: the client acted on it before posting it.
  A resume the model then fails to answer (provider error) keeps its
  answers; the calls are no longer open, and the next message reads them.
- a new message sent instead closes the open calls with
  `UNANSWERED_TOOL_RESULT`, before the history is read.

A call that produced no action (its arguments refused) is answered by the
tool as usual: there is nothing for the user to answer. The answer is the
client's word: the model reads it as data, and what it claims to have done
(a created entity) is the client's to have done under the user's rights.

## SSE endpoints (already wired in `api/src/app.py`)

`POST /sse/chat` (streaming conversation, page context, message limits) and
`GET /sse/signals` (user channel). An endpoint serving user-answered tools also
takes the answers in place of the message and passes them as `tool_answers`.
A refused input raises `LysError` from inside the stream, once the response
has started: the endpoint turns it into an `error` event carrying its code
(`INVALID_CHAT_INPUT`, `INVALID_TOOL_ANSWERS`), not a generic internal error. Custom
endpoints are exceptional — extend through services and tools instead.
