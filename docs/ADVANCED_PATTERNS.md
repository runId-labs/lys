# Advanced Patterns in Lys Framework

This document describes advanced usage patterns for the lys framework, including webservice overriding and fixture merging.

## Table of Contents

1. [Webservice Overriding](#webservice-overriding)
2. [Fixture Merging](#fixture-merging)
3. [Module-Qualified Fixture Names](#module-qualified-fixture-names)
4. [Access Level Configuration](#access-level-configuration)

---

## Webservice Overriding

### Overview

When multiple apps define a webservice with the same name, the **last registered webservice wins** by default. This allows apps to extend or modify webservices defined in base apps.

### Basic Example

```python
# In user_auth/modules/user/webservices.py
@register_query("graphql")
@strawberry.type
class UserQuery(Query):
    @lys_getter(
        UserNode,
        access_levels=[OWNER_ACCESS_LEVEL],
        description="Return user information."
    )
    async def user(self):
        pass
```

```python
# In user_role/modules/user/webservices.py
@register_query("graphql")
@strawberry.type
class UserQuery(Query):
    @lys_getter(
        UserNode,
        access_levels=[OWNER_ACCESS_LEVEL, ROLE_ACCESS_LEVEL],  # Extended access
        description="Return user information."
    )
    async def user(self):
        pass
```

**Result**: The `user` webservice will have `access_levels=[OWNER, ROLE]` because `user_role` is loaded after `user_auth`.

### Explicit Override Control

Use the `allow_override` parameter to control override behavior:

```python
@lys_getter(
    UserNode,
    access_levels=[OWNER_ACCESS_LEVEL],
    allow_override=False,  # Prevent accidental override
    description="Return user information."
)
async def user(self):
    pass
```

If another app tries to override this webservice, it will raise a `ValueError`.

### Override Logging

When a webservice is overridden, a warning is logged:

```
⚠ Overwriting webservice 'user' with new configuration
```

### App Loading Order

The order of apps in `settings.py` determines override priority:

```python
# In settings.py
app_settings.configure(
    apps=[
        "lys.apps.base",        # Loaded first
        "lys.apps.user_auth",   # Can override base
        "lys.apps.user_role",   # Can override user_auth (highest priority)
    ]
)
```

**Rule**: Apps loaded later can override webservices from apps loaded earlier.

---

## Fixture Merging

### Overview

Fixtures can add data to existing tables without deleting previous data using `delete_previous_data = False`.

### Basic Example

```python
# In user_auth/modules/access_level/fixtures.py
@register_fixture()
class AccessLevelFixtures(EntityFixtures[AccessLevelService]):
    model = ParametricEntityFixturesModel
    delete_previous_data = True  # Default: replace all data

    data_list = [
        {"id": "CONNECTED", "attributes": {"enabled": True}},
        {"id": "OWNER", "attributes": {"enabled": True}},
    ]
```

```python
# In user_role/modules/access_level/fixtures.py
@register_fixture()
class AccessLevelFixtures(EntityFixtures[AccessLevelService]):
    model = ParametricEntityFixturesModel
    delete_previous_data = False  # Add without deleting existing

    data_list = [
        {"id": "ROLE", "attributes": {"enabled": True}},
    ]
```

**Result**: The `access_level` table will contain all three records: `CONNECTED`, `OWNER`, and `ROLE`.

### delete_previous_data Behavior

| Value | Behavior for Parametric Entities | Behavior for Business Entities |
|-------|----------------------------------|--------------------------------|
| `True` (default) | Disable entities not in data_list | Delete all existing rows |
| `False` | Only add/update entities in data_list | Only add entities in data_list |

### Use Cases

**Add new reference data**:
```python
delete_previous_data = False  # Extend existing data
```

**Replace all data** (clean slate):
```python
delete_previous_data = True  # Remove old data
```

---

## Module-Qualified Fixture Names

### Problem

Multiple apps defining fixtures with the same class name caused conflicts:

```python
# user_auth/modules/access_level/fixtures.py
class AccessLevelFixtures(...):  # Conflict!
    pass

# user_role/modules/access_level/fixtures.py
class AccessLevelFixtures(...):  # Conflict!
    pass
```

### Solution

Fixtures are now identified by module-qualified names:

```
lys.apps.user_auth.modules.access_level.fixtures.AccessLevelFixtures
lys.apps.user_role.modules.access_level.fixtures.AccessLevelFixtures
```

**No code changes required** - this happens automatically.

### Benefits

- Multiple apps can use the same fixture class name
- Each fixture is uniquely identified
- No naming conflicts

---

## Access Level Configuration

### Multiple Access Levels (OR Logic)

Access levels use **OR logic** - a user needs ANY ONE of the specified access levels:

```python
@lys_getter(
    UserNode,
    access_levels=[OWNER_ACCESS_LEVEL, ROLE_ACCESS_LEVEL],
)
async def user(self):
    pass
```

**Access granted if user has**:
- OWNER access level **OR**
- ROLE access level **OR**
- Super admin status (always has access)

### Common Patterns

**Owner-only access**:
```python
access_levels=[OWNER_ACCESS_LEVEL]
```

**Connected users**:
```python
access_levels=[CONNECTED_ACCESS_LEVEL]
```

**Multiple roles** (any role grants access):
```python
access_levels=[ROLE_ACCESS_LEVEL, ADMIN_ACCESS_LEVEL, MODERATOR_ACCESS_LEVEL]
```

**Super admin only**:
```python
access_levels=[]  # Or omit the parameter
is_public=False
```

### Adding New Access Levels

1. Create constant:
```python
# In app/consts.py
MY_NEW_ACCESS_LEVEL = "MY_NEW_ACCESS"
```

2. Add fixture:
```python
@register_fixture()
class MyAccessLevelFixtures(EntityFixtures[AccessLevelService]):
    model = ParametricEntityFixturesModel
    delete_previous_data = False

    data_list = [
        {"id": MY_NEW_ACCESS_LEVEL, "attributes": {"enabled": True}}
    ]
```

3. Use in webservices:
```python
@lys_getter(
    MyNode,
    access_levels=[MY_NEW_ACCESS_LEVEL],
)
async def my_query(self):
    pass
```

---

## Best Practices

### Webservice Overriding

1. **Document overrides**: Add comments explaining why you're overriding
2. **Check app order**: Verify your app loads after the app you're overriding
3. **Use explicit override**: Set `allow_override=False` to prevent accidents
4. **Keep function names consistent**: Use the same GraphQL field name

### Fixture Merging

1. **Use `delete_previous_data=False`** when extending reference data
2. **Document dependencies**: Use `depends_on` parameter for fixture ordering
3. **Test fixture order**: Verify fixtures load in the correct sequence
4. **Validate data**: Ensure IDs don't conflict between fixtures

### Access Levels

1. **Use constants**: Never hardcode access level strings
2. **Create fixtures**: Always create access_level entries via fixtures
3. **Document requirements**: Explain which roles need which access levels
4. **Test permissions**: Verify access control works as expected

---

## Troubleshooting

### Webservice Not Overriding

**Symptom**: Your webservice override isn't taking effect

**Causes**:
1. App order incorrect in `settings.py`
2. Webservice name doesn't match
3. `allow_override=False` on the original webservice

**Solution**: Check app loading order and webservice names

### Access Level Not Found

**Symptom**: `AccessLevel 'ROLE' not found` error

**Causes**:
1. Access level fixture not loaded
2. Fixture has `delete_previous_data=True` and doesn't include the level
3. App not included in `settings.apps`

**Solution**: Add access level fixture with `delete_previous_data=False`

### Fixture Conflict

**Symptom**: `Fixture 'X' already registered` error

**Causes**:
1. Same module path defines fixture twice
2. Duplicate import

**Solution**: This should not happen with module-qualified names. Check for duplicate registrations in the same module.

---

## Examples

### Complete Override Example

```python
# Step 1: Base app defines webservice
# lys/apps/user_auth/modules/user/webservices.py
@register_query("graphql")
@strawberry.type
class UserQuery(Query):
    @lys_getter(
        UserNode,
        access_levels=[OWNER_ACCESS_LEVEL],
    )
    async def user(self):
        pass

# Step 2: Extension app overrides with more access levels
# lys/apps/user_role/modules/user/webservices.py
@register_query("graphql")
@strawberry.type
class UserQuery(Query):
    @lys_getter(
        UserNode,
        access_levels=[OWNER_ACCESS_LEVEL, ROLE_ACCESS_LEVEL],
    )
    async def user(self):
        pass

# Step 3: Add ROLE access level via fixture
# lys/apps/user_role/modules/access_level/fixtures.py
@register_fixture()
class AccessLevelFixtures(EntityFixtures[AccessLevelService]):
    model = ParametricEntityFixturesModel
    delete_previous_data = False  # Don't remove OWNER

    data_list = [
        {"id": ROLE_ACCESS_LEVEL, "attributes": {"enabled": True}}
    ]

# Step 4: Ensure correct app order in settings.py
app_settings.configure(
    apps=[
        "lys.apps.user_auth",   # Defines base webservice
        "lys.apps.user_role",   # Overrides webservice
    ]
)
```

**Result**: The `user` webservice accepts both OWNER and ROLE access levels.