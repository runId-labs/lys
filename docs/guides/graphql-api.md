# GraphQL API

This guide covers how to define GraphQL types (nodes) and operations (webservices) in Lys.

Lys uses [Strawberry GraphQL](https://strawberry.rocks/) with Relay support for Global IDs, cursor-based pagination, and node resolution.

## Table of Contents

1. [Nodes](#nodes)
2. [Webservices](#webservices)
3. [Decorators](#decorators)
4. [Input Types](#input-types)
5. [GraphQL Context](#graphql-context)
6. [Public Endpoints](#public-endpoints)
7. [Complete CRUD Example](#complete-crud-example)
8. [Next Steps](#next-steps)

## Nodes

Nodes are GraphQL type definitions that map entities to the schema.

### EntityNode

`EntityNode[T]` is the base class for nodes backed by an entity service:

```python
import strawberry
from strawberry import relay
from datetime import datetime
from typing import Optional
from lys.core.graphql.nodes import EntityNode
from lys.core.registries import register_node


@register_node()
class ProductNode(EntityNode["ProductService"], relay.Node):
    """GraphQL type for Product."""

    id: relay.NodeID[str]
    name: str
    price: float
    description: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]

    _entity: strawberry.Private["Product"]
```

Key points:
- Inherit from both `EntityNode["ServiceClass"]` and `relay.Node`
- Declare `id: relay.NodeID[str]` for Relay Global IDs
- Store the backing entity in `_entity: strawberry.Private[EntityClass]` for lazy loading
- Simple fields are auto-mapped from the entity by `from_obj()`

### Soft FK Fields as GlobalID

Convert soft FK strings to Relay Global IDs:

```python
@register_node()
class ProductNode(EntityNode["ProductService"], relay.Node):
    id: relay.NodeID[str]
    name: str

    _entity: strawberry.Private["Product"]

    @strawberry.field
    def client_id(self) -> relay.GlobalID:
        """Client reference as a Relay Global ID."""
        return relay.GlobalID("ClientNode", self._entity.client_id)
```

### Relationship Fields (Lazy Loading)

Use `_lazy_load_relation()` for single relationships and `_lazy_load_relation_list()` for collections:

```python
@register_node()
class ProductNode(EntityNode["ProductService"], relay.Node):
    id: relay.NodeID[str]
    name: str

    _entity: strawberry.Private["Product"]

    @strawberry.field
    async def category(self, info) -> "ProductCategoryNode":
        """Lazy load the category relationship."""
        return await self._lazy_load_relation("category", ProductCategoryNode, info)

    @strawberry.field
    async def reviews(self, info) -> list["ReviewNode"]:
        """Lazy load the reviews relationship."""
        return await self._lazy_load_relation_list("reviews", ReviewNode, info)
```

Lazy loading fetches the relationship data only when the field is requested in the GraphQL query.

### Parametric Nodes

For `ParametricEntity` types, use the `@parametric_node` decorator to auto-generate all fields:

```python
from lys.core.graphql.nodes import parametric_node
from lys.core.registries import register_node


@register_node()
@parametric_node(ProductCategoryService)
class ProductCategoryNode:
    """Auto-generated node for ProductCategory."""
    pass
```

This auto-generates: `id`, `code`, `enabled`, `description`, `created_at`, `updated_at`.

### ServiceNode

For nodes not backed by an entity (custom response types):

```python
from lys.core.graphql.nodes import ServiceNode


@register_node()
class ImportResultNode(ServiceNode["ProductService"]):
    success: bool
    imported_count: int
    error_count: int
    message: str
```

### Order By Support

Define sortable fields by implementing `order_by_attribute_map`:

```python
from sqlalchemy.util import classproperty

@register_node()
class ProductNode(EntityNode["ProductService"], relay.Node):
    id: relay.NodeID[str]
    name: str
    price: float

    _entity: strawberry.Private["Product"]

    @classproperty
    def order_by_attribute_map(cls) -> dict:
        entity_class = cls.service_class.entity_class
        return {
            "created_at": entity_class.created_at,
            "name": entity_class.name,
            "price": entity_class.price,
        }
```

This generates an `order_by` argument in the GraphQL schema for `lys_connection` queries.

## Webservices

Webservices define the GraphQL queries and mutations exposed in the API.

### Query Class

```python
import strawberry
from lys.core.graphql.types import Query
from lys.core.graphql.registries import register_query


@register_query()
@strawberry.type
class ProductQuery(Query):
    # Define query fields here
    pass
```

Requirements:
- Decorated with `@register_query()` and `@strawberry.type`
- Inherits from `Query`

### Mutation Class

```python
from lys.core.graphql.types import Mutation
from lys.core.graphql.registries import register_mutation


@register_mutation()
@strawberry.type
class ProductMutation(Mutation):
    # Define mutation fields here
    pass
```

## Decorators

Lys provides five decorators for GraphQL operations. Each handles database access, permissions, and response conversion automatically.

### @lys_getter — Get Single Entity

Fetches a single entity by its Relay Global ID.

```python
from lys.core.graphql.getter import lys_getter


@register_query()
@strawberry.type
class ProductQuery(Query):

    @lys_getter(
        ProductNode,
        access_levels=[ROLE_ACCESS_LEVEL, ORGANIZATION_ROLE_ACCESS_LEVEL],
        is_licenced=False,
        description="Get a product by ID."
    )
    async def product(self, obj, info):
        """Called after the entity is fetched and access-checked.

        Args:
            obj: The resolved entity (Product instance).
            info: GraphQL context.

        Use this for additional validation. The entity is already
        fetched and permission-checked.
        """
        if obj.is_archived:
            raise LysError(NOT_FOUND_ERROR, "Product is archived")
```

The decorator:
1. Resolves the `id` argument (Relay Global ID) to the entity
2. Checks permissions via the permission chain
3. Calls your function for additional validation
4. Converts the entity to a node and returns it

Parameters:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `ensure_type` | `Type[EntityNode]` | Required | The node class to return |
| `is_public` | `bool` | `False` | Whether publicly accessible without auth |
| `access_levels` | `list[str]` | `None` | Required access levels |
| `is_licenced` | `bool` | `True` | Whether requires an active license |
| `enabled` | `bool` | `True` | Whether enabled in the schema |
| `allow_override` | `bool` | `False` | Whether child apps can override |
| `description` | `str` | `None` | GraphQL documentation string |

### @lys_connection — List Entities (Paginated)

Returns a paginated list of entities using Relay cursor pagination.

```python
from typing import Optional, Annotated
from sqlalchemy import select
from lys.core.graphql.connection import lys_connection


@register_query()
@strawberry.type
class ProductQuery(Query):

    @lys_connection(
        ProductNode,
        access_levels=[ROLE_ACCESS_LEVEL, ORGANIZATION_ROLE_ACCESS_LEVEL],
        is_licenced=False,
        description="List products with optional search."
    )
    async def all_products(
        self,
        info,
        search: Annotated[
            Optional[str],
            strawberry.argument(description="Search by name")
        ] = None,
        category_id: Annotated[
            Optional[str],
            strawberry.argument(description="Filter by category code")
        ] = None,
    ):
        """Build and return a SQLAlchemy SELECT statement.

        The decorator handles:
        - Permission-based row filtering
        - Relay cursor pagination (first, last, after, before)
        - Sorting via order_by argument
        - Total count
        """
        entity = info.context.app_manager.get_entity("product")
        stmt = select(entity).order_by(entity.created_at.desc())

        if search:
            stmt = stmt.where(entity.name.ilike(f"%{search.strip()}%"))
        if category_id:
            stmt = stmt.where(entity.category_id == category_id)

        return stmt
```

Your function must return a `sqlalchemy.Select` statement. The decorator applies pagination, filtering, and sorting on top.

**Auto-injected GraphQL arguments:**

| Argument | Type | Description |
|----------|------|-------------|
| `first` | `Int` | Number of items from the start |
| `last` | `Int` | Number of items from the end |
| `after` | `String` | Cursor for forward pagination |
| `before` | `String` | Cursor for backward pagination |
| `order_by` | Dynamic | Sorting field and direction |
| `limit` | `Int` | Additional result limit |

### @lys_creation — Create Entity

Creates a new entity from input data.

```python
from lys.core.graphql.create import lys_creation


@register_mutation()
@strawberry.type
class ProductMutation(Mutation):

    @lys_creation(
        ensure_type=ProductNode,
        access_levels=[ROLE_ACCESS_LEVEL],
        is_licenced=False,
        description="Create a new product."
    )
    async def create_product(self, inputs, info):
        """Create and return a new entity.

        Args:
            inputs: Strawberry input type (use inputs.to_pydantic() to convert).
            info: GraphQL context.

        Returns:
            The created entity instance.
        """
        input_data = inputs.to_pydantic()
        product_service = info.context.app_manager.get_service("product")

        product = await product_service.create(
            info.context.session,
            name=input_data.name,
            price=input_data.price,
            category_id=input_data.category_id,
            client_id=input_data.client_id,
        )
        return product
```

The decorator:
1. Calls your function to create the entity
2. Validates the return type matches `ensure_type.entity_class`
3. Adds the entity to the session, flushes, and refreshes
4. Converts to a node and returns

### @lys_edition — Update Entity

Updates an existing entity.

```python
from lys.core.graphql.edit import lys_edition


@register_mutation()
@strawberry.type
class ProductMutation(Mutation):

    @lys_edition(
        ProductNode,
        UpdateProductInput,
        access_levels=[ROLE_ACCESS_LEVEL, ORGANIZATION_ROLE_ACCESS_LEVEL],
        is_licenced=False,
        description="Update a product."
    )
    async def update_product(self, obj, inputs, info):
        """Modify the entity.

        Args:
            obj: The fetched and access-checked entity.
            inputs: Strawberry input type with update data.
            info: GraphQL context.
        """
        input_data = inputs.to_pydantic()

        if input_data.name is not None:
            obj.name = input_data.name
        if input_data.price is not None:
            obj.price = input_data.price
```

The decorator:
1. Resolves the `id` argument to the entity
2. Checks permissions
3. Calls your function to modify the entity
4. Flushes and refreshes the entity
5. Converts to a node and returns

### @lys_delete — Delete Entity

Deletes an entity.

```python
from lys.core.graphql.delete import lys_delete


@register_mutation()
@strawberry.type
class ProductMutation(Mutation):

    @lys_delete(
        ProductNode,
        access_levels=[ROLE_ACCESS_LEVEL],
        is_licenced=False,
        description="Delete a product."
    )
    async def delete_product(self, obj, info):
        """Perform cleanup before deletion.

        Args:
            obj: The fetched and access-checked entity.
            info: GraphQL context.
        """
        # Optional cleanup (cascade deletes, file removal, etc.)
        pass
```

The decorator handles the actual deletion. Returns a `SuccessNode` with `succeed=True`.

## Input Types

Lys uses Strawberry's Pydantic integration for input validation.

### Defining Inputs

**Step 1 — Pydantic model** (in `models.py`):

```python
from pydantic import BaseModel, Field
from typing import Optional


class CreateProductInputModel(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    price: float = Field(..., gt=0)
    category_id: str
    client_id: str

class UpdateProductInputModel(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    price: Optional[float] = Field(None, gt=0)
```

**Step 2 — Strawberry input** (in `inputs.py`):

```python
import strawberry


@strawberry.experimental.pydantic.input(model=CreateProductInputModel)
class CreateProductInput:
    name: strawberry.auto = strawberry.field(description="Product name")
    price: strawberry.auto = strawberry.field(description="Product price")
    category_id: strawberry.auto = strawberry.field(description="Category code")
    client_id: strawberry.auto = strawberry.field(description="Client ID")

@strawberry.experimental.pydantic.input(model=UpdateProductInputModel)
class UpdateProductInput:
    name: strawberry.auto = strawberry.field(description="New product name")
    price: strawberry.auto = strawberry.field(description="New product price")
```

### Using Inputs in Webservices

Convert the Strawberry input to a Pydantic model with `to_pydantic()`:

```python
@lys_creation(ensure_type=ProductNode)
async def create_product(self, inputs, info):
    input_data = inputs.to_pydantic()  # Pydantic validation runs here

    product = await product_service.create(
        session,
        name=input_data.name,
        price=input_data.price,
    )
    return product
```

## GraphQL Context

Inside webservices, `info.context` provides access to:

| Property | Type | Description |
|----------|------|-------------|
| `info.context.session` | `AsyncSession` | Active database session (auto-managed) |
| `info.context.app_manager` | `AppManager` | Access to entities and services |
| `info.context.connected_user` | `dict \| None` | JWT claims of the authenticated user |
| `info.context.access_type` | `dict \| bool` | Resolved permission data |
| `info.context.webservice_name` | `str` | Name of the current webservice |
| `info.context.service_caller` | `dict \| None` | Service-to-service caller info |

## Public Endpoints

For endpoints accessible without authentication:

```python
@lys_connection(
    ProductCategoryNode,
    is_public=True,
    description="List all product categories (public)."
)
async def all_categories(self, info):
    entity = info.context.app_manager.get_entity("product_category")
    return select(entity).where(entity.enabled == True).order_by(entity.id.asc())
```

## Complete CRUD Example

```python
# webservices.py
import strawberry
from typing import Optional, Annotated
from sqlalchemy import select
from strawberry import relay
from lys.core.graphql.types import Query, Mutation
from lys.core.graphql.registries import register_query, register_mutation
from lys.core.graphql.getter import lys_getter
from lys.core.graphql.connection import lys_connection
from lys.core.graphql.create import lys_creation
from lys.core.graphql.edit import lys_edition
from lys.core.graphql.delete import lys_delete
from lys.apps.user_role.consts import ROLE_ACCESS_LEVEL
from lys.apps.organization.consts import ORGANIZATION_ROLE_ACCESS_LEVEL


@register_query()
@strawberry.type
class ProductQuery(Query):

    @lys_getter(
        ProductNode,
        access_levels=[ROLE_ACCESS_LEVEL, ORGANIZATION_ROLE_ACCESS_LEVEL],
        is_licenced=False,
        description="Get a product by ID."
    )
    async def product(self, obj, info):
        pass

    @lys_connection(
        ProductNode,
        access_levels=[ROLE_ACCESS_LEVEL, ORGANIZATION_ROLE_ACCESS_LEVEL],
        is_licenced=False,
        description="List products."
    )
    async def all_products(
        self,
        info,
        search: Annotated[Optional[str], strawberry.argument(description="Search")] = None,
    ):
        entity = info.context.app_manager.get_entity("product")
        stmt = select(entity).order_by(entity.created_at.desc())
        if search:
            stmt = stmt.where(entity.name.ilike(f"%{search.strip()}%"))
        return stmt


@register_mutation()
@strawberry.type
class ProductMutation(Mutation):

    @lys_creation(
        ensure_type=ProductNode,
        access_levels=[ROLE_ACCESS_LEVEL],
        is_licenced=False,
        description="Create a product."
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

    @lys_edition(
        ProductNode,
        UpdateProductInput,
        access_levels=[ROLE_ACCESS_LEVEL, ORGANIZATION_ROLE_ACCESS_LEVEL],
        is_licenced=False,
        description="Update a product."
    )
    async def update_product(self, obj, inputs, info):
        input_data = inputs.to_pydantic()
        if input_data.name is not None:
            obj.name = input_data.name
        if input_data.price is not None:
            obj.price = input_data.price

    @lys_delete(
        ProductNode,
        access_levels=[ROLE_ACCESS_LEVEL],
        is_licenced=False,
        description="Delete a product."
    )
    async def delete_product(self, obj, info):
        pass
```

## Next Steps

- [Permissions](permissions.md) — configuring access control for your webservices
- [Entities and Services](entities-and-services.md) — defining the models behind your nodes
