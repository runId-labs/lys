# JWT-Based Permission System

## Quick Reference

**Purpose**: Stateless permission checking using JWT claims for microservices architecture.

**Key Files**:
- `lys/apps/user_auth/permissions.py` - AnonymousPermission, JWTPermission
- `lys/apps/organization/permissions.py` - OrganizationPermission
- `lys/apps/user_auth/modules/auth/services.py` - AuthService.generate_access_claims()
- `lys/apps/user_role/modules/auth/services.py` - RoleAuthService
- `lys/apps/organization/modules/auth/services.py` - OrganizationAuthService
- `lys/apps/licensing/modules/auth/services.py` - LicensingAuthService
- `lys/apps/user_auth/middlewares.py` - JWTAuthMiddleware

**Settings Configuration**:
```python
permissions=[
    "lys.apps.user_auth.permissions.AnonymousPermission",
    "lys.apps.user_auth.permissions.JWTPermission",
    "lys.apps.organization.permissions.OrganizationPermission",
]
```

---

## Overview

The JWT-based permission system provides stateless authentication and authorization for a microservices architecture. Instead of querying databases for each permission check, the system embeds all necessary access information in JWT tokens.

### Architecture

```
Auth Server (Mimir)                    Business Microservice
┌─────────────────────────────┐       ┌─────────────────────────────┐
│ Has full database:          │       │ No webservice table         │
│ - user, role, webservice    │       │ Only business data          │
│ - client, client_user       │       │                             │
│ - subscription              │       │ Permissions via JWT only:   │
│                             │       │ - JWTPermission             │
│ Generates JWT with:         │       │ - OrganizationPermission    │
│ - webservices (dict)        │       │                             │
│ - organizations (dict)      │       │ Row filtering via:          │
│                             │       │ - client_id                 │
│ Permissions:                │       │ - department_id             │
│ - AnonymousPermission (DB)  │       │ - team_id                   │
│ - JWTPermission (JWT)       │       │                             │
│ - OrganizationPermission    │       │                             │
└─────────────────────────────┘       └─────────────────────────────┘
```

### Key Principles

1. **Stateless**: No database queries for permission checks on business servers
2. **JWT Contains All Access Info**: webservices, organizations, access types
3. **Row-Level Filtering**: Entity queries filtered by organization scope
4. **Inheritance Chain**: AuthService subclasses build claims progressively

---

## JWT Structure

### Complete JWT Claims

```json
{
    "sub": "user-uuid",
    "is_super_user": false,
    "exp": 1734000000,
    "xsrf_token": "abc123...",

    "webservices": {
        "logout": "full",
        "refresh_token": "full",
        "connected_user": "full",
        "user": "owner",
        "update_user_email": "owner",
        "update_password": "owner",
        "create_user": "full",
        "list_users": "full"
    },

    "organizations": {
        "client-uuid-1": {
            "level": "client",
            "webservices": ["manage_billing", "list_projects", "create_invoice"]
        },
        "client-uuid-2": {
            "level": "client",
            "webservices": ["list_projects", "view_reports"]
        }
    }
}
```

### Claims Description

| Claim | Type | Description |
|-------|------|-------------|
| `sub` | string | User ID (standard JWT subject claim) |
| `is_super_user` | boolean | Super user bypass flag |
| `exp` | integer | Expiration timestamp |
| `xsrf_token` | string | CSRF protection token |
| `webservices` | dict | Webservice name -> access type ("full" or "owner") |
| `organizations` | dict | Organization ID -> {level, webservices[]} |

### Access Types

| Access Type | Description | Row Filtering |
|-------------|-------------|---------------|
| `"full"` | Full access to all data | No filtering |
| `"owner"` | Access only to owned data | Filter by `user_id` |

---

## Permission Classes

### AnonymousPermission

**File**: `lys/apps/user_auth/permissions.py`

**Purpose**: Handle public webservices for non-authenticated users.

**When Used**: User has no JWT token (not connected).

**Logic**:
```python
if context.connected_user is not None:
    return None, None  # Let other permissions handle

if webservice.is_public:
    return True, None  # Grant access

return None, ACCESS_DENIED_ERROR  # Deny access
```

**Database Access**: Yes (checks `webservice.is_public`)

**Use On**: Auth Server only

### JWTPermission

**File**: `lys/apps/user_auth/permissions.py`

**Purpose**: Check webservice access via JWT claims.

