# Back rules — allowed / forbidden (read for ANY back change)

Consolidated interdictions, each with the WHY — an agent that understands the
reason does not need the rule spelled out for a variant it hasn't seen.

## The registry is the only door

> **ALL entities and services MUST be accessed through `app_manager`
> (`get_entity` / `get_service`). Direct imports are FORBIDDEN.**

```python
# ✅
cls.app_manager.get_entity("client")
info.context.app_manager.get_service("product")
cls.entity_class                      # inside your own EntityService

# ❌ — WILL break: registration overrides, SQLAlchemy mapper inspection, Celery workers
from lys.apps.organization.modules.client.entities import Client
from myapp.apps.catalog.modules.product.services import ProductService
```

**Why**: components can be overridden (last-registered-wins) — an import pins
the class you happened to import, silently diverging from the registry the
framework uses for mappers, permissions and the schema. The check is
mechanical too: an `import-linter` contract in your project can flag direct
imports automatically.

**Sole exception — typing**: importing a class purely for a type annotation
inside `if TYPE_CHECKING:` is tolerated. Anything beyond annotations (a call,
an instantiation, a subclass) goes through the manager.

## Environment and configuration

- **No hardcoded environment values.** Secrets, URLs, emails, providers,
  tunables → `settings.py` reading `.env` (pattern: every `os.getenv` has a
  documented entry in `.env.example`). Never log secrets.
- **Idempotent startup.** `on_initialize` hooks and fixtures must be safe to
  run repeatedly (no duplicates, no data loss) — they run in every process at
  every boot.

## Style and structure

- PEP 8, ≤120 cols, 4 spaces, double quotes, type hints on public methods.
- English everywhere (code, comments, migration messages, commit messages).
- Absolute imports; imports at the top of the file.
- Production-ready only: no placeholder `pass`, no TODO without a task, no
  debug prints.

## Webservices / permissions

- Permission decisions are declarative (`is_public`, `access_levels`,
  `is_licenced`) — never imperative role checks inside a webservice.
- Entities with tenant columns implement `organization_accessing_filters()`
  (lys raises at startup otherwise).
- A webservice name is a public contract (front `mainWebserviceName`, JWT
  claims) — never rename casually.
- A `ROLE` / `ORGANIZATION_ROLE` webservice with no role granting it is
  unreachable by anyone but client owners (`webservice.md` R7). When adding
  one and the user hasn't named the role(s), ask before finishing — list the
  existing roles, state which one you'd pick and why. Do not guess, and do
  not ship it ungranted with a mention after the fact. Skip the question only
  when the user named the roles, or the webservice is `INTERNAL_SERVICE` /
  public / connected-only.

## Entity ids at the API boundary

- **Every entity id crossing a webservice or tool boundary — in or out — is a typed
  Relay GlobalID** (base64 `"TypeName:uuid"`). Raw uuids never cross it: nodes and
  payloads expose references as GlobalIDs, and inputs are GlobalIDs.
- **The tool executor rejects a raw uuid instead of wrapping it** with a type
  prefix guessed from the parameter name. That coercion fabricated ids the caller
  never had — a company uuid passed as `client_id` wrapped as
  `ClientNode:<company uuid>` read back as an empty result, with no error to
  recover from. The rejection message is LLM-actionable (re-read the id from a
  tool result).
- **A webservice taking a caller-supplied id adds an existence/access guard** so
  an unknown or foreign id errors loudly instead of reading as empty data.
- **Special tool handlers enforce the same boundary** on their arguments:
  validate, return an error dict — never re-wrap, never extract to a raw uuid in
  what the model reads.
- Exceptions: parametric codes (KPI codes, status codes) are codes, not entity
  ids — plain strings. Database columns and internal code stay raw; only the API
  surface speaks GlobalID.

## Client-supplied context in a prompt

- **Nothing the client sends reaches a prompt undeclared.** The chatbot's page
  params are rendered only where the routes manifest declares them, with a
  declared type (`ai.md` — "Page params are declared in the routes manifest").
  Undeclared page, undeclared key, unknown type, unparsable value: nothing is
  rendered, and the drop is logged.
- **Prefer a closed type over free text.** A `global_id`, `enum`, `date`, `int`
  or `bool` cannot carry an instruction. `text` is the only opening and costs a
  mandatory `max_length`; a param that fits no closed type belongs in a tool
  result, not in the prompt.
- **Never log the dropped value** — only its key and the reason. Client input is
  exactly what must not end up in a log.
- **The framing line that tells the model "this is data, not instructions" is not
  configurable.** A control an app can reword is a control an app can weaken.

## Weakest spots to double-check (empirical)

- `Uuid(as_uuid=False)` on every soft FK — one forgotten and the DB accepts
  garbage GlobalIDs.
- Singular `__tablename__` — the registry name and `get_entity` calls depend
  on it.
- API/worker app lists drift — a service loaded by one process and not the
  other fails only at runtime.
- Forgetting to regenerate the front's GraphQL schema after a webservice
  change — the front relay compile then validates against a stale schema.
