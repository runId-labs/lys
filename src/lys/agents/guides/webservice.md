# Webservices — queries and mutations (back)

A webservice = one GraphQL field. Declared on a strawberry type registered
with `@register_query()` / `@register_mutation()`, built with one of the five
operation decorators that handle resolution, permissions and conversion.

## The five operation decorators

| Decorator | For | Your function returns |
|-----------|-----|----------------------|
| `lys_getter(Node, …)` | fetch one by GlobalID | nothing — validate only; `(self, obj, info)` receives the resolved entity |
| `lys_connection(Node)` | paginated Relay list | a `sqlalchemy.Select` (the decorator paginates/filters/sorts it) |
| `lys_creation(Node)` | create | the created entity — `(self, inputs, info)` |
| `lys_edition(Node, InputType)` | update | the updated entity — `(self, obj, inputs, info)` |
| `lys_delete(Node)` | delete | nothing — `(self, obj, info)` for cleanup only |

Common parameters: `ensure_type` (the node, positional), `is_public=False`,
`access_levels=None`, `is_licenced=True`, `enabled=True`, `allow_override=False`,
`description` (GraphQL doc).

## RULES

- **R1 — Webservices are thin.** Resolve (`info.context.app_manager.get_service(…)`,
  `info.context.session`), call a service method, return. Invariants live in
  services (`service.md` R4).
- **R2 — Access control is declarative**: `is_public` / `access_levels` /
  `is_licenced` on the decorator + the global permission chain in settings.
  Levels combine with OR: `access_levels=[ROLE_ACCESS_LEVEL, ORGANIZATION_ROLE_ACCESS_LEVEL]`.
  Never hand-roll "if user is admin" inside a webservice.
- **R3 — Inputs are two-step**: pydantic model in `models.py` (validation,
  `Field` constraints) → strawberry input in `inputs.py`
  (`@strawberry.experimental.pydantic.input(model=…)`), converted with
  `inputs.to_pydantic()` in the webservice.
- **R4 — The webservice NAME is its identity** (registry key, permission
  reference, front `mainWebserviceName`). Name it `verb_subject` in snake_case
  (`create_product`, `all_products`) and never rename without updating front
  references.
- **R5 — Chatbot tools**: a webservice becomes an LLM tool with
  `options={"generate_tool": True}` — see `ai.md`.
- **R5b — After adding/changing a webservice**: regenerate the GraphQL schema
  consumed by the front, using your project's schema-export tooling —
  relay-compiler validates every front operation against it.
- **R6 — Frontend webservice_name gating**: private pages declare
  `mainWebserviceName` = this webservice's name; the JWT `webservices` claim and
  role webservice lists reference these exact names.
- **R7 — A `ROLE` / `ORGANIZATION_ROLE` webservice is unreachable until a role
  grants it**: the name must also appear in `role_webservices` of a role fixture,
  and the server must restart for that fixture change to take effect
  (`fixtures.md`). Nothing fails at build time — the symptom is a silent 403 /
  empty screen. See `rules.md` for the "ask which role" process rule.

## PROCEDURE — query (connection)

```python
import strawberry
from sqlalchemy import select
from lys.core.graphql.connection import lys_connection
from lys.core.graphql.registries import register_query
from lys.core.graphql.types import Query


@register_query()
class ProductQuery(Query):
    @lys_connection(ProductNode, description="List products for the focused client.")
    async def all_products(self, info: strawberry.Info, client_id: str | None = None) -> select:
        entity = info.context.app_manager.get_entity("product")
        stmt = select(entity)
        if client_id is not None:
            stmt = stmt.where(entity.client_id == client_id)
        return stmt
```

## PROCEDURE — mutation (creation)

```python
@register_mutation()
class ProductMutation(Mutation):
    @lys_creation(ProductNode, description="Create a product.")
    async def create_product(self, info: strawberry.Info, inputs: CreateProductInput) -> "Product":
        service = info.context.app_manager.get_service("product")
        return await service.create(session=info.context.session, **inputs.to_pydantic().model_dump())
```

## Context cheatsheet

`info.context.session` (AsyncSession) · `info.context.app_manager` ·
`info.context.connected_user` (JWT claims) · `info.context.access_type` ·
`info.context.webservice_name` · `info.context.service_caller`.

## Tweaking an existing lys webservice

Metadata only → `override_webservice(name, …)` / `disable_webservice(name)` from
`lys.core.registries`. Behavior → re-register a same-named webservice in a
project app loaded after lys (last-registered-wins).
