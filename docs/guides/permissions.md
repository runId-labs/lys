# Permissions

This guide covers how Lys handles authentication, authorization, and row-level access control.

## Table of Contents

1. [Overview](#overview)
2. [Permission Chain](#permission-chain)
3. [Permission Classes](#permission-classes)
4. [Access Levels](#access-levels)
5. [Row-Level Filtering](#row-level-filtering)
6. [Implementing Access Control on Entities](#implementing-access-control-on-entities)
7. [Tenant Column Safety Check](#tenant-column-safety-check)
8. [JWT Claims Generation](#jwt-claims-generation)
9. [Service-to-Service Authentication](#service-to-service-authentication)
10. [Auth Server vs Business Server](#auth-server-vs-business-server)
11. [Permission Flow Example](#permission-flow-example)
12. [Custom Permission Classes](#custom-permission-classes)
13. [Next Steps](#next-steps)

## Overview

Lys implements a **stateless, pluggable permission system** designed for microservices:

- **Stateless**: All permission data is embedded in JWT claims. Business servers make zero database queries for authorization.
- **Pluggable**: Permission modules are chained. Each module contributes to the access decision.
- **Row-level**: Entities implement filtering methods that restrict query results to authorized rows.

## Permission Chain

Permissions are evaluated in order. The chain is configured in settings:

```python
app_settings.configure(
    permissions=[
        "lys.apps.base.permissions.InternalServicePermission",
        "lys.apps.user_auth.permissions.AnonymousPermission",
        "lys.apps.user_auth.permissions.JWTPermission",
        "lys.apps.organization.permissions.OrganizationPermission",
    ],
)
```

Each permission class returns one of three results:

| Result | Meaning | Effect |
|--------|---------|--------|
| `(True, None)` | Access granted | Short-circuits, no more checks |
| `(False, error)` | Access denied | Short-circuits with error |
| `(None, None)` | No opinion | Next permission is checked |
| `({...}, None)` | Conditional access | Merged with other dicts, chain continues |

Dictionary results (conditional access) are additive — they accumulate across the chain and are used for row-level filtering.

## Permission Classes

### InternalServicePermission

Handles **service-to-service** calls using a dedicated service JWT.

**Activated when**: Request has `Authorization: Service <token>` header.

**Returns**: `(True, None)` if the webservice allows `INTERNAL_SERVICE_ACCESS_LEVEL`; `(None, None)` otherwise.

```python
# A webservice restricted to internal calls only
@lys_getter(
    ProductNode,
    access_levels=[INTERNAL_SERVICE_ACCESS_LEVEL],
    description="Internal: sync product data between services."
)
async def sync_product(self, obj, info):
    pass
```

### AnonymousPermission

Handles **public endpoints** for unauthenticated users.

**Activated when**: No JWT token in the request.

**Returns**: `(True, None)` if the webservice is marked as public; `(None, ACCESS_DENIED_ERROR)` if no user and webservice is not public.

```python
# A public webservice
@lys_connection(
    ProductCategoryNode,
    is_public=True,
    description="List product categories (no auth required)."
)
async def all_categories(self, info):
    pass
```

### JWTPermission

Handles **authenticated user** access based on JWT claims.

**Activated when**: Request has a valid JWT with `connected_user` claims.

**JWT claims structure**:
```json
{
    "sub": "user-uuid",
    "is_super_user": false,
    "webservices": {
        "product": "owner",
        "all_products": "full",
        "create_product": "full"
    }
}
```

**Logic**:
1. If `is_super_user` is `true`: returns `(True, None)` — full access, no filtering (logged for audit).
2. If webservice name is in `webservices` claims:
   - Value `"full"`: returns `(True, None)` — full access
   - Value `"owner"`: returns `({OWNER_ACCESS_KEY: True}, None)` — access limited to user's own data
3. Otherwise: returns `(None, None)` — let OrganizationPermission handle it.

### OrganizationPermission

Handles **organization-scoped** access for multi-tenant applications.

**Activated when**: User has `organizations` claim in JWT.

**JWT claims structure**:
```json
{
    "organizations": {
        "client-uuid-1": {
            "level": "client",
            "webservices": ["all_products", "product"]
        },
        "client-uuid-2": {
            "level": "client",
            "webservices": ["all_products"]
        }
    }
}
```

**Returns**: A dictionary mapping organization levels to the IDs that grant access:
```python
{
    "organization_role": {
        "client": ["client-uuid-1", "client-uuid-2"]
    }
}
```

This dictionary is used downstream for row-level filtering.

## Access Levels

Each webservice declares its required access levels:

| Level | Constant | Description |
|-------|----------|-------------|
| Owner | `OWNER_ACCESS_LEVEL` | User can only access their own data |
| Role | `ROLE_ACCESS_LEVEL` | User has the webservice in their role's allowed list |
| Organization | `ORGANIZATION_ROLE_ACCESS_LEVEL` | User belongs to the right organization |
| Internal | `INTERNAL_SERVICE_ACCESS_LEVEL` | Service-to-service JWT |

Multiple levels can be combined — access is granted if **any** level matches:

```python
@lys_getter(
    ProductNode,
    access_levels=[ROLE_ACCESS_LEVEL, ORGANIZATION_ROLE_ACCESS_LEVEL],
    description="Get a product."
)
```

## Row-Level Filtering

Row-level filtering restricts query results to rows the user is authorized to see. It operates at two levels.

### Query-Level Filtering

Applied automatically to `lys_connection` and `lys_getter` operations. The permission chain calls `add_statement_access_constraints()` which modifies the SQL WHERE clause.

**JWTPermission** applies owner filtering when `access_type = {OWNER_ACCESS_KEY: True}`:

```sql
-- Before filtering
SELECT * FROM product

-- After JWTPermission filtering (owner access)
SELECT * FROM product WHERE product.owner_id = 'user-uuid'
```

**OrganizationPermission** applies organization filtering when `access_type = {ORGANIZATION_ROLE_ACCESS_KEY: {...}}`:

```sql
-- Before filtering
SELECT * FROM product

-- After OrganizationPermission filtering
SELECT * FROM product WHERE product.client_id IN ('client-uuid-1', 'client-uuid-2')
```

### Instance-Level Checks

For `lys_getter`, `lys_edition`, and `lys_delete`, the entity's `check_permission()` method is called after the entity is fetched:

```python
def check_permission(self, user_id, access_type):
    if isinstance(access_type, bool):
        return access_type

    if access_type.get(ROLE_ACCESS_KEY):
        return True  # Role-based access already checked at webservice level

    if access_type.get(OWNER_ACCESS_KEY):
        return user_id in self.accessing_users()

    if access_type.get(ORGANIZATION_ROLE_ACCESS_KEY):
        for org_key, org_ids in self.accessing_organizations().items():
            user_org_ids = access_type[ORGANIZATION_ROLE_ACCESS_KEY].get(org_key, [])
            if any(uid in org_ids for uid in user_org_ids):
                return True

    return False
```

## Implementing Access Control on Entities

To enable row-level filtering, implement these methods on your entities:

### accessing_users()

Returns a list of user IDs with direct access to this entity instance. Used by `OWNER_ACCESS_LEVEL`.

```python
@register_entity()
class Product(Entity):
    owner_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), nullable=True)

    def accessing_users(self) -> list[str]:
        if self.owner_id:
            return [self.owner_id]
        return []
```

### accessing_organizations()

Returns a dictionary mapping organization levels to IDs. Used by `ORGANIZATION_ROLE_ACCESS_LEVEL`.

```python
@register_entity()
class Product(Entity):
    client_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), nullable=False)

    def accessing_organizations(self) -> dict[str, list[str]]:
        return {"client": [self.client_id]}
```

### user_accessing_filters()

Returns SQLAlchemy conditions for owner-based list queries:

```python
@classmethod
def user_accessing_filters(cls, stmt, user_id):
    return stmt, [cls.owner_id == user_id]
```

### organization_accessing_filters()

Returns SQLAlchemy conditions for organization-based list queries:

```python
@classmethod
def organization_accessing_filters(cls, stmt, organization_id_dict):
    client_ids = organization_id_dict.get("client", [])
    return stmt, [cls.client_id.in_(client_ids)]
```

Both methods return a tuple of `(statement, conditions)`. The conditions are combined with `OR` and appended to the query's WHERE clause.

## Tenant Column Safety Check

`OrganizationPermission` includes a safety mechanism that detects entities with tenant columns (like `client_id`) that haven't overridden `organization_accessing_filters()`. If detected, a `RuntimeError` is raised to prevent accidental data leaks.

Default tenant columns: `{"client_id"}`

To add custom tenant columns for your domain, extend OrganizationPermission:

```python
from lys.apps.organization.permissions import OrganizationPermission


class MyOrganizationPermission(OrganizationPermission):
    DEFAULT_TENANT_COLUMNS = OrganizationPermission.DEFAULT_TENANT_COLUMNS | {
        "department_id",
        "team_id",
    }
```

Register it in settings:

```python
app_settings.configure(
    permissions=[
        # ...
        "my_apps.core.permissions.MyOrganizationPermission",
    ],
)
```

Now any entity with a `department_id` or `team_id` column must implement `organization_accessing_filters()` or Lys raises an error at startup.

`ParametricEntity` subclasses are exempt from this check (they contain global configuration data, not tenant-scoped data).

## JWT Claims Generation

JWT claims are generated at login time by the **auth server**. The claims contain all permission data needed for stateless authorization:

```json
{
    "sub": "user-uuid",
    "is_super_user": false,
    "exp": 1734000300,
    "xsrf_token": "random-token",
    "webservices": {
        "product": "owner",
        "all_products": "full",
        "create_product": "full"
    },
    "organizations": {
        "client-uuid-1": {
            "level": "client",
            "webservices": ["all_products", "product", "create_product"]
        }
    }
}
```

The `webservices` dict maps webservice names to access types (`"full"` or `"owner"`). The `organizations` dict maps organization IDs to their levels and allowed webservices.

This structure is generated from the user's roles and organization memberships. Business servers never query the database for permissions — they decode the JWT and use these claims directly.

## Service-to-Service Authentication

When microservices need to communicate, they use **service JWT tokens**:

```python
from lys.core.utils.auth import ServiceAuthUtils

auth_utils = ServiceAuthUtils(secret_key=settings.secret_key)
token = auth_utils.generate_token(
    service_name="catalog-service",
    expiration_minutes=1,
)
```

The calling service includes this token in the request:

```
Authorization: Service eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

On the receiving end, `ServiceAuthMiddleware` decodes the token and sets `context.service_caller`. `InternalServicePermission` then grants access if the webservice allows `INTERNAL_SERVICE_ACCESS_LEVEL`.

Service tokens are short-lived (1 minute default) and contain:
```json
{
    "type": "service",
    "service_name": "catalog-service",
    "instance_id": "unique-id",
    "iat": 1734000000,
    "exp": 1734000060
}
```

## Auth Server vs Business Server

The permission configuration differs between auth servers and business servers:

**Auth server** (has the user database):
```python
permissions=[
    "lys.apps.base.permissions.InternalServicePermission",
    "lys.apps.user_auth.permissions.AnonymousPermission",
    "lys.apps.user_auth.permissions.JWTPermission",
    "lys.apps.organization.permissions.OrganizationPermission",
]
```

**Business server** (stateless, JWT only):
```python
permissions=[
    "lys.apps.user_auth.permissions.JWTPermission",
    "lys.apps.organization.permissions.OrganizationPermission",
]
```

Business servers don't need `AnonymousPermission` (no webservice database table) or `InternalServicePermission` (unless they receive service-to-service calls).

## Permission Flow Example

**Scenario**: User Alice requests `all_products` with organization-scoped access.

**Alice's JWT**:
```json
{
    "sub": "alice-uuid",
    "organizations": {
        "client-1": {
            "level": "client",
            "webservices": ["all_products", "product"]
        }
    }
}
```

**Flow**:

1. `InternalServicePermission`: no `service_caller` → `(None, None)`, skip.
2. `AnonymousPermission`: user is connected → `(None, None)`, skip.
3. `JWTPermission`: `all_products` not in `webservices` claim → `(None, None)`, skip.
4. `OrganizationPermission`: finds `all_products` in org `client-1`:
   - Returns `({ORGANIZATION_ROLE_ACCESS_KEY: {"client": ["client-1"]}}, None)`.
5. `add_statement_access_constraints()`:
   - Calls `Product.organization_accessing_filters(stmt, {"client": ["client-1"]})`.
   - Adds `WHERE product.client_id IN ('client-1')`.
6. Final SQL: `SELECT * FROM product WHERE product.client_id IN ('client-1') ORDER BY ...`.

Alice only sees products belonging to client-1.

## Custom Permission Classes

Create a custom permission class by implementing the `PermissionInterface`:

```python
from lys.core.interfaces.permissions import PermissionInterface


class IPWhitelistPermission(PermissionInterface):

    async def check_webservice_permission(self, webservice_id, context):
        """Check if the request IP is whitelisted."""
        client_ip = context.request.client.host
        allowed_ips = self.get_allowed_ips()

        if client_ip not in allowed_ips:
            return False, (403, "IP not allowed")

        return None, None  # No opinion, let other permissions decide

    async def add_statement_access_constraints(self, access_type, entity_class, stmt, or_where, context):
        """No row-level filtering for IP checks."""
        return stmt, or_where
```

Register it:

```python
permissions=[
    "my_apps.core.permissions.IPWhitelistPermission",
    "lys.apps.user_auth.permissions.JWTPermission",
    # ...
]
```

## Next Steps

- [GraphQL API](graphql-api.md) — applying permissions to webservices
- [Entities and Services](entities-and-services.md) — implementing access control methods on entities
