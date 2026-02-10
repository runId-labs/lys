# Creating an App

This guide covers how to create, structure, and register a Lys application module.

## App Structure

A Lys app is a Python package containing one or more **modules**, each providing up to five component types: entities, services, fixtures, nodes, and webservices.

```
my_apps/
└── catalog/
    ├── __init__.py
    ├── consts.py                 # App-level constants (optional)
    ├── permissions.py            # Custom permission classes (optional)
    └── modules/
        ├── __init__.py           # Declares __submodules__
        ├── product/
        │   ├── __init__.py
        │   ├── entities.py       # SQLAlchemy models
        │   ├── services.py       # Business logic
        │   ├── fixtures.py       # Seed data
        │   ├── nodes.py          # GraphQL types
        │   ├── webservices.py    # Queries and mutations
        │   ├── inputs.py         # Pydantic input models (optional)
        │   ├── models.py         # Additional data models (optional)
        │   └── consts.py         # Module constants (optional)
        └── category/
            ├── __init__.py
            ├── entities.py
            ├── services.py
            ├── fixtures.py
            ├── nodes.py
            └── webservices.py
```

## Declaring Submodules

Each app must declare its submodules in `modules/__init__.py` via the `__submodules__` list. This controls which modules are loaded and in what order.

```python
# my_apps/catalog/modules/__init__.py
from . import category
from . import product

__submodules__ = [
    category,   # Loaded first (product may depend on category)
    product,
]
```

The order matters: modules listed first are loaded before later ones. If `product` entities reference `category` via a foreign key, `category` should appear first.

## Component Types

Each module can provide any combination of these component files:

| File | Component Type | Purpose |
|------|---------------|---------|
| `entities.py` | ENTITIES | SQLAlchemy models (database tables) |
| `services.py` | SERVICES | Business logic, CRUD operations |
| `fixtures.py` | FIXTURES | Seed data for initialization |
| `nodes.py` | NODES | GraphQL type definitions (Strawberry) |
| `webservices.py` | WEBSERVICES | GraphQL queries and mutations |

Files are optional. A module only needs the components relevant to its purpose.

## Component Loading Order

Lys loads components in a strict order across **all apps**:

```
1. ENTITIES      ─── All apps' entities are loaded, then the registry is locked
2. SERVICES      ─── All apps' services are loaded, then locked
3. FIXTURES      ─── All apps' fixtures are registered, then locked
4. NODES         ─── All apps' nodes are loaded, then locked
5. WEBSERVICES   ─── All apps' webservices are loaded, then locked
```

Within each component type, apps are loaded in the order they appear in `settings.apps`, and submodules are loaded in `__submodules__` order.

This means all entities from all apps are available before any service is loaded. All services are available before any fixture is registered, and so on.

## Registering an App

Register your app by adding its module path to the `apps` list in settings:

```python
# settings.py
app_settings.configure(
    apps=[
        # Lys built-in apps (loaded first)
        "lys.apps.base",
        "lys.apps.user_auth",
        "lys.apps.user_role",
        "lys.apps.organization",
        # Your apps
        "my_apps.catalog",
        "my_apps.analytics",
    ],
)
```

## Component Registration

Each component type uses a decorator that registers it in the global registry:

```python
# entities.py
from lys.core.registries import register_entity

@register_entity()
class Product(Entity):
    __tablename__ = "product"
```

```python
# services.py
from lys.core.registries import register_service

@register_service()
class ProductService(EntityService["Product"]):
    pass
```

```python
# nodes.py
from lys.core.registries import register_node

@register_node()
class ProductNode(EntityNode["ProductService"], relay.Node):
    id: relay.NodeID[str]
```

```python
# fixtures.py
from lys.core.registries import register_fixture

@register_fixture()
class ProductCategoryFixtures(EntityFixtures["ProductCategoryService"]):
    data_list = [...]
```

```python
# webservices.py
from lys.core.graphql.registries import register_query, register_mutation

@register_query()
@strawberry.type
class ProductQuery(Query):
    pass

@register_mutation()
@strawberry.type
class ProductMutation(Mutation):
    pass
```

