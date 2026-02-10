# Entities and Services

This guide covers how to define database models (entities) and business logic (services) in Lys.

## Entity Types

Lys provides two base entity classes:

| Class | Primary Key | Use Case |
|-------|-------------|----------|
| `Entity` | Auto-generated UUID | Business objects (users, orders, products) |
| `ParametricEntity` | Business-meaningful string | Reference data (statuses, categories, types) |

## Entity

`Entity` is the base class for all business objects. It provides:

- **UUID primary key** (`id`) — auto-generated
- **Audit timestamps** — `created_at` (auto-set), `updated_at` (auto-set on change)
- **Access control methods** — for row-level permission filtering

```python
from sqlalchemy import Uuid, String, Numeric, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, declared_attr, relationship
from lys.core.entities import Entity
from lys.core.registries import register_entity


@register_entity()
class Product(Entity):
    __tablename__ = "product"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    description: Mapped[str | None] = mapped_column(nullable=True)

    # Hard FK to parametric entity (same database)
    category_id: Mapped[str] = mapped_column(
        ForeignKey("product_category.id"), nullable=False
    )

    # Soft FK to another service's entity (no FK constraint)
    client_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), nullable=False,
        comment="Client reference (soft FK)"
    )

    # Relationship to parametric entity
    @declared_attr
    def category(self):
        return relationship("product_category", foreign_keys=[self.category_id])

    # Indexes
    __table_args__ = (
        Index("ix_product_client", "client_id"),
        Index("ix_product_category", "category_id"),
    )
```

### UUID Fields

All ID fields in `Entity` subclasses that reference other entities must use `Uuid(as_uuid=False)`:

```python
# Soft FK fields — no ForeignKey constraint, UUID-validated
client_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), nullable=False)
owner_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), nullable=True)
```

This ensures the database validates UUID format at insert/update time, catching invalid data early. The `as_uuid=False` keeps the value as a string for JSON serialization.

**Exception:** `ParametricEntity` subclasses use plain string IDs, not UUIDs.

### Hard FK vs Soft FK

| Type | When to Use | SQLAlchemy |
|------|-------------|------------|
| **Hard FK** | Same database, same service | `ForeignKey("table.id")` |
| **Soft FK** | Cross-service, cross-database | `Uuid(as_uuid=False)`, no ForeignKey |

Hard FKs are used for relationships within the same app (e.g., product → category). Soft FKs are used for references to entities managed by other services (e.g., product → client).

### Sensitive Entities

For entities containing private data (personal information, credentials), set the `_sensitive` flag. Access attempts to sensitive entities are logged for audit purposes.

```python
@register_entity()
class UserPrivateData(Entity):
    __tablename__ = "user_private_data"
    _sensitive = True

    social_security_number: Mapped[str] = mapped_column(nullable=False)
```

### Access Control Methods

Entities implement these methods for row-level permission filtering. See the [Permissions guide](permissions.md) for details.

```python
@register_entity()
class Product(Entity):
    __tablename__ = "product"

    client_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), nullable=False)
    owner_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), nullable=True)

    def accessing_users(self) -> list[str]:
        """User IDs with direct access to this entity."""
        if self.owner_id:
            return [self.owner_id]
        return []

    def accessing_organizations(self) -> dict[str, list[str]]:
        """Organization hierarchy that can access this entity."""
        return {"client": [self.client_id]}

    @classmethod
    def user_accessing_filters(cls, stmt, user_id):
        """SQLAlchemy filter for owner-based access."""
        return stmt, [cls.owner_id == user_id]

    @classmethod
    def organization_accessing_filters(cls, stmt, organization_id_dict):
        """SQLAlchemy filter for organization-based access."""
        return stmt, [cls.client_id.in_(organization_id_dict.get("client", []))]
```

## ParametricEntity

`ParametricEntity` is for reference/configuration data with business-meaningful string IDs. These entities are shared across all tenants.

```python
from lys.core.entities import ParametricEntity
from lys.core.registries import register_entity


@register_entity()
class ProductCategory(ParametricEntity):
    """Product categories: ELECTRONICS, CLOTHING, BOOKS, etc."""
    __tablename__ = "product_category"
```

`ParametricEntity` inherits from `Entity` but overrides:

- **`id`** — plain string primary key (not UUID)
- **`enabled`** — boolean flag to activate/deactivate
- **`description`** — human-readable description
- **`code`** — property alias for `id` (avoids GraphQL encoding)

