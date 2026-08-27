# Services (back)

A service = business logic over one entity. Stateless class-based, all methods
`@classmethod`, registered by entity name.

## Definition

```python
from lys.core.services import EntityService
from lys.core.registries import register_service


@register_service()
class ProductService(EntityService["Product"]):
    pass   # full CRUD inherited
```

Properties: `cls.entity_class`, `cls.app_manager`, `cls.service_name`.

## Built-in CRUD (async classmethods, session passed in)

`get_by_id(id, session)` · `get_all(session, limit=50, offset=0)` ·
`get_multiple_by_ids([…], session)` · `create(session, **fields)` ·
`update(id, session, **fields)` · `delete(id, session)` ·
`check_and_update(obj, **fields) → (entity, was_updated)`.

`create`/`update` **validate fields against the entity schema** — unknown
fields are silently filtered (mass-assignment protection). Do not fight it.

## RULES

- **R1 — Sessions are arguments, never stored.** Every method takes the
  `AsyncSession`; GraphQL gives you `info.context.session`; parallel work uses
  `cls.execute_parallel(lambda session: …, …)` (one session per branch).
- **R2 — Cross-component access via the manager ONLY**:
  ```python
  entity = cls.app_manager.get_entity("client")        # ✅
  service = cls.app_manager.get_service("emailing")    # ✅
  own = cls.entity_class                               # ✅ shortcut in your own service
  ```
  Direct imports break overrides, SQLAlchemy inspection and Celery workers —
  see `rules.md` (typing exception included).
- **R3 — Lifecycle hooks**: `async def on_initialize(cls)` / `on_shutdown(cls)`
  run in EVERY process loading the app (api AND worker). Keep them idempotent
  (safe to run many times) and side-effect-light.
- **R4 — Business rules in services, not in webservices.** A webservice
  resolves + converts; the invariants (uniqueness, state transitions,
  computations) live in the service so the worker and the API share them.
- **R5 — Custom methods are classmethods**, session-first or id-first
  signature, returning entities (not nodes — conversion is the node layer's
  job).

## PROCEDURE — add business method

```python
@register_service()
class ProductService(EntityService["Product"]):
    @classmethod
    async def archive_expired(cls, client_id: str, session: AsyncSession) -> int:
        entity = cls.app_manager.get_entity("product")
        service = cls.app_manager.get_service("job")      # cross-app access, R2
        stmt = select(entity).where(entity.client_id == client_id, entity.expired_at.is_not(None))
        result = await session.execute(stmt)
        products = result.scalars().all()
        for product in products:
            product.archived = True
        await session.flush()
        return len(products)
```

Then: expose it through a webservice (`webservice.md`) or call from a task —
never import the service class to call it.

## Overriding a lys service

Last-registered-wins: re-register the same name (subclass the lys service, keep
the `@register_service()` + same generic) in a project app loaded after lys
apps. Only override when you must change behavior lys doesn't parameterize.