**When Used**: User is authenticated (has valid JWT).

**Logic**:
```python
if connected_user.get("is_super_user"):
    return True, None  # Super user bypass

user_webservices = connected_user.get("webservices", {})

if webservice.id in user_webservices:
    access_type = user_webservices[webservice.id]
    if access_type == "owner":
        return {OWNER_ACCESS_KEY: True}, None
    return True, None  # "full" access

return None, None  # Let other permissions handle
```

**Database Access**: No (JWT only)

**Use On**: All servers

**Row-Level Filtering**:
When `access_type = {OWNER_ACCESS_KEY: True}`, queries are filtered:
```python
entity_class.user_accessing_filters(stmt, connected_user_id)
# Typically: WHERE entity.user_id = connected_user_id
```

### OrganizationPermission

**File**: `lys/apps/organization/permissions.py`

**Purpose**: Check organization-scoped webservice access via JWT claims.

**When Used**: User is authenticated and webservice has ORGANIZATION_ROLE_ACCESS_LEVEL.

**Logic**:
```python
organizations = connected_user.get("organizations", {})

accessible_orgs = {}
for org_id, org_data in organizations.items():
    org_level = org_data.get("level", "client")
    org_webservices = org_data.get("webservices", [])

    if webservice.id in org_webservices:
        if org_level not in accessible_orgs:
            accessible_orgs[org_level] = []
        accessible_orgs[org_level].append(org_id)

if accessible_orgs:
    return {ORGANIZATION_ROLE_ACCESS_KEY: accessible_orgs}, None

return None, None
```

**Database Access**: No (JWT only)

**Use On**: All servers

**Row-Level Filtering**:
When `access_type = {ORGANIZATION_ROLE_ACCESS_KEY: {...}}`, queries are filtered:
```python
entity_class.organization_accessing_filters(stmt, accessing_organization_dict)
# Typically: WHERE entity.client_id IN (id1, id2, ...)
```

---

## AuthService Inheritance Chain

The JWT claims are built progressively by a chain of AuthService subclasses:

```
AuthService (user_auth)
    │
    │ generate_access_claims():
    │   - sub: user.id
    │   - is_super_user: user.is_super_user
    │   - webservices: {PUBLIC_NO_LIMIT, CONNECTED, OWNER}
    │
    ▼
RoleAuthService (user_role)
    │
    │ generate_access_claims():
    │   - super().generate_access_claims()
    │   - + role-based webservices with "full" access
    │
    ▼
OrganizationAuthService (organization)
    │
    │ generate_access_claims():
    │   - super().generate_access_claims()
    │   - + organizations: {org_id: {level, webservices}}
    │
    ▼
LicensingAuthService (licensing)
    │
    │ generate_access_claims():
    │   - super().generate_access_claims()
    │   - filters webservices by license status
    │   - licensed webservices require subscription_user entry
```

### AuthService._get_base_webservices()

Returns webservices accessible to any connected user:

```python
# Query webservices that are:
# 1. Public with NO_LIMITATION type -> "full"
# 2. Have CONNECTED_ACCESS_LEVEL enabled -> "full"
# 3. Have OWNER_ACCESS_LEVEL enabled -> "owner"

return {
    "logout": "full",
    "connected_user": "full",
    "user": "owner",
    "update_user_email": "owner"
}
```

### RoleAuthService._get_user_role_webservices()

Returns webservices from user's global roles:

```python
# Query roles assigned to user that are enabled
# Collect unique webservice names from all roles
# Role access is always "full"
```

### OrganizationAuthService._get_user_organizations()

Returns organizations where user has access:

```python
# For each organization (client) where user is:
# 1. Owner (automatic full access)
# 2. Member with ClientUserRole

return {
    "client-uuid-1": {
        "level": "client",
        "webservices": ["manage_billing", "list_projects"]
    }
}
```

### LicensingAuthService

Filters webservices based on license status:

```python
# For licensed webservices:
# - Check if user exists in subscription_user table
# - If not licensed, remove from organizations claim

# For non-licensed webservices:
# - Include normally
```

---

## Access Level Types