Use `ParametricEntity` for:
- Statuses (ACTIVE, SUSPENDED, DELETED)
- Types (STANDARD, EXPRESS, PRIORITY)
- Categories (ELECTRONICS, CLOTHING, BOOKS)
- Any enumeration that needs to be stored in the database

### Using Parametric Values

```python
# In business logic
if product.category.code == "ELECTRONICS":
    apply_electronics_rules(product)

# In queries
stmt = select(Product).where(Product.category_id == "ELECTRONICS")
```

## EntityService

`EntityService[T]` provides CRUD operations for an entity type. It is the base class for all service logic.

```python
from lys.core.services import EntityService
from lys.core.registries import register_service


@register_service()
class ProductService(EntityService["Product"]):
    """Service for product operations."""
    pass  # Inherits full CRUD from EntityService
```

### Built-in CRUD Methods

`EntityService` provides these methods out of the box:

```python
# Get by ID
product = await ProductService.get_by_id(product_id, session)

# Get all (with pagination)
products = await ProductService.get_all(session, limit=50, offset=0)

# Get multiple by IDs
products = await ProductService.get_multiple_by_ids(["id1", "id2"], session)

# Create
product = await ProductService.create(session, name="Widget", price=9.99, category_id="ELECTRONICS", client_id=client_id)

# Update
product = await ProductService.update(product_id, session, price=12.99)

# Delete
success = await ProductService.delete(product_id, session)

# Check and update (only updates if values changed)
product, was_updated = await ProductService.check_and_update(product, name="New Name", price=12.99)
```

### Adding Custom Methods

Add business logic by defining class methods:

```python
@register_service()
class ProductService(EntityService["Product"]):

    @classmethod
    async def search(cls, session, query: str, category_id: str | None = None) -> list:
        """Search products by name with optional category filter."""
        stmt = select(cls.entity_class).where(
            cls.entity_class.name.ilike(f"%{query}%")
        )
        if category_id:
            stmt = stmt.where(cls.entity_class.category_id == category_id)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @classmethod
    async def apply_discount(cls, session, product_id: str, percentage: float):
        """Apply a percentage discount to a product."""
        product = await cls.get_by_id(product_id, session)
        if product is None:
            raise ValueError("Product not found")
        product.price = product.price * (1 - percentage / 100)
        return product
```

### Accessing Other Entities and Services

Use `cls.app_manager` to access entities and services from other apps. Never import them directly.

```python
@register_service()
class OrderService(EntityService["Order"]):

    @classmethod
    async def create_order(cls, session, user_id: str, product_ids: list[str]):
        # Access another service
        product_service = cls.app_manager.get_service("product")
        products = await product_service.get_multiple_by_ids(product_ids, session)

        # Access another entity class
        order_item_entity = cls.app_manager.get_entity("order_item")

        # Use current entity class via shortcut
        order = cls.entity_class(user_id=user_id, total=sum(p.price for p in products))
        session.add(order)
        await session.flush()

        for product in products:
            item = order_item_entity(order_id=order.id, product_id=product.id, price=product.price)
            session.add(item)

        return order
```

### Why app_manager?

Direct imports of entities break the component registration system:

```python
# WRONG — breaks the architecture
from my_apps.catalog.modules.product.entities import Product
product = await session.get(Product, product_id)  # May fail

# CORRECT — uses the registered entity
product_entity = cls.app_manager.get_entity("product")
product = await session.get(product_entity, product_id)
```

The app_manager resolves the correct entity/service class from the registry, which handles overrides (last-registered-wins) and ensures proper SQLAlchemy mapper configuration.

### Service Properties

| Property | Description |
|----------|-------------|
| `cls.entity_class` | The registered entity class for this service |
| `cls.app_manager` | The global `AppManager` instance |
| `cls.service_name` | Auto-resolved name from the generic type parameter |

### Lifecycle Hooks

Services can implement startup and shutdown hooks:

```python
@register_service()
class CacheService(EntityService["CacheEntry"]):

    @classmethod
    async def on_initialize(cls):
        """Called at app startup, after all components are registered."""
        cls._cache = {}
        await cls._warm_cache()

    @classmethod
    async def on_shutdown(cls):
        """Called at app shutdown."""
        cls._cache.clear()
```

### Parallel Execution

For independent queries that can run concurrently:

```python
@classmethod
async def get_dashboard_data(cls, user_id: str):
    results = await cls.execute_parallel(
        lambda session: cls._get_recent_orders(session, user_id),
        lambda session: cls._get_favorite_products(session, user_id),
        lambda session: cls._get_notifications(session, user_id),
    )
    return {
        "recent_orders": results[0],
        "favorites": results[1],
        "notifications": results[2],
    }
```

