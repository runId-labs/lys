# Organization-Based Permission System

## Overview

The organization-based permission system provides multi-tenant access control where users gain access to resources through roles assigned within specific organizations. This system enables fine-grained data isolation while allowing flexible role-based access across organizational boundaries.

## Key Concepts

### Organizations

Organizations are hierarchical entities that represent business units, departments, or clients. The system supports multiple organization types:

- **Client**: Top-level organization entity representing a customer or tenant
- **Department**: Sub-organization within a client (extensible architecture)
- **Division**: Further subdivision (extensible architecture)

**Characteristics**:
- Organizations can have parent-child relationships
- Child organizations inherit access from parent organizations
- Each organization has an owner (user)
- **Client owners automatically receive full access** to their client's data without requiring explicit role assignment

### Organization Roles

Users are assigned roles within specific organizations through the `ClientUserRole` entity (or similar entities for other organization types). A role grants a user access to specific webservices within the context of that organization.

**Components**:
- **ClientUser**: Links a User to a Client (organization membership)
- **ClientUserRole**: Links a ClientUser to a Role (role assignment within organization)
- **Role**: Defines a set of permissions (associated webservices)
- **Webservice**: An API endpoint or operation requiring access control

### Access Levels

The system uses the `ORGANIZATION_ROLE_ACCESS_LEVEL` constant to identify webservices that require organization-scoped permissions.

## Permission Flow

### 1. Webservice Access Check

When a user attempts to access a webservice, the system performs the following checks:

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Check if webservice requires ORGANIZATION_ROLE_ACCESS_LEVEL │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. Query user's organization roles for this webservice      │
│    - User must be member of organization (via ClientUser)   │
│    - Role must be enabled                                   │
│    - Role must include the requested webservice            │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. Check if user is owner of any clients                   │
│    - Query: SELECT * FROM client WHERE owner_id = user_id   │
│    - Owner gets automatic access without explicit roles    │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. Build access map of accessible organizations            │
│    - Include organizations from roles (step 2)             │
│    - Include owned clients (step 3)                        │
│    - Avoid duplicates                                      │
│    {                                                        │
│      "organization_role": {                                 │
│        "client": [client_id1, client_id2],                 │
│        "department": [dept_id1]                            │
│      }                                                      │
│    }                                                        │
└─────────────────────────────────────────────────────────────┘
```

**Result**:
- **Access granted**: User receives a dictionary mapping organization types to accessible IDs
- **Access denied**: User receives `None` and cannot proceed

### 2. Data Filtering

Once webservice access is granted, all database queries are automatically filtered to respect organization boundaries:

```
┌─────────────────────────────────────────────────────────────┐
│ User requests data (e.g., list of projects)                 │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ System applies organization filters via                     │
│ entity.organization_accessing_filters()                     │
│                                                             │
│ Example: WHERE project.client_id IN (1, 2)                 │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ Query returns only data from accessible organizations       │
└─────────────────────────────────────────────────────────────┘
```

## Database Schema

### Core Entities

```
┌──────────┐       ┌─────────────┐       ┌────────┐
│   User   │──────▶│ ClientUser  │──────▶│ Client │
└──────────┘       └─────────────┘       └────────┘
                          │
                          ▼
                   ┌──────────────────┐
                   │ ClientUserRole   │
                   └──────────────────┘
                          │
                          ▼
                      ┌──────┐       ┌─────────────┐
                      │ Role │──────▶│ Webservice  │
                      └──────┘       └─────────────┘
