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

## Weakest spots to double-check (empirical)

- `Uuid(as_uuid=False)` on every soft FK — one forgotten and the DB accepts
  garbage GlobalIDs.
- Singular `__tablename__` — the registry name and `get_entity` calls depend
  on it.
- API/worker app lists drift — a service loaded by one process and not the
  other fails only at runtime.
- Forgetting to regenerate the front's GraphQL schema after a webservice
  change — the front relay compile then validates against a stale schema.