Each function receives its own database session and runs in parallel.

## Field Validation

`EntityService.create()` and `EntityService.update()` validate fields against the entity schema. If a field doesn't exist on the entity, it is silently filtered out. This prevents mass-assignment attacks.

```python
# Only "name" and "price" are saved; "is_admin" is ignored
product = await ProductService.create(
    session,
    name="Widget",
    price=9.99,
    is_admin=True,  # Filtered out — not a field on Product
)
```

## Fixtures

Fixtures load seed data at application startup. See the [Creating an App](creating-an-app.md#minimal-app-example) guide for a basic example.

### Parametric Fixtures

For `ParametricEntity` types — always loaded regardless of environment:

```python
from lys.core.fixtures import EntityFixtures
from lys.core.models.fixtures import ParametricEntityFixturesModel
from lys.core.registries import register_fixture


@register_fixture()
class ProductCategoryFixtures(EntityFixtures["ProductCategoryService"]):
    model = ParametricEntityFixturesModel
    delete_previous_data = False  # Add without removing existing data

    data_list = [
        {"id": "ELECTRONICS", "attributes": {"enabled": True, "description": "Electronic devices."}},
        {"id": "CLOTHING", "attributes": {"enabled": True, "description": "Apparel and fashion."}},
        {"id": "BOOKS", "attributes": {"enabled": True, "description": "Physical and digital books."}},
    ]
```

Parametric fixtures use a **disable strategy**: when `delete_previous_data=True`, existing values not in `data_list` are set to `enabled=False` instead of being deleted. This preserves referential integrity.

### Business Fixtures

For `Entity` types — loaded only in specific environments:

```python
from lys.core.consts.environments import EnvironmentEnum

@register_fixture()
class DemoProductFixtures(EntityFixtures["ProductService"]):
    model = EntityFixturesModel
    _allowed_envs = [EnvironmentEnum.DEV, EnvironmentEnum.DEMO]
    delete_previous_data = True  # Clean slate in dev/demo

    data_list = [
        {"id": "product-1", "attributes": {"name": "Sample Widget", "price": 9.99, "category_id": "ELECTRONICS", "client_id": "demo-client-id"}},
    ]
```

Business fixtures are never loaded in production, even if listed in `_allowed_envs`.

### Fixture Dependencies

Use `depends_on` to control loading order:

```python
@register_fixture(depends_on=["ProductCategoryFixtures"])
class DemoProductFixtures(EntityFixtures["ProductService"]):
    # Loaded after ProductCategoryFixtures
    data_list = [...]
```

### Custom Attribute Formatting

Define `format_*` methods to transform attributes before entity creation:

```python
@register_fixture()
class UserFixtures(EntityFixtures["UserService"]):
    data_list = [
        {"id": "user-1", "attributes": {"email": "admin@example.com", "password": "plaintext123"}},
    ]

    @classmethod
    async def format_password(cls, value: str) -> str:
        """Hash password before storing."""
        import bcrypt
        return bcrypt.hashpw(value.encode(), bcrypt.gensalt()).decode()
```

### Custom Entity Creation

Override `create_from_service()` to use a service method instead of direct instantiation:

```python
@register_fixture()
class ClientFixtures(EntityFixtures["ClientService"]):
    @classmethod
    async def create_from_service(cls, attributes, session):
        client_service = cls.app_manager.get_service("client")
        return await client_service.create_with_owner(
            name=attributes["name"],
            owner_email=attributes["owner_email"],
            session=session,
        )

    data_list = [
        {"id": "client-1", "attributes": {"name": "Acme Corp", "owner_email": "owner@acme.com"}},
    ]
```

### Fixture Merging (Extending Base Apps)

Use `delete_previous_data=False` to add data to an existing table without removing base app data:

```python
# lys.apps.base defines AccessLevelFixtures with: OWNER
# Your app extends it:

@register_fixture()
class AccessLevelFixtures(EntityFixtures["AccessLevelService"]):
    delete_previous_data = False  # Don't remove base data

    data_list = [
        {"id": "DEPARTMENT_ADMIN", "attributes": {"enabled": True, "description": "Department administrator."}},
    ]
```

Result: the table contains both `OWNER` (from base) and `DEPARTMENT_ADMIN` (from your app).

## Next Steps

- [GraphQL API](graphql-api.md) — exposing entities via GraphQL nodes and webservices
- [Permissions](permissions.md) — controlling access with roles and organizations