```

### Relationships

**User → ClientUser**:
- One user can belong to multiple clients
- Foreign key: `client_user.user_id → user.id`

**Client → ClientUser**:
- One client can have multiple users
- Foreign key: `client_user.client_id → client.id`

**ClientUser → ClientUserRole**:
- One client user can have multiple roles within that client
- Foreign key: `client_user_role.client_user_id → client_user.id`

**Role → ClientUserRole**:
- One role can be assigned to multiple client users
- Foreign key: `client_user_role.role_id → role.id`

**Role → Webservice** (many-to-many):
- A role grants access to multiple webservices
- A webservice can be included in multiple roles
- Junction table: `role_webservice`

## Use Cases

### Use Case 1: Project Manager Access

**Scenario**: Alice is a project manager for Client A. She should only see projects belonging to Client A.

**Setup**:
1. Alice has a User account
2. Alice is linked to Client A via ClientUser
3. Alice has the "Project Manager" role via ClientUserRole
4. The "Project Manager" role includes the "list_projects" webservice

**Flow**:
1. Alice requests `/graphql` with query `list_projects`
2. System checks: Does `list_projects` require `ORGANIZATION_ROLE_ACCESS_LEVEL`? → Yes
3. System queries: Does Alice have a role in any organization that includes `list_projects`? → Yes (Client A, Project Manager role)
4. System builds access map: `{"organization_role": {"client": [client_a_id]}}`
5. System filters query: `WHERE project.client_id = client_a_id`
6. Alice receives only projects from Client A

**Result**: Alice sees only her organization's data, even though other organizations exist in the database.

### Use Case 2: Multi-Client Consultant

**Scenario**: Bob is a consultant working for both Client A and Client B. He should see data from both clients.

**Setup**:
1. Bob has one User account
2. Bob is linked to Client A via ClientUser (id=1)
3. Bob is linked to Client B via ClientUser (id=2)
4. Bob has "Consultant" role in both clients via ClientUserRole
5. The "Consultant" role includes "view_reports" webservice

**Flow**:
1. Bob requests `/graphql` with query `view_reports`
2. System checks: Does `view_reports` require `ORGANIZATION_ROLE_ACCESS_LEVEL`? → Yes
3. System queries: Does Bob have a role in any organization that includes `view_reports`? → Yes (Client A and Client B)
4. System builds access map: `{"organization_role": {"client": [client_a_id, client_b_id]}}`
5. System filters query: `WHERE report.client_id IN (client_a_id, client_b_id)`
6. Bob receives reports from both Client A and Client B

**Result**: Bob has access to multiple organizations' data through his multiple organization memberships.

### Use Case 3: Disabled Role

**Scenario**: Charlie had access to Client C, but his role was disabled. He should no longer access the data.

**Setup**:
1. Charlie has a User account
2. Charlie is linked to Client C via ClientUser
3. Charlie has "Analyst" role via ClientUserRole
4. The "Analyst" role is marked as `enabled = False`

**Flow**:
1. Charlie requests `/graphql` with query `view_analytics`
2. System checks: Does `view_analytics` require `ORGANIZATION_ROLE_ACCESS_LEVEL`? → Yes
3. System queries: Does Charlie have an **enabled** role in any organization? → No (role is disabled)
4. System denies access: Charlie cannot proceed
5. API returns permission denied error

**Result**: Disabling a role immediately revokes access for all users with that role.

### Use Case 4: Client Owner Automatic Access

**Scenario**: Diana is the owner of Client D. She should have full access to all Client D's data without needing explicit role assignments.

**Setup**:
1. Diana has a User account
2. Diana created Client D and is set as `client.owner_id = diana_user_id`
3. Diana does NOT have any ClientUser or ClientUserRole entries
4. Other users in Client D have roles assigned through ClientUserRole

**Flow**:
1. Diana requests `/graphql` with query `view_client_data`
2. System checks: Does `view_client_data` require `ORGANIZATION_ROLE_ACCESS_LEVEL`? → Yes
3. System queries: Does Diana have a role in any organization? → No explicit roles found
4. System queries: Is Diana the owner of any clients? → Yes (Client D)
5. System builds access map: `{"organization_role": {"client": [client_d_id]}}`
6. System filters query: `WHERE data.client_id = client_d_id`
7. Diana receives all data from Client D

**Result**: Client owners have automatic administrator-level access to their client's data without requiring role configuration. This simplifies onboarding and ensures owners always maintain control of their organizations.

**Implementation Details**:
- Owner check happens automatically in `OrganizationPermission.check_webservice_permission()`
- Query: `SELECT * FROM client WHERE owner_id = connected_user_id`
- Owned client IDs are added to the access map alongside role-based access
- Duplicates are avoided if owner also has explicit roles
- Owner access is scoped only to webservices with `ORGANIZATION_ROLE_ACCESS_LEVEL`

### Use Case 5: Hierarchical Organizations (Future Extension)

**Scenario**: Department D is a child of Client C. Users with access to Client C should also access Department D's data.

**Setup**:
1. Client C exists
2. Department D exists with `parent_organization = Client C`
3. User has role in Client C

**Flow** (with hierarchy support):
1. System detects user has access to Client C
2. System calls `client.accessing_organizations()` which recursively includes child organizations
3. Access map includes both Client C and Department D
4. Queries filter by both organization IDs

**Result**: Parent organization access automatically includes child organizations.

## Security Considerations

### Data Isolation

- **Principle**: Users can only access data within organizations where they have an active role
- **Enforcement**: Every database query is automatically filtered by the permission system
- **Bypass**: Super users (defined in `user_auth` permission) bypass organization restrictions

### Role Management

- **Role Enablement**: Roles can be disabled to immediately revoke access for all users
- **Role Scope**: Roles are specific to webservices, not broad permissions
- **Role Assignment**: Users must have both ClientUser membership AND ClientUserRole assignment

### Hierarchical Access

- **Parent Access**: Access to parent organizations can grant access to child organizations
- **Inheritance**: Child organizations inherit accessibility from parent
- **Polymorphism**: Organizations are polymorphic (Client, Department, Division, etc.)

## Performance Optimization

### Eager Loading

The system uses SQLAlchemy's `selectinload()` to prevent N+1 query problems:

```python
.options(
    selectinload(client_user_role_entity.client_user)
    .selectinload(client_user_entity.client)
)
```

**Performance Impact**:
- **Without optimization**: 1 + (N × 2) queries for N roles
- **With optimization**: 3 queries total (constant)
- **Example**: 10 roles = 3 queries instead of 21 queries (86% reduction)

### Query Optimization

- **Single Query Check**: Webservice access check uses a single query with joins
- **Batch Loading**: Organization IDs are loaded in batches via `IN` clauses
- **Lazy Evaluation**: Filters are only applied when queries are executed

## API Reference

### Permission Class: `OrganizationPermission`

**Location**: `lys.apps.organization.permission`

#### Method: `check_webservice_permission()`

**Purpose**: Determine if user can access the webservice through organization roles

**Parameters**:
- `webservice`: The webservice being accessed
- `context`: Request context with connected user info
- `session`: Database session

**Returns**:
- `(access_type, error_code)` tuple
- `access_type`: Dict mapping organizations to IDs, or None
- `error_code`: Error string, or None

**Example**:
```python
access_type, error_code = await OrganizationPermission.check_webservice_permission(
    webservice=my_webservice,
    context=request_context,
    session=db_session
)