## Registry Locking

After all components of a given type are loaded, the registry is **locked** for that type. No more registrations are allowed. This prevents accidental late registrations and ensures deterministic behavior.

## Last-Registered-Wins Override

When two apps register the same component name (e.g., the same webservice), the **last registered version wins**. This enables app composition:

```python
# settings.py
apps=[
    "lys.apps.organization",     # Defines "create_client" webservice
    "my_apps.custom_org",        # Overrides "create_client" with custom logic
]
```

The same pattern applies to nodes: if app B registers a `UserNode` after app A, all references to `UserNode` in the schema are updated to use app B's version.

This is how business apps extend or customize built-in Lys apps without modifying framework code.

## Controlling Component Types

Use `configure_component_types()` to control which components are loaded. This is useful for workers or specialized services that don't need the full stack:

```python
from lys.core.consts.component_types import AppComponentTypeEnum

# API server: load everything
app_manager.configure_component_types([
    AppComponentTypeEnum.ENTITIES,
    AppComponentTypeEnum.SERVICES,
    AppComponentTypeEnum.FIXTURES,
    AppComponentTypeEnum.NODES,
    AppComponentTypeEnum.WEBSERVICES,
])

# Celery worker: only entities and services
app_manager.configure_component_types([
    AppComponentTypeEnum.ENTITIES,
    AppComponentTypeEnum.SERVICES,
])
```

## Minimal App Example

Here is a complete minimal app with one module:

**`my_apps/hello/__init__.py`**:
```python
```

**`my_apps/hello/modules/__init__.py`**:
```python
from . import greeting

__submodules__ = [greeting]
```

**`my_apps/hello/modules/greeting/entities.py`**:
```python
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from lys.core.entities import ParametricEntity
from lys.core.registries import register_entity

@register_entity()
class GreetingType(ParametricEntity):
    __tablename__ = "greeting_type"
```

**`my_apps/hello/modules/greeting/services.py`**:
```python
from lys.core.services import EntityService
from lys.core.registries import register_service

@register_service()
class GreetingService(EntityService["GreetingType"]):
    pass
```

**`my_apps/hello/modules/greeting/fixtures.py`**:
```python
from lys.core.fixtures import EntityFixtures
from lys.core.models.fixtures import ParametricEntityFixturesModel
from lys.core.registries import register_fixture

@register_fixture()
class GreetingFixtures(EntityFixtures["GreetingService"]):
    model = ParametricEntityFixturesModel
    data_list = [
        {"id": "HELLO", "attributes": {"enabled": True, "description": "Standard greeting."}},
        {"id": "GOODBYE", "attributes": {"enabled": True, "description": "Farewell greeting."}},
    ]
```

**`my_apps/hello/modules/greeting/nodes.py`**:
```python
from lys.core.graphql.nodes import parametric_node
from lys.core.registries import register_node

@register_node()
@parametric_node(GreetingService)
class GreetingTypeNode:
    pass
```

**`my_apps/hello/modules/greeting/webservices.py`**:
```python
import strawberry
from sqlalchemy import select
from lys.core.graphql.types import Query
from lys.core.graphql.registries import register_query
from lys.core.graphql.connection import lys_connection

@register_query()
@strawberry.type
class GreetingQuery(Query):
    @lys_connection(
        GreetingTypeNode,
        is_public=True,
        description="List all greeting types."
    )
    async def all_greetings(self, info) -> select:
        entity = info.context.app_manager.get_entity("greeting_type")
        return select(entity).order_by(entity.id.asc())
```

Register it:

```python
app_settings.configure(
    apps=[
        "lys.apps.base",
        "my_apps.hello",
    ],
)
```

## Next Steps

- [Entities and Services](entities-and-services.md) — defining models and business logic
- [GraphQL API](graphql-api.md) — building queries, mutations, and nodes
- [Permissions](permissions.md) — access control and row-level filtering