| Access Level | Constant | Permission Class | JWT Location |
|--------------|----------|------------------|--------------|
| PUBLIC | `is_public=True` | AnonymousPermission | N/A (DB check) |
| PUBLIC (NO_LIMITATION) | `NO_LIMITATION_WEBSERVICE_PUBLIC_TYPE` | JWTPermission | `webservices[name] = "full"` |
| CONNECTED | `CONNECTED_ACCESS_LEVEL` | JWTPermission | `webservices[name] = "full"` |
| OWNER | `OWNER_ACCESS_LEVEL` | JWTPermission | `webservices[name] = "owner"` |
| ROLE | `ROLE_ACCESS_LEVEL` | JWTPermission | `webservices[name] = "full"` |
| ORGANIZATION_ROLE | `ORGANIZATION_ROLE_ACCESS_LEVEL` | OrganizationPermission | `organizations[id].webservices[]` |

---

## Row-Level Filtering

### Entity Implementation

Entities must implement filtering methods:

```python
class Project(Entity):
    client_id = Column(ForeignKey("client.id"))
    user_id = Column(ForeignKey("user.id"))

    @classmethod
    def user_accessing_filters(cls, stmt, user_id):
        """Filter for OWNER access level."""
        conditions = [cls.user_id == user_id]
        return stmt, conditions

    @classmethod
    def organization_accessing_filters(cls, stmt, org_dict):
        """Filter for ORGANIZATION_ROLE access level."""
        conditions = []
        client_ids = org_dict.get("client", [])
        if client_ids:
            conditions.append(cls.client_id.in_(client_ids))
        return stmt, conditions
```

### Permission Integration

```python
# In JWTPermission.add_statement_access_constraints():
if access_type.get(OWNER_ACCESS_KEY):
    stmt, conditions = entity_class.user_accessing_filters(stmt, connected_user_id)
    or_where |= or_(*conditions)

# In OrganizationPermission.add_statement_access_constraints():
if access_type.get(ORGANIZATION_ROLE_ACCESS_KEY):
    stmt, conditions = entity_class.organization_accessing_filters(stmt, org_dict)
    or_where |= or_(*conditions)
```

---

## Organization Permission Details

### Organization Hierarchy

```
Client (top-level tenant)
    │
    ├── Department (sub-organization)
    │       │
    │       └── Team (sub-sub-organization)
    │
    └── ClientUser (user membership)
            │
            └── ClientUserRole (role assignment)
```

### Database Schema

```
┌──────────┐       ┌─────────────┐       ┌────────┐
│   User   │──────▶│ ClientUser  │──────▶│ Client │
└──────────┘       └─────────────┘       └────────┘
                          │                   │
                          ▼                   │ owner_id
                   ┌──────────────────┐       │
                   │ ClientUserRole   │       │
                   └──────────────────┘       │
                          │                   │
                          ▼                   ▼
                      ┌──────┐       ┌─────────────┐
                      │ Role │──────▶│ Webservice  │
                      └──────┘       └─────────────┘
```

### Owner Access

Client owners automatically receive full access without explicit role assignment:

```python
# In OrganizationAuthService._get_user_organizations():
# 1. Query clients where user is owner
stmt = select(client_entity).where(client_entity.owner_id == user_id)

# 2. Get all ORGANIZATION_ROLE webservices for owned clients
# 3. Add to organizations claim
```

### Use Cases

**Use Case 1: Project Manager**
- Alice is a project manager for Client A
- She has ClientUser + ClientUserRole with "Project Manager" role
- Role includes "list_projects" webservice
- JWT contains: `organizations: {"client-a-id": {level: "client", webservices: ["list_projects"]}}`
- Queries are filtered: `WHERE project.client_id = 'client-a-id'`

**Use Case 2: Multi-Client Consultant**
- Bob works for Client A and Client B
- He has ClientUser in both clients
- JWT contains: `organizations: {"client-a-id": {...}, "client-b-id": {...}}`
- Queries are filtered: `WHERE project.client_id IN ('client-a-id', 'client-b-id')`

**Use Case 3: Client Owner**
- Diana owns Client D (no ClientUserRole needed)
- JWT contains: `organizations: {"client-d-id": {level: "client", webservices: [...]}}`
- Full access to all ORGANIZATION_ROLE webservices for her client

---

## Middleware Integration

### JWTAuthMiddleware

**File**: `lys/apps/user_auth/middlewares.py`

```python
class JWTAuthMiddleware(MiddlewareInterface, BaseHTTPMiddleware):
    REQUIRED_JWT_CLAIMS = ["sub", "exp", "xsrf_token"]

    async def dispatch(self, request, call_next):
        access_token = request.cookies.get(ACCESS_COOKIE_KEY)

        if access_token:
            jwt_claims = await self.auth_utils.decode(access_token)
            # Validate required claims
            # Validate XSRF token if enabled

            # Pass ALL JWT claims to context
            connected_user = jwt_claims

        request.state.connected_user = connected_user
```