# access_type = {
#     "organization_role": {
#         "client": ["client-id-1", "client-id-2"]
#     }
# }
```

#### Method: `add_statement_access_constraints()`

**Purpose**: Add organization-based filtering to a database query

**Parameters**:
- `stmt`: SQLAlchemy SELECT statement
- `or_where`: Binary expression for OR conditions
- `context`: Request context with access_type
- `entity_class`: Entity being queried

**Returns**:
- `(modified_stmt, modified_or_where)` tuple

**Example**:
```python
stmt, or_where = await OrganizationPermission.add_statement_access_constraints(
    stmt=select(Project),
    or_where=false(),
    context=request_context,
    entity_class=Project
)

# stmt now includes: WHERE project.client_id IN (1, 2)
```

### Service Class: `UserService`

**Location**: `lys.apps.organization.modules.user.services`

#### Method: `get_user_organization_roles()`

**Purpose**: Retrieve all organization roles assigned to a user

**Parameters**:
- `user_id`: User ID to query
- `session`: Database session
- `webservice_id`: Optional filter by webservice

**Returns**:
- List of `ClientUserRole` entities with preloaded relationships

**Performance**:
- Uses eager loading to avoid N+1 queries
- 3 queries total regardless of number of roles

**Example**:
```python
roles = await UserService.get_user_organization_roles(
    user_id="user-123",
    session=db_session,
    webservice_id="list_projects"
)

# Returns: [ClientUserRole(...), ClientUserRole(...)]
# With preloaded: role.client_user.client
```

## Configuration

### Registering the Permission

In `app/src/settings.py`:

```python
from lys.apps.organization.permission import OrganizationPermission

