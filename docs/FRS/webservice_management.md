# Webservice Management

## Overview

This document describes the webservice management system in the lys framework. Webservices are GraphQL operations (queries and mutations) that are automatically registered, can be overridden with different parameters, or disabled entirely.

## Table of Contents

1. [Webservice Types](#webservice-types)
2. [Webservice Creation](#webservice-creation)
3. [Webservice Override - Metadata Only](#webservice-override---metadata-only)
4. [Webservice Override - Full Implementation](#webservice-override---full-implementation)
5. [Webservice Disabling](#webservice-disabling)
6. [Best Practices](#best-practices)

---

## Webservice Types

The lys framework provides five different types of webservices, each designed for specific use cases. All are GraphQL operations (queries or mutations) that are automatically registered and managed.

### 1. lys_getter - Retrieve Single Entity (Query)

**Purpose:** Fetch a single entity by ID with automatic permission checks.

**Key Features:**
- Automatically fetches entity from database
- Built-in permission validation (access levels, ownership)
- Returns single entity or null
- Typically used with OWNER access level

**Function Signature:**
```python
@lys_getter(
    ensure_type: Type[NodeInterface],
    is_public: bool = False,
    access_levels: List[str] = None,
    is_licenced: bool = True,
    allow_override: bool = True,
    description: str = ""
)
```

**Example:**
```python
@register_query("graphql")
@strawberry.type
class UserQuery(Query):
    @lys_getter(
        UserNode,
        is_public=False,
        access_levels=[OWNER_ACCESS_LEVEL],
        is_licenced=False,
        description="Return user information."
    )
    async def user(self):
        """
        Get user by ID with owner permission check.

        GraphQL Query:
            query {
                user(id: "user-123") {
                    id
                    emailAddress { address }
                    privateData { firstName lastName }
                }
            }
        """
        pass
```

**When to Use:**
- Fetching user profile (owner only)
- Getting organization details (member access)
- Retrieving single record with permission checks
- Read operations on single entities

---

### 2. lys_connection - Retrieve List of Entities (Query)

**Purpose:** Fetch a paginated list of entities with filtering and ordering.

**Key Features:**
- Cursor-based pagination (Relay specification)
- Automatic permission filtering
- Support for search and filters
- Order by capabilities
- Returns connection with edges and pageInfo

**Function Signature:**
```python
@lys_connection(
    ensure_type: Type[NodeInterface],
    is_public: bool = False,
    access_levels: List[str] = None,
    is_licenced: bool = True,
    allow_override: bool = True,
    description: str = ""
)
```

**Example:**
```python
@register_query("graphql")
@strawberry.type
class UserQuery(Query):
    @lys_connection(
        UserNode,
        is_public=False,
        is_licenced=False,
        description="Return all users. Only accessible to super users."
    )
    async def all_users(self, info: Info, search: Optional[str] = None) -> Select:
        """
        Get paginated list of users with search.

        GraphQL Query:
            query {
                allUsers(first: 10, search: "john", orderBy: {field: "created_at", direction: DESC}) {
                    edges {
                        node {
                            id
                            emailAddress { address }
                        }
                        cursor
                    }
                    pageInfo {
                        hasNextPage
                        hasPreviousPage
                    }
                }
            }
        """
        from sqlalchemy import or_

        entity_type = info.context.app_manager.get_entity("user")
        email_entity = info.context.app_manager.get_entity("user_email_address")
        private_data_entity = info.context.app_manager.get_entity("user_private_data")

        # Build query with joins for search and order by
        stmt = (
            select(entity_type)
            .join(email_entity)
            .join(private_data_entity)
            .order_by(entity_type.created_at.desc())
        )

        # Apply search filter
        if search:
            search_pattern = f"%{search.lower()}%"
            stmt = stmt.where(
                or_(
                    email_entity.id.ilike(search_pattern),
                    private_data_entity.first_name.ilike(search_pattern),
                    private_data_entity.last_name.ilike(search_pattern)
                )
            )

        return stmt
```

**When to Use:**
- Listing users with pagination
- Searching through entities
- Admin dashboards with data tables
- Any list view with filtering

**Important Notes:**
- Must return SQLAlchemy `Select` statement
- Pagination, permission filtering, and ordering are handled automatically
- Include necessary joins for search and order_by fields
- Define `order_by_attribute_map` on Node for custom ordering

---

### 3. lys_creation - Create New Entity (Mutation)

**Purpose:** Create a new entity with validation and permission checks.

**Key Features:**
- Automatic input validation (Pydantic)
- Permission checks before creation
- Returns created entity
- Supports background tasks

**Function Signature:**
```python
@lys_creation(
    ensure_type: Type[NodeInterface],
    is_public: bool = False,
    access_levels: List[str] = None,
    is_licenced: bool = True,
    allow_override: bool = True,
    description: str = ""
)
```

**Example:**
```python
@register_mutation("graphql")
@strawberry.type
class UserMutation(Mutation):
    @lys_creation(
        ensure_type=UserNode,
        is_public=False,
        access_levels=[ROLE_ACCESS_LEVEL],
        is_licenced=False,
        description="Create a new user with role assignments."
    )
    async def create_user(self, inputs: CreateUserWithRolesInput, info: Info):
        """
        Create a new user with roles.

        GraphQL Mutation:
            mutation {
                createUser(inputs: {
                    email: "john@example.com"
                    password: "SecurePass123"
                    languageCode: "en"
                    firstName: "John"
                    lastName: "Doe"
                    roleCodes: ["USER_ADMIN_ROLE"]
                }) {
                    id
                    emailAddress { address }
                }
            }
        """
        input_data = inputs.to_pydantic()
        session = info.context.session
        connected_user = info.context.connected_user
        user_service = info.context.app_manager.get_service("user")

        # Business logic validation
        is_super_user = connected_user.get("is_super_user", False)
        if input_data.roles and not is_super_user:
            # Check role assignment permissions
            connected_user_entity = await user_service.get_by_id(connected_user["id"], session)
            connected_user_role_ids = {role.id for role in connected_user_entity.roles}
            requested_role_ids = set(input_data.roles)
            unauthorized_roles = requested_role_ids - connected_user_role_ids

            if unauthorized_roles:
                raise LysError(
                    UNAUTHORIZED_ROLE_ASSIGNMENT,
                    f"You cannot assign roles you don't have: {', '.join(unauthorized_roles)}"
                )

        # Create entity via service
        user = await user_service.create_user(
            session=session,
            email=input_data.email,
            password=input_data.password,
            language_id=input_data.language_code,
            send_verification_email=True,
            background_tasks=info.context.background_tasks,
            roles=input_data.role_codes,
            first_name=input_data.first_name,
            last_name=input_data.last_name,
            gender_id=input_data.gender_code
        )

        return user
```

**When to Use:**
- Creating new users
- Adding organizations
- Creating new records
- Any POST-like operation

**Important Notes:**
- Define Strawberry Input types (with Pydantic models)
- Implement validation logic before service call
- Use services for business logic
- Return the created entity

---

### 4. lys_edition - Update Existing Entity (Mutation)

**Purpose:** Update an existing entity with automatic fetching and permission checks.

**Key Features:**
- Automatically fetches entity by ID
- Validates ownership/permissions before update
- Takes entity as parameter (not ID)
- Returns updated entity

**Function Signature:**
```python
@lys_edition(
    ensure_type: Type[NodeInterface],
    is_public: bool = False,
    access_levels: List[str] = None,
    is_licenced: bool = True,
    allow_override: bool = True,
    description: str = ""
)
```

**Example:**
```python
@register_mutation("graphql")
@strawberry.type
class UserMutation(Mutation):
    @lys_edition(
        ensure_type=UserNode,
        is_public=False,
        access_levels=[OWNER_ACCESS_LEVEL],
        is_licenced=False,
        description="Update user email address. Only the owner can update their own email."
    )
    async def update_email(self, obj: User, inputs: UpdateEmailInput, info: Info):
        """
        Update user email with verification.

        GraphQL Mutation:
            mutation {
                updateEmail(id: "user-123", inputs: {
                    newEmail: "newemail@example.com"
                }) {
                    id
                    emailAddress { address validatedAt }
                }
            }

        Note: The 'obj' parameter is automatically populated by lys_edition.
              It fetches the User entity and validates permissions before calling this function.
        """
        input_data = inputs.to_pydantic()
        session = info.context.session
        user_service = info.context.app_manager.get_service("user")

        # Delegate to service
        await user_service.update_email(
            user=obj,
            new_email=input_data.new_email,
            session=session,
            background_tasks=info.context.background_tasks
        )

        logger.info(f"User {obj.id} email updated to: {input_data.new_email}")

        return obj
```

**When to Use:**
- Updating user profile
- Editing organization settings
- Modifying existing records
- Any PUT/PATCH-like operation

**Important Notes:**
- First parameter MUST be `obj: EntityType` (entity is auto-fetched)
- Entity is fetched and validated automatically
- Permission checks happen before function execution
- Return the updated entity

---

### 5. lys_field - Custom Mutation (Mutation)

**Purpose:** Custom mutations that don't follow standard CRUD patterns.

**Key Features:**
- Maximum flexibility
- No automatic entity fetching
- Custom return types allowed
- For complex business operations

**Function Signature:**
```python
@lys_field(
    ensure_type: Type[NodeInterface],
    is_public: bool = False,
    access_levels: List[str] = None,
    is_licenced: bool = True,
    allow_override: bool = True,
    description: str = ""
)
```

**Example:**
```python
@register_mutation("graphql")
@strawberry.type
class UserMutation(Mutation):
    @lys_field(
        ensure_type=PasswordResetRequestNode,
        is_public=True,
        is_licenced=False,
        description="Send a password reset email to the user."
    )
    async def request_password_reset(self, email: str, info: Info) -> PasswordResetRequestNode:
        """
        Request password reset without authentication.

        GraphQL Mutation:
            mutation {
                requestPasswordReset(email: "user@example.com") {
                    success
                }
            }
        """
        node = PasswordResetRequestNode.get_effective_node()
        session = info.context.session
        user_service = node.service_class

        # Custom business logic
        await user_service.request_password_reset(
            email=email,
            session=session,
            background_tasks=info.context.background_tasks
        )

        logger.info(f"Password reset requested for email: {email}")

        return node(success=True)

    @lys_field(
        ensure_type=ResetPasswordNode,
        is_public=True,
        is_licenced=False,
        description="Reset user password using a one-time token from email."
    )
    async def reset_password(self, inputs: ResetPasswordInput, info: Info) -> ResetPasswordNode:
        """
        Reset password using token.

        GraphQL Mutation:
            mutation {
                resetPassword(inputs: {
                    token: "abc-123-def-456"
                    newPassword: "NewSecurePass123"
                }) {
                    success
                }
            }
        """
        input_data = inputs.to_pydantic()
        node = ResetPasswordNode.get_effective_node()
        session = info.context.session
        user_service = node.service_class

        await user_service.reset_password(
            token=input_data.token,
            new_password=input_data.new_password,
            session=session
        )

        logger.info("Password successfully reset using token")

        return node(success=True)
```

**When to Use:**
- Password reset workflows
- Email verification
- Complex multi-step operations
- Operations not tied to single entity
- Public endpoints (no authentication)
- Custom return types (success flags, etc.)

**Important Notes:**
- Full control over parameters and logic
- Define custom return Node types
- Can be public (is_public=True)
- No automatic entity fetching

---

### Comparison Table

| Type | Operation | Auto-Fetch | Return Type | Use Case |
|------|-----------|------------|-------------|----------|
| **lys_getter** | Query | ✅ Single entity | Entity Node | Get single record by ID |
| **lys_connection** | Query | ✅ List | Connection (paginated) | List records with filtering |
| **lys_creation** | Mutation | ❌ None | Entity Node | Create new record |
| **lys_edition** | Mutation | ✅ Single entity | Entity Node | Update existing record |
| **lys_field** | Mutation | ❌ None | Custom Node | Complex operations |

---

## Webservice Creation

### Basic Registration

Webservices are automatically registered when using lys decorators (`@lys_getter`, `@lys_creation`, `@lys_edition`, `@lys_field`, `@lys_connection`).

**Example - Query with Owner Access:**

```python
@register_query("graphql")
@strawberry.type
class UserQuery(Query):
    @lys_getter(
        UserNode,
        is_public=False,
        access_levels=[OWNER_ACCESS_LEVEL],
        is_licenced=False,
        description="Return user information."
    )
    async def user(self):
        pass
```

**Example - Mutation with Business Logic:**

```python
@register_mutation("graphql")
@strawberry.type
class UserMutation(Mutation):
    @lys_edition(
        ensure_type=UserNode,
        is_public=False,
        access_levels=[OWNER_ACCESS_LEVEL],
        is_licenced=False,
        description="Update user email address."
    )
    async def update_email(
        self,
        obj: User,
        inputs: UpdateEmailInput,
        info: Info
    ):
        """Update user email address and send verification email."""
        input_data = inputs.to_pydantic()
        session = info.context.session
        user_service = info.context.app_manager.get_service("user")

        await user_service.update_email(
            user=obj,
            new_email=input_data.new_email,
            session=session,
            background_tasks=info.context.background_tasks
        )

        return obj
```

### Registration Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `is_public` | `bool` or `WebserviceIsPublicType` | `False` | Controls public access (no authentication required) |
| `access_levels` | `List[str]` | `None` | Required access levels (e.g., `OWNER_ACCESS_LEVEL`, `ROLE_ACCESS_LEVEL`) |
| `is_licenced` | `bool` | `True` | Whether license check is required |
| `enabled` | `bool` | `True` | Whether the webservice is active |
| `allow_override` | `bool` | `True` | Whether the webservice can be overridden in other apps |
| `description` | `str` | - | Description of the webservice functionality |

---

## Webservice Override - Metadata Only

### When to Use

Use `override_webservice()` when you want to **modify only the metadata** of an existing webservice without changing its implementation logic. This is the recommended approach for:

- Extending access levels (e.g., adding ROLE access to an OWNER-only webservice)
- Updating descriptions
- Changing public/private status
- Modifying license requirements

### Function Signature

```python
def override_webservice(
    name: str,
    access_levels: List[str] | None = None,
    description: str | None = None,
    is_public: WebserviceIsPublicType | None = None,
    is_licenced: bool | None = None,
    enabled: bool | None = None,
    register: AppRegister = None
)
```

### Example - Extending Access Levels

**Original webservice in `user_auth/modules/user/webservices.py`:**

```python
@lys_edition(
    ensure_type=UserNode,
    is_public=False,
    access_levels=[OWNER_ACCESS_LEVEL],  # Only owner can access
    is_licenced=False,
    description="Update user email address."
)
async def update_email(self, obj: User, inputs: UpdateEmailInput, info: Info):
    # Implementation remains in user_auth
    ...
```

**Override in `user_role/modules/user/webservices.py`:**

```python
from lys.core.registers import override_webservice
from lys.core.consts.webservices import OWNER_ACCESS_LEVEL
from lys.apps.user_role.consts import ROLE_ACCESS_LEVEL

# Extend access levels to include ROLE without duplicating code
override_webservice(
    name="update_email",
    access_levels=[OWNER_ACCESS_LEVEL, ROLE_ACCESS_LEVEL],
    description="Update user email address. Accessible to owner or users with ROLE access level."
)
```

### Multiple Overrides Example

```python
# Override multiple webservices from user_auth to extend access levels to include ROLE
override_webservice(
    name="user",
    access_levels=[OWNER_ACCESS_LEVEL, ROLE_ACCESS_LEVEL],
    description="Return user information. Accessible to owner or users with ROLE access level."
)

override_webservice(
    name="update_email",
    access_levels=[OWNER_ACCESS_LEVEL, ROLE_ACCESS_LEVEL],
    description="Update user email address. Accessible to owner or users with ROLE access level."
)

override_webservice(
    name="update_password",
    access_levels=[OWNER_ACCESS_LEVEL, ROLE_ACCESS_LEVEL],
    description="Update user password. Accessible to owner or users with ROLE access level."
)

override_webservice(
    name="update_user_private_data",
    access_levels=[OWNER_ACCESS_LEVEL, ROLE_ACCESS_LEVEL],
    description="Update user private data. Accessible to owner or users with ROLE access level."
)
```

### Key Characteristics

- ✅ **No code duplication** - Implementation stays in the original app
- ✅ **Maintainability** - Changes to business logic only need to happen in one place
- ✅ **Clear intent** - Explicitly shows what metadata is being changed
- ✅ **Type-safe** - Raises `ValueError` if webservice doesn't exist
- ⚠️ **Warning on no-op** - Logs warning if no parameters are provided

---

## Webservice Override - Full Implementation

### When to Use

Use full implementation override (with `allow_override=True`) when you need to **change the business logic** of an existing webservice. This is necessary when:

- Input types differ (e.g., adding role assignment to user creation)
- Additional validation is required
- Different service methods need to be called
- Business logic fundamentally differs from the base implementation

### Example - User Creation with Roles

**Original webservice in `user_auth/modules/user/webservices.py`:**

```python
@lys_creation(
    ensure_type=UserNode,
    is_public=False,
    is_licenced=False,
    description="Create a new regular user. Only accessible to super users."
)
async def create_user(self, inputs: CreateUserInput, info: Info):
    """Create a user without role assignment."""
    input_data = inputs.to_pydantic()
    session = info.context.session
    user_service = info.context.app_manager.get_service("user")

    # No role assignment
    user = await user_service.create_user(
        session=session,
        email=input_data.email,
        password=input_data.password,
        language_id=input_data.language_code,
        send_verification_email=True,
        background_tasks=info.context.background_tasks,
        first_name=input_data.first_name,
        last_name=input_data.last_name,
        gender_id=input_data.gender_code
    )

    return user
```

**Override in `user_role/modules/user/webservices.py`:**

```python
@register_mutation("graphql")
@strawberry.type
class UserMutation(Mutation):
    @lys_creation(
        ensure_type=UserNode,
        is_public=False,
        access_levels=[ROLE_ACCESS_LEVEL],
        is_licenced=False,
        allow_override=True,  # Explicitly allow override
        description="Create a new user with role assignments."
    )
    async def create_user(self, inputs: CreateUserWithRolesInput, info: Info):
        """
        Create a user with role assignment validation.

        Uses different input type (CreateUserWithRolesInput) and
        implements role validation logic.
        """
        input_data = inputs.to_pydantic()
        session = info.context.session
        connected_user = info.context.connected_user
        user_service = info.context.app_manager.get_service("user")

        is_super_user = connected_user.get("is_super_user", False)

        # Additional validation logic for roles
        if input_data.role_codes and not is_super_user:
            connected_user_entity = await user_service.get_by_id(connected_user["id"], session)
            connected_user_role_codes = {role.id for role in connected_user_entity.roles}
            requested_role_codes = set(input_data.role_codes)
            unauthorized_roles = requested_role_codes - connected_user_role_codes

            if unauthorized_roles:
                raise LysError(
                    UNAUTHORIZED_ROLE_ASSIGNMENT,
                    f"You cannot assign roles you don't have: {', '.join(unauthorized_roles)}"
                )

        # Call service with roles parameter
        user = await user_service.create_user(
            session=session,
            email=input_data.email,
            password=input_data.password,
            language_id=input_data.language_code,
            send_verification_email=True,
            background_tasks=info.context.background_tasks,
            roles=input_data.role_codes,  # Additional parameter
            first_name=input_data.first_name,
            last_name=input_data.last_name,
            gender_id=input_data.gender_code
        )

        return user
```

### Key Characteristics

- ⚠️ **Code duplication** - Full implementation must be written
- ✅ **Custom logic** - Can implement different business rules
- ✅ **Different inputs** - Can use different input types
- ⚠️ **Maintenance overhead** - Changes need to be synchronized manually
- ✅ **Explicit override** - `allow_override=True` makes intent clear

---

## Webservice Disabling

### When to Use

Use `disable_webservice()` when you want to **completely disable** a webservice without removing its registration. Useful for:

- Temporarily disabling features
- Security lockdown
- Feature flags
- Environment-specific behavior (e.g., disable certain operations in production)

### Function Signature

```python
def disable_webservice(
    name: str,
    register: AppRegister = None
)
```

### Example

```python
from lys.core.registers import disable_webservice

# Disable super user creation in production environment
disable_webservice("create_super_user")

# Disable dangerous operations
disable_webservice("delete_all_users")
disable_webservice("reset_database")
```

### Example - Environment-Based Disabling

```python
from lys.core.configs import app_settings
from lys.core.consts.environments import EnvironmentEnum
from lys.core.registers import disable_webservice

# Disable certain webservices in production
if app_settings.env == EnvironmentEnum.PROD:
    disable_webservice("create_super_user")
    disable_webservice("import_test_data")
    disable_webservice("reset_password_without_token")
```

### Key Characteristics

- ✅ **Quick disable** - One line of code
- ✅ **Reversible** - Can be re-enabled programmatically
- ✅ **Safe** - Doesn't delete the webservice, just marks it disabled
- ⚠️ **Database impact** - Updates fixture in database
- ✅ **Type-safe** - Raises `ValueError` if webservice doesn't exist

---

## Best Practices

### 1. Choose the Right Approach

| Scenario | Recommended Approach |
|----------|---------------------|
| Extend access levels only | `override_webservice()` |
| Update description only | `override_webservice()` |
| Change multiple metadata fields | `override_webservice()` |
| Different input types | Full implementation override |
| Additional business logic | Full implementation override |
| Custom validation | Full implementation override |
| Disable feature | `disable_webservice()` |

### 2. Metadata Override Pattern

```python
# ✅ GOOD - Clear, concise, no duplication
override_webservice(
    name="update_email",
    access_levels=[OWNER_ACCESS_LEVEL, ROLE_ACCESS_LEVEL],
    description="Update email. Accessible to owner or ROLE users."
)

# ❌ BAD - Full implementation for metadata change only
@lys_edition(
    ensure_type=UserNode,
    is_public=False,
    access_levels=[OWNER_ACCESS_LEVEL, ROLE_ACCESS_LEVEL],
    is_licenced=False,
    allow_override=True,
    description="Update email. Accessible to owner or ROLE users."
)
async def update_email(self, obj: User, inputs: UpdateEmailInput, info: Info):
    # Duplicated implementation from user_auth
    input_data = inputs.to_pydantic()
    session = info.context.session
    user_service = info.context.app_manager.get_service("user")
    await user_service.update_email(...)
    return obj
```

### 3. Organization

Group related overrides together with clear comments:

```python
# Override webservices from user_auth to extend access levels to include ROLE
override_webservice(
    name="user",
    access_levels=[OWNER_ACCESS_LEVEL, ROLE_ACCESS_LEVEL]
)

override_webservice(
    name="update_email",
    access_levels=[OWNER_ACCESS_LEVEL, ROLE_ACCESS_LEVEL]
)

override_webservice(
    name="update_password",
    access_levels=[OWNER_ACCESS_LEVEL, ROLE_ACCESS_LEVEL]
)
```

### 4. Error Handling

Both `override_webservice()` and `disable_webservice()` raise explicit errors:

```python
# ❌ Will raise ValueError with helpful message
override_webservice(
    name="nonexistent_webservice",
    access_levels=[OWNER_ACCESS_LEVEL]
)

# Error message:
# ValueError: Webservice 'nonexistent_webservice' not found in registry and cannot be overridden.
# Available webservices: create_user, update_email, update_password, ...
# Make sure the webservice is registered before attempting to override it.
```

### 5. Documentation

Always document why you're overriding or disabling:

```python
# Override to allow USER_ADMIN role to manage user profiles
# This enables delegated user management without granting super user privileges
override_webservice(
    name="update_user_private_data",
    access_levels=[OWNER_ACCESS_LEVEL, ROLE_ACCESS_LEVEL],
    description="Update user private data. Accessible to owner or users with ROLE access level."
)

# Disable in production for security - super users should only be created via CLI
if app_settings.env == EnvironmentEnum.PROD:
    disable_webservice("create_super_user")
```

### 6. Testing Considerations

When overriding webservices, ensure:

1. **Permission tests** - Verify new access levels work correctly
2. **Regression tests** - Ensure original functionality still works
3. **Integration tests** - Test interaction between base and override apps

```python
# Test that ROLE access level can now access the webservice
async def test_update_email_with_role_access():
    # Setup user with ROLE access
    user_admin = create_user_with_role(USER_ADMIN_ROLE)
    target_user = create_regular_user()

    # Should succeed with ROLE access
    result = await execute_graphql(
        UPDATE_EMAIL_MUTATION,
        user=user_admin,
        variables={"userId": target_user.id, "newEmail": "new@example.com"}
    )

    assert result.errors is None
    assert result.data["updateEmail"]["success"] is True
```

---

## Summary

| Operation | Function | Use Case | Code Duplication |
|-----------|----------|----------|------------------|
| **Create** | Decorators (`@lys_getter`, etc.) | New webservice | No |
| **Override Metadata** | `override_webservice()` | Extend access, change description | No |
| **Override Implementation** | Full override with `allow_override=True` | Different logic, inputs, validation | Yes |
| **Disable** | `disable_webservice()` | Turn off feature | No |

**Recommendation**: Prefer `override_webservice()` over full implementation override whenever possible to minimize code duplication and maintenance overhead.