### Context Access

```python
# In webservices/resolvers:
connected_user = info.context.connected_user

user_id = connected_user["sub"]
is_super = connected_user["is_super_user"]
webservices = connected_user.get("webservices", {})
organizations = connected_user.get("organizations", {})
```

---

## Configuration

### Auth Server (Mimir)

```python
# settings.py
permissions=[
    "lys.apps.user_auth.permissions.AnonymousPermission",  # DB check for public
    "lys.apps.user_auth.permissions.JWTPermission",        # JWT check
    "lys.apps.organization.permissions.OrganizationPermission",  # Org JWT check
]
```

### Business Microservice

```python
# settings.py
permissions=[
    "lys.apps.user_auth.permissions.JWTPermission",        # JWT only
    "lys.apps.organization.permissions.OrganizationPermission",  # Org JWT check
]
# Note: No AnonymousPermission (no webservice table)
```

### Webservice Definition

```python
@lys_connection(
    ensure_type=ProjectNode,
    is_public=False,
    access_levels=[ORGANIZATION_ROLE_ACCESS_LEVEL],
    is_licenced=True,
    description="List projects for user's organizations"
)
async def list_projects(self, info: Info) -> Select:
    # Permission checked automatically
    # Query filtered by organization
    pass
```

---

## Security Considerations

### Token Security

- JWT signed with `SECRET_KEY` (HS256)
- Short expiration (default: 5 minutes)
- XSRF token validation (optional)
- HttpOnly, Secure, SameSite cookies

### Super User Bypass

```python
if connected_user.get("is_super_user"):
    return True, None  # Full access, no filtering
```

### License Verification

Licensed webservices require user to be in `subscription_user` table:
- Checked during JWT generation (not at request time)
- Filtered from `organizations` claim if not licensed

---

## Troubleshooting

### User Cannot Access Webservice

1. **Check JWT claims**: `logger.debug(f"JWT claims: {connected_user}")`
2. **Verify webservice in claims**: Is `webservice.id` in `webservices` or `organizations[*].webservices`?
3. **Check access type**: Is it "full" or "owner"?
4. **Check super user**: Is `is_super_user = true`?

### User Sees Wrong Data

1. **Check access_type**: Is `OWNER_ACCESS_KEY` or `ORGANIZATION_ROLE_ACCESS_KEY` set?
2. **Check entity filters**: Does entity implement `user_accessing_filters()` or `organization_accessing_filters()`?
3. **Check organization IDs**: Are correct org IDs in JWT?

### Permission Denied After Login

1. **Check JWT generation**: Are all AuthService subclasses in chain?
2. **Check webservice fixtures**: Is webservice in DB with correct access_levels?
3. **Check role assignment**: Does user have roles with this webservice?

### Debug Logging

```python
# In AuthService.generate_access_token():
logger.debug(f"Generated JWT claims: {claims}")

# In JWTAuthMiddleware:
logger.debug(f"User {connected_user['sub']} authenticated via JWT")

# In permission classes:
logger.debug(f"Checking permission for webservice {webservice.id}")
```

---

## Migration from Database Permissions

### Before (Database-based)

```python
# Permission checked via DB query
async def check_webservice_permission(cls, webservice, context, session):
    roles = await session.execute(
        select(Role).where(Role.users.any(id=user_id))
    )
    # ... complex DB queries
```

### After (JWT-based)

```python
# Permission checked via JWT claims
async def check_webservice_permission(cls, webservice, context, session):
    webservices = context.connected_user.get("webservices", {})
    if webservice.id in webservices:
        return True, None
    # No DB query needed
```

### Key Changes

1. `connected_user["id"]` -> `connected_user["sub"]`
2. `webservice.name` -> `webservice.id` (ParametricEntity)
3. `user["user"]` nested object removed -> claims at root level
4. DB queries in permissions -> JWT claims check
5. Permission module paths use full class path

---

## Related Documentation

- **[auth.md](./auth.md)**: Authentication flow, login/logout, token refresh
- **[webservice_management.md](./webservice_management.md)**: Webservice definition and configuration
- **[../todos/jwt-permissions-refactoring.md](../todos/jwt-permissions-refactoring.md)**: Implementation details and progress