app_settings.configure(
    permissions=[
        UserAuthPermission,
        UserRolePermission,
        OrganizationPermission  # Add organization permission
    ]
)
```

### Creating an Access Level

In `lys.apps.organization.consts`:

```python
ORGANIZATION_ROLE_ACCESS_LEVEL = "ORGANIZATION_ROLE"
```

In fixtures (`lys.apps.organization.modules.access_level.fixtures`):

```python
data_list = [
    {
        "id": ORGANIZATION_ROLE_ACCESS_LEVEL,
        "attributes": {"enabled": True}
    }
]
```

### Configuring a Webservice

```python
@lys_connection(
    ensure_type=ProjectNode,
    is_public=False,
    access_levels=[ORGANIZATION_ROLE_ACCESS_LEVEL],
    description="List projects for user's organizations"
)
async def list_projects(self, info: Info) -> Select:
    # This webservice now requires organization-role access
    # Users can only see projects from their organizations
    pass
```

## Extension Points

### Adding New Organization Types

To add a new organization type (e.g., Division):

1. **Create Entity**:
```python
class Division(AbstractOrganizationEntity):
    __tablename__ = "division"
    parent_client_id = Column(ForeignKey("client.id"))
    # ...
```

2. **Create UserRole Entity**:
```python
class DivisionUserRole(AbstractUserOrganizationRoleEntity):
    __tablename__ = "division_user_role"
    division_user_id = Column(ForeignKey("division_user.id"))
    # ...
```

3. **Update Service**:
```python
# Extend get_user_organization_roles to query DivisionUserRole
```

4. **Implement Filters**:
```python
@classmethod
def organization_accessing_filters(cls, stmt, organization_id_dict):
    return stmt, [cls.division_id.in_(organization_id_dict.get("division", []))]
```

### Custom Permission Logic

To add custom permission logic (e.g., license checking):

```python
# In OrganizationPermission.check_webservice_permission()

if ORGANIZATION_ROLE_ACCESS_LEVEL in access_levels:
    # Check organization license
    has_valid_license = await check_organization_license(
        organization_id=user_organization.id,
        feature_id=webservice.id,
        session=session
    )

    if not has_valid_license:
        return None, "LICENSE_REQUIRED"

    # Continue with role checking...
```

## Testing Recommendations

### Unit Tests

1. **Test permission check**:
   - User with role → access granted
   - User without role → access denied
   - Disabled role → access denied
   - Multiple organizations → correct access map
   - Client owner without role → access granted to owned client
   - Client owner with roles → access to owned client + role-based clients (no duplicates)

2. **Test query filtering**:
   - Data from accessible organizations returned
   - Data from inaccessible organizations excluded
   - Multiple organizations correctly filtered

3. **Test edge cases**:
   - No connected user → access denied
   - Webservice not in role → access denied
   - Empty organization roles → access denied

### Integration Tests

1. **Test complete flow**:
   - Create user, client, role
   - Assign role to user
   - Make API request
   - Verify data isolation

2. **Test multi-tenant scenarios**:
   - Multiple users, multiple clients
   - Verify each user sees only their data
   - Verify consultant sees multiple clients

3. **Test hierarchical access**:
   - Parent-child organizations
   - Verify inheritance works correctly

## Troubleshooting

### User Cannot Access Webservice

**Checklist**:
1. Is the user connected? Check `context.connected_user`
2. Does the webservice require `ORGANIZATION_ROLE_ACCESS_LEVEL`?
3. Is the user the owner of a client? Check `client.owner_id = user.id` (automatic access)
4. Is the user a member of an organization? Check `ClientUser` exists
5. Does the user have a role in that organization? Check `ClientUserRole` exists
6. Is the role enabled? Check `role.enabled = True`
7. Does the role include this webservice? Check `role.webservices` relationship

### User Sees Wrong Data

**Checklist**:
1. Check access map: Does it include the correct organization IDs?
2. Check entity filter: Does `organization_accessing_filters()` use the correct column?
3. Check query: Is the WHERE clause correctly applied?
4. Check eager loading: Are relationships preloaded to avoid lazy loading issues?

### Performance Issues

**Checklist**:
1. Enable SQL logging: Check for N+1 queries
2. Verify eager loading: Ensure `selectinload()` is used
3. Check query count: Should be 3 queries for role check
4. Profile slow queries: Use database query analyzer

## Future Enhancements

1. **License Management**: Add license checking to control feature access per organization
2. **Audit Logging**: Track all organization access for compliance
3. **Dynamic Hierarchies**: Support arbitrary depth organization hierarchies
4. **Caching**: Cache organization roles for better performance
5. **Multi-Database**: Support organization data in separate databases for tenant isolation