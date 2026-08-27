# GraphQL nodes (back)

Nodes = GraphQL types exposed in the schema. Backed by an entity service
(`EntityNode[T]`), auto-generated for parametric entities (`@parametric_node`),
or free-form for custom payloads (`ServiceNode`).

## Standard entity node

```python
import strawberry
from strawberry import relay
from lys.core.graphql.nodes import EntityNode
from lys.core.registries import register_node


@register_node()
class ProductNode(EntityNode["ProductService"], relay.Node):
    id: relay.NodeID[str]                      # Relay Global ID
    name: str                                  # auto-mapped from the entity by from_obj()
    _entity: strawberry.Private["Product"]     # backing entity (never in the schema)
```

## RULES

- **R1 — Fields are plain data mapped from the entity.** Computed/relational
  fields are `@strawberry.field` resolvers, kept lazy.
- **R2 — Soft FK ids become GlobalIDs**:
  ```python
  @strawberry.field
  def client_id(self) -> relay.GlobalID:
      return relay.GlobalID("ClientNode", self._entity.client_id)
  ```
  (Node TYPE name first argument, raw entity id second.)
- **R3 — Lazy relations** instead of eager joins:
  `await self._lazy_load_relation("category", ProductCategoryNode, info)` /
  `_lazy_load_relation_list(…)` — loads only when the field is requested.
- **R4 — Sortable connections**: implement `order_by_attribute_map` as a
  `@classproperty` mapping GraphQL field names → entity columns; this is what
  generates the `order_by` argument on `lys_connection` queries.
- **R5 — No DB sessions inside node resolvers**: fetch through services
  (`info.context.app_manager`) — resolvers may open `info.context.session`
  usage via services only.
- **R6 — Register** with `@register_node()`; never import a node from another
  module (same registry rule as services — reference by class inside the same
  module or by string name).

## Parametric node (one-liner)

```python
from lys.core.graphql.nodes import parametric_node

@register_node()
@parametric_node(ProductStatusService)
class ProductStatusNode:
    pass    # id/code/enabled/description/created_at/updated_at auto-generated
```

## Extending an existing node — subclass it (do NOT rewrite)

Lys supports node extension **by inheritance**: to add fields to a lys node,
subclass the existing node class and register the subclass under the same
name — last-registered-wins replaces the base, and inherited fields,
resolvers and `order_by_attribute_map` keep working (lys resolves inherited
annotations in `from_obj` and decorates ancestor classes at registration).

Reference implementation (verified end to end):
`lys/apps/licensing/modules/client/nodes.py` subclasses the organization
`ClientNode`, inherits `id/name/created_at/updated_at/owner_id/open_requests`
and adds `subscription`/`license_plan` — a lys-only project gets the full
merged node with no project-side override.

```python
from lys.apps.organization.modules.client.nodes import ClientNode as OrganizationClientNode
from lys.core.registries import register_node


@register_node()
class ClientNode(OrganizationClientNode):
    """Inherits the base fields; adds licensing fields."""
    # Redeclare _entity (private back-reference used by resolvers)
    _entity: strawberry.Private["Client"]

    @strawberry.field(description="Current subscription for this client")
    async def subscription(self, info: Info) -> Optional[SubscriptionNode]:
        ...
```

RULES:

- **R-ext1 — Subclass, don't copy.** Redeclare only `_entity` and your new
  fields/resolvers. Copying the whole base body reintroduces the drift the
  inheritance removed (a field added to the base later would vanish from
  your copy).
- **R-ext2 — Registration name replaces.** The subclass must keep the same
  class name (the registry key) and your app must load AFTER the app that
  declares the base (project apps load after lys apps by convention).
- **R-ext3 — Diff the schema after any node override** — replacement is
  still silent: run your project's schema-export tooling and compare, a
  missing field is otherwise invisible until a front query stops compiling.
- **R-ext4 — Importing the base node class from the other app's `nodes.py`
  is the sanctioned pattern** (the import-linter contract forbids
  entities/services imports, not nodes).
- **R-ext5 — Legacy**: full field-by-field rewrites of a lys node predate
  inheritance support and still exist in some projects — do not copy that
  pattern in new code; subclass instead.

## ✅ / ❌

| ✅ | ❌ |
|----|----|
| `relay.GlobalID("ClientNode", self._entity.client_id)` | Returning the raw UUID string for a cross-entity reference |
| Subclass the base node + schema diff against the previous export | Copy-pasting the whole node body to add one field (drift) |
| `_lazy_load_relation_list("reviews", ReviewNode, info)` | A JOIN baked into every parent fetch |
| `order_by_attribute_map` on nodes exposed in lists | Front-side sorting of a full unpaginated list |
