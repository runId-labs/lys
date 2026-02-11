# Lys

![Coverage](https://img.shields.io/badge/coverage-77%25-green)
![Python](https://img.shields.io/badge/python-3.13+-blue)
![License](https://img.shields.io/badge/license-Apache%202.0-blue)

A modular Python framework for building GraphQL APIs with FastAPI and SQLAlchemy, inspired by Django's app architecture.

Lys provides a component-based system where each application module is self-contained and can be deployed as part of a monolith or extracted into its own microservice.

## Features

- **Modular app system** with automatic component discovery and registration
- **GraphQL API** via Strawberry with Relay support (Global IDs, cursor pagination)
- **Async SQLAlchemy** with PostgreSQL, SQLite, and MySQL support
- **JWT authentication** with refresh tokens, XSRF protection, and rate limiting
- **Permission system** with role-based, organization-based, and row-level access control
- **Multi-tenant architecture** with organization-scoped data filtering
- **Microservice-ready** with service-to-service JWT authentication
- **Celery integration** for background tasks and periodic jobs
- **Fixture system** with dependency resolution and environment-based loading

## Requirements

- Python >= 3.13
- PostgreSQL (production) or SQLite (development/testing)
- Redis (for Celery workers and rate limiting)

## Installation

```bash
pip install lys
```

For optional features:

```bash
pip install lys[storage]   # S3 file storage (aioboto3)
pip install lys[mollie]    # Mollie payment integration
pip install lys[dev]       # Development and testing tools
```

## Quick Start

### 1. Project Structure

A Lys project consists of a **server project** that configures and runs the framework, and one or more **app packages** that contain your business logic.

```
my-project/
├── settings.py              # App registration, database, plugins
├── main.py                  # CLI entry point (Typer)
├── src/
│   └── app.py               # FastAPI application factory
├── .env                     # Environment variables
└── pyproject.toml
```

### 2. Create an App

Apps follow a consistent structure. Each module contains up to five component types: entities, services, fixtures, nodes, and webservices.

```
my_apps/
└── catalog/
    ├── __init__.py
    └── modules/
        ├── __init__.py          # Declares __submodules__
        └── product/
            ├── __init__.py
            ├── entities.py      # SQLAlchemy models
            ├── services.py      # Business logic
            ├── fixtures.py      # Seed data
            ├── nodes.py         # GraphQL types
            └── webservices.py   # Queries and mutations
```

Declare submodules in `modules/__init__.py`:

```python
from . import product

__submodules__ = [product]
```

### 3. Define an Entity

Lys provides two base entity classes:

- **`Entity`** — for business objects with auto-generated UUID primary keys
- **`ParametricEntity`** — for reference/configuration data with business-meaningful string IDs

```python
from sqlalchemy import Uuid, String, Numeric, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, declared_attr, relationship
from lys.core.entities import Entity, ParametricEntity
from lys.core.registries import register_entity


@register_entity()
class ProductCategory(ParametricEntity):
    """Reference table for product categories (ELECTRONICS, CLOTHING, etc.)."""
    __tablename__ = "product_category"


@register_entity()
class Product(Entity):
    """A product in the catalog."""
    __tablename__ = "product"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)

    # Hard FK to parametric entity
    category_id: Mapped[str] = mapped_column(
        ForeignKey("product_category.id"), nullable=False
    )

    # Soft FK to another service's entity (no FK constraint)
    client_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), nullable=False,
        comment="Client reference (soft FK)"
    )

    @declared_attr
    def category(self):
        return relationship("product_category", foreign_keys=[self.category_id])

    def accessing_organizations(self) -> dict[str, list[str]]:
        return {"client": [self.client_id]}

    @classmethod
    def organization_accessing_filters(cls, stmt, organization_id_dict):
        filters = [cls.client_id.in_(organization_id_dict.get("client", []))]
        return stmt, filters
```

> **Rule:** All soft FK fields in `Entity` subclasses must use `Uuid(as_uuid=False)` for database-level UUID validation. `ParametricEntity` subclasses use plain string IDs.

### 4. Define a Service

Services contain business logic and CRUD operations. They are accessed exclusively through `app_manager`.

```python
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from lys.core.services import EntityService
from lys.core.registries import register_service


@register_service()
class ProductCategoryService(EntityService["ProductCategory"]):
    """Service for product category reference data."""
    pass  # Inherits full CRUD from EntityService


@register_service()
class ProductService(EntityService["Product"]):
    """Service for product operations."""

    @classmethod
    async def search(
        cls, session: AsyncSession, query: str, category_id: Optional[str] = None
    ) -> list:
        stmt = select(cls.entity_class).where(
            cls.entity_class.name.ilike(f"%{query}%")
        )
        if category_id:
            stmt = stmt.where(cls.entity_class.category_id == category_id)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @classmethod
    async def update_price(
        cls, session: AsyncSession, product_id: str, new_price: float
    ):
        product = await cls.get_by_id(product_id, session)
        if product is None:
            raise ValueError("Product not found")
        product.price = new_price
        return product
```

> **Rule:** Always access entities and services through `app_manager`, never via direct imports. Use `cls.entity_class` for the current service's entity and `cls.app_manager.get_service("name")` / `cls.app_manager.get_entity("name")` for others.

### 5. Define GraphQL Nodes

Nodes map entities to GraphQL types using Strawberry.

```python
import strawberry
from strawberry import relay
from lys.core.graphql.nodes import EntityNode, parametric_node
from lys.core.registries import register_node


@register_node()
@parametric_node(ProductCategoryService)
class ProductCategoryNode:
    """Auto-generated GraphQL type for ProductCategory."""
    pass


@register_node()
class ProductNode(EntityNode["ProductService"], relay.Node):
    """GraphQL type for Product."""

    id: relay.NodeID[str]
    name: str
    price: float

    _entity: strawberry.Private["Product"]

    @strawberry.field
    def client_id(self) -> relay.GlobalID:
        return relay.GlobalID("ClientNode", self._entity.client_id)

    @strawberry.field
    def category(self) -> ProductCategoryNode:
        return self._entity.category
```

### 6. Define Webservices (Queries and Mutations)

Webservices expose GraphQL operations with built-in permission checking.

```python
import strawberry
from strawberry import relay
from typing import Optional, Annotated
from sqlalchemy import select
from lys.core.graphql.types import Query, Mutation
from lys.core.graphql.registries import register_query, register_mutation
from lys.core.graphql.getter import lys_getter
from lys.core.graphql.connection import lys_connection
from lys.core.graphql.create import lys_creation
from lys.apps.user_role.consts import ROLE_ACCESS_LEVEL
from lys.apps.organization.consts import ORGANIZATION_ROLE_ACCESS_LEVEL


@strawberry.type
@register_query()
class ProductQuery(Query):

    @lys_getter(
        ProductNode,
        access_levels=[ROLE_ACCESS_LEVEL, ORGANIZATION_ROLE_ACCESS_LEVEL],
        description="Get a product by ID."
    )
    async def product(self, obj, info):
        pass  # Handled by lys_getter

    @lys_connection(
        ProductNode,
        access_levels=[ROLE_ACCESS_LEVEL, ORGANIZATION_ROLE_ACCESS_LEVEL],
        description="List products with optional search."
    )
    async def all_products(
        self,
        info,
        search: Annotated[Optional[str], strawberry.argument(description="Search by name")] = None,
    ):
        entity = info.context.app_manager.get_entity("product")
        stmt = select(entity).order_by(entity.created_at.desc())
        if search:
            stmt = stmt.where(entity.name.ilike(f"%{search.strip()}%"))
        return stmt


@strawberry.type
@register_mutation()
class ProductMutation(Mutation):

    @lys_creation(
        ensure_type=ProductNode,
        access_levels=[ROLE_ACCESS_LEVEL],
        description="Create a new product."
    )
    async def create_product(self, inputs, info):
        input_data = inputs.to_pydantic()
        service = info.context.app_manager.get_service("product")
        return await service.create(
            info.context.session,
            name=input_data.name,
            price=input_data.price,
            category_id=input_data.category_id,
            client_id=input_data.client_id,
        )
```

### 7. Define Fixtures

Fixtures load seed data into the database, with support for environment-based filtering.

```python
from lys.core.fixtures import EntityFixtures
from lys.core.models.fixtures import ParametricEntityFixturesModel
from lys.core.registries import register_fixture


@register_fixture()
class ProductCategoryFixtures(EntityFixtures["ProductCategoryService"]):
    model = ParametricEntityFixturesModel
    delete_previous_data = False

    data_list = [
        {"id": "ELECTRONICS", "attributes": {"enabled": True, "description": "Electronic devices and accessories."}},
        {"id": "CLOTHING", "attributes": {"enabled": True, "description": "Apparel and fashion items."}},
        {"id": "BOOKS", "attributes": {"enabled": True, "description": "Physical and digital books."}},
    ]
```

### 8. Configure and Run

**settings.py** — register apps and configure services:

```python
import os
from lys.core.configs import settings as app_settings
from lys.core.consts.environments import EnvironmentEnum


def configure_app():
    app_settings.configure(
        env=EnvironmentEnum(os.getenv("ENVIRONMENT", "dev")),
        secret_key=os.getenv("SECRET_KEY"),
        front_url=os.getenv("FRONT_URL", "http://localhost:3000"),
        apps=[
            "lys.apps.base",
            "lys.apps.user_auth",
            "lys.apps.user_role",
            "lys.apps.organization",
            "my_apps.catalog",
        ],
        middlewares=[
            "lys.core.middlewares.SecurityHeadersMiddleware",
            "lys.core.middlewares.RateLimitMiddleware",
        ],
        permissions=[
            "lys.apps.base.permissions.InternalServicePermission",
            "lys.apps.user_auth.permissions.AnonymousPermission",
            "lys.apps.user_auth.permissions.JWTPermission",
            "lys.apps.organization.permissions.OrganizationPermission",
        ],
    )

    app_settings.database.configure(
        type="postgresql",
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        username=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
    )
```

**src/app.py** — create the FastAPI application:

```python
from lys.core.managers.app import LysAppManager
from lys.core.consts.component_types import AppComponentTypeEnum
from settings import configure_app

configure_app()

app_manager = LysAppManager()
app_manager.configure_component_types([
    AppComponentTypeEnum.ENTITIES,
    AppComponentTypeEnum.SERVICES,
    AppComponentTypeEnum.FIXTURES,
    AppComponentTypeEnum.NODES,
    AppComponentTypeEnum.WEBSERVICES,
])

app = app_manager.initialize_app(
    title="My API",
    description="Built with Lys",
    version="1.0.0",
)
```

**main.py** — CLI entry point:

```python
import typer
from pathlib import Path
from lys.core.clis import run_fast_app

cli = typer.Typer()

@cli.command()
def run(
    host: str = typer.Option("0.0.0.0", "--host"),
    port: int = typer.Option(8000, "--port"),
    reload: bool = typer.Option(False, "--reload"),
    workers: int = typer.Option(1, "--workers"),
):
    run_fast_app(host=host, port=port, reload=reload, workers=workers, app_path=Path("src/app.py"))

if __name__ == "__main__":
    cli()
```

Run the server:

```bash
python main.py run --reload
```

The GraphQL playground is available at `http://localhost:8000/graphql`.

## Architecture

### Component System

Lys organizes code into five component types, loaded in this order:

| Order | Component | Role | Base Class |
|-------|-----------|------|------------|
| 1 | **Entities** | SQLAlchemy models | `Entity`, `ParametricEntity` |
| 2 | **Services** | Business logic, CRUD | `EntityService[T]` |
| 3 | **Fixtures** | Seed data | `EntityFixtures[T]` |
| 4 | **Nodes** | GraphQL type definitions | `EntityNode[T]` |
| 5 | **Webservices** | Queries, mutations, endpoints | `Query`, `Mutation` |

Components are discovered automatically via the `@register_entity()`, `@register_service()`, `@register_node()`, and `@register_fixture()` decorators.

### App Manager

`LysAppManager` is the central orchestrator. It loads apps, registers components, initializes the database, and creates the FastAPI application.

All entities and services are accessed through the app manager:

```python
# Get a registered entity class
user_entity = app_manager.get_entity("user")

# Get a registered service class
user_service = app_manager.get_service("user")

# Inside a service, use cls.app_manager
class OrderService(EntityService["Order"]):
    @classmethod
    async def create_order(cls, session, user_id, items):
        product_service = cls.app_manager.get_service("product")
        # ...
```

### Monolith to Microservices

Lys apps are designed to be independently deployable. A typical evolution:

**Phase 1 — Monolith:** All apps in a single process.

```python
apps=[
    "lys.apps.base",
    "lys.apps.user_auth",
    "lys.apps.organization",
    "my_apps.catalog",
    "my_apps.analytics",
    "my_apps.billing",
]
```

**Phase 2 — Microservices:** Each app (or group of apps) in its own service. Apps communicate via GraphQL with service-to-service JWT authentication.

```
┌──────────────────┐    ┌───────────────────┐    ┌──────────────────┐
│   Auth Service   │    │ Catalog Service   │    │ Billing Service  │
│                  │    │                   │    │                  │
│ lys.apps.base    │    │ lys.apps.base     │    │ lys.apps.base    │
│ lys.apps.user_*  │    │ my_apps.catalog   │    │ my_apps.billing  │
│ lys.apps.org     │    │                   │    │                  │
└────────┬─────────┘    └────────┬──────────┘    └────────┬─────────┘
         │                       │                        │
         └───────────── GraphQL + JWT ────────────────────┘
```

Each service registers only the apps it needs. Lys handles service-to-service authentication via `InternalServicePermission` and `ServiceAuthUtils`.

## Permission System

Lys implements a layered permission system:

| Level | Description | Class |
|-------|-------------|-------|
| **Anonymous** | Public endpoints, no auth required | `AnonymousPermission` |
| **JWT** | Authenticated user with valid token | `JWTPermission` |
| **Role-based** | User has a specific role | `ROLE_ACCESS_LEVEL` |
| **Organization** | User belongs to the right organization | `ORGANIZATION_ROLE_ACCESS_LEVEL` |
| **Owner** | User owns the resource | `OWNER_ACCESS_LEVEL` |
| **Internal** | Service-to-service calls | `InternalServicePermission` |

Permissions are evaluated in chain. Each webservice declares its required access levels:

```python
@lys_getter(
    ProductNode,
    access_levels=[ROLE_ACCESS_LEVEL, ORGANIZATION_ROLE_ACCESS_LEVEL],
    is_licenced=True,
    description="Get a product."
)
```

Row-level filtering is handled by implementing `accessing_users()`, `accessing_organizations()`, and `organization_accessing_filters()` on entities.

## Celery Workers

Lys integrates with Celery for background tasks. Workers load only entities and services (no nodes or webservices).

**worker.py:**

```python
from settings import configure_app
from lys.core.configs import settings
from lys.core.celery_app import create_celery_app

configure_app()
celery_app = create_celery_app(settings)
app = celery_app
```

**Task definition:**

```python
from celery import shared_task, current_app

@shared_task
def process_catalog_import(file_id: str):
    app_manager = current_app.app_manager
    product_service = app_manager.get_service("product")

    with app_manager.database.get_sync_session() as session:
        # Process import...
        session.commit()

    return {"status": "completed"}
```

Run the worker:

```bash
celery -A worker worker --loglevel=info
```

## Configuration

### Environment Modes

| Mode | `debug` | `testing` | GraphQL Introspection | Log Level |
|------|---------|-----------|----------------------|-----------|
| `DEV` | True | True | Enabled | DEBUG |
| `DEMO` | False | False | Enabled | INFO |
| `PREPROD` | False | False | Disabled | WARNING |
| `PROD` | False | False | Disabled | ERROR |

### Database

```python
app_settings.database.configure(
    type="postgresql",        # postgresql, sqlite, mysql
    host="localhost",
    port=5432,
    username="user",
    password="password",
    database="mydb",
    pool_size=10,             # Connection pool size
    max_overflow=20,          # Extra connections allowed
    pool_pre_ping=True,       # Verify connections before use
    pool_recycle=3600,        # Recycle connections after 1 hour
    ssl_mode="require",       # PostgreSQL SSL mode
)
```

### Plugins

Lys supports plugin-based configuration for optional features:

```python
app_settings.configure(
    plugins={
        "cors": {
            "allow_origins": ["http://localhost:3000"],
            "allow_methods": ["*"],
        },
        "auth": {
            "cookie_secure": True,
            "access_token_expire_minutes": 5,
            "refresh_token_expire_hours": 24,
        },
        "file_storage": {
            "provider": "s3",
            "bucket": "my-bucket",
        },
        "rate_limit": {
            "requests_per_minute": 60,
        },
    }
)
```

## Testing

### Running Tests

```bash
# Unit tests (mocked dependencies, fast)
pytest tests/unit/ -v

# Integration tests (real database, forked for isolation)
pytest tests/integration/ --forked -v

# Combined coverage
pytest tests/unit/ --cov=src/lys --cov-report=
pytest tests/integration/ --forked --cov=src/lys --cov-append --cov-report=term-missing
```

### Test Structure

```
tests/
├── unit/                    # Mocked dependencies
│   └── apps/
│       └── catalog/
│           ├── test_product_entities.py
│           ├── test_product_services.py
│           └── test_product_services_logic.py
├── integration/             # Real DB (SQLite in-memory), forked
│   └── apps/
│       └── catalog/
│           └── test_product_service.py
└── conftest.py              # Shared fixtures
```

Integration tests run in forked subprocesses (`pytest-forked`) to isolate the SQLAlchemy registry singleton between test runs.

## Built-in Apps

Lys ships with several pre-built apps:

| App | Description |
|-----|-------------|
| `lys.apps.base` | Languages, emailing, jobs, logging, access levels, webservice management |
| `lys.apps.user_auth` | User entity, login/logout, JWT tokens, password reset, email verification |
| `lys.apps.user_role` | Role management, role-based permissions |
| `lys.apps.organization` | Multi-tenant client/organization support, organization roles |
| `lys.apps.licensing` | Subscription plans, license rules, payment integration |
| `lys.apps.file_management` | File upload/download with S3 storage, file import processing |
| `lys.apps.ai` | AI conversation management, text improvement, tool generation from GraphQL |

## Documentation

Detailed documentation is available in the `docs/` directory:

**Developer Guides:**

- [`docs/guides/creating-an-app.md`](docs/guides/creating-an-app.md) — App structure, modules, registration, and component loading
- [`docs/guides/entities-and-services.md`](docs/guides/entities-and-services.md) — Database models, business logic, CRUD, and fixtures
- [`docs/guides/graphql-api.md`](docs/guides/graphql-api.md) — Nodes, webservices, decorators, inputs, and pagination
- [`docs/guides/permissions.md`](docs/guides/permissions.md) — Authentication, authorization, and row-level access control

**Functional Specifications:**

- [`docs/FRS/auth.md`](docs/FRS/auth.md) — Authentication system (login, tokens, refresh, logout)
- [`docs/FRS/jwt_permissions.md`](docs/FRS/jwt_permissions.md) — JWT permission system and access control
- [`docs/FRS/webservice_management.md`](docs/FRS/webservice_management.md) — Webservice configuration and access levels
- [`docs/FRS/internal_service_communication.md`](docs/FRS/internal_service_communication.md) — Service-to-service authentication

## License

Apache License 2.0 — see [LICENSE](LICENSE) for details.
