# Internal Service-to-Service Communication

## Quick Reference

**Purpose**: Secure communication between microservices using short-lived JWT tokens.

**Key Files**:
- `lys/apps/base/middlewares.py` - ServiceAuthMiddleware
- `lys/apps/base/permissions.py` - InternalServicePermission
- `lys/core/utils/auth.py` - AuthUtils (token generation/validation)
- `lys/core/managers/app.py` - `_register_webservices_to_auth_server()`
- `lys/apps/base/modules/webservice/webservices.py` - registerWebservices mutation
- `lys/apps/base/modules/webservice/entities.py` - Webservice.app_name column

**Settings Configuration**:
```python
# Business microservice settings
settings.service_name = "billing-service"  # Identifies this microservice
settings.gateway_server_url = "http://gateway:4000"  # Apollo Gateway URL
settings.secret_key = "shared-secret"  # Must match Auth Server

# Auth Server middlewares
middlewares=[
    "lys.apps.base.middlewares.ServiceAuthMiddleware",
    "lys.apps.user_auth.middlewares.UserAuthMiddleware",
]

# Auth Server permissions
permissions=[
    "lys.apps.base.permissions.InternalServicePermission",
    "lys.apps.user_auth.permissions.AnonymousPermission",
    "lys.apps.user_auth.permissions.JWTPermission",
]
```

---

## Overview

Internal service communication enables business microservices to securely call Auth Server endpoints. This is used primarily for webservice registration at startup.

### Architecture

```
Business Microservice                     Auth Server
┌─────────────────────────────┐          ┌─────────────────────────────┐
│                             │          │                             │
│ At startup:                 │          │ ServiceAuthMiddleware:      │
│ 1. Generate service JWT     │  ──────► │ - Validates service token   │
│    (AuthUtils)              │          │ - Sets service_caller       │
│ 2. Call registerWebservices │          │                             │
│    mutation                 │          │ InternalServicePermission:  │
│                             │          │ - Checks INTERNAL_SERVICE   │
│ Headers:                    │          │   access level              │
│ Authorization: Service xxx  │          │ - Grants access if valid    │
│                             │          │                             │
│ registry.webservices ───────┼──────────┼► Webservice table           │
│                             │          │   (with app_name column)    │
└─────────────────────────────┘          └─────────────────────────────┘
```

### Key Principles

1. **Short-lived tokens**: Service JWT tokens expire in 1 minute (configurable)
2. **Shared secret**: Both services use the same `secret_key` for JWT signing
3. **Separate auth flow**: `Authorization: Service <token>` prefix distinguishes from user auth
4. **Access level control**: Only webservices with `INTERNAL_SERVICE` access level are accessible

---

## Service JWT Token

### Token Structure

```python
{
    "type": "service",           # Identifies as service token (not user)
    "service_name": "billing",   # Name of calling microservice
    "iat": 1734000000,           # Issued at timestamp
    "exp": 1734000060            # Expires in 1 minute
}
```

### Token Generation (AuthUtils)

```python
from lys.core.utils.auth import AuthUtils

auth_utils = AuthUtils(secret_key="shared-secret")
token = auth_utils.generate_token(
    service_name="billing-service",
    expiration_minutes=1  # Default: 1 minute
)
# Returns: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

### Token Validation

```python
try:
    payload = auth_utils.decode_token(token)
    # payload = {"type": "service", "service_name": "billing", ...}
except ExpiredSignatureError:
    # Token expired
except InvalidTokenError:
    # Invalid token or not a service token
```

---

## Components

### ServiceAuthMiddleware

**File**: `lys/apps/base/middlewares.py`

Validates incoming service JWT tokens and injects caller context.

```python
class ServiceAuthMiddleware(MiddlewareInterface, BaseHTTPMiddleware):
    AUTHORIZATION_PREFIX = "Service "

    async def dispatch(self, request, call_next):
        auth_header = request.headers.get("Authorization", "")

        if auth_header.startswith(self.AUTHORIZATION_PREFIX):
            token = auth_header[len(self.AUTHORIZATION_PREFIX):]
            try:
                service_caller = self.auth_utils.decode_token(token)
                request.state.service_caller = service_caller
            except (ExpiredSignatureError, InvalidTokenError):
                request.state.service_caller = None

        return await call_next(request)
```

**Context access**:
```python
# In GraphQL resolver or permission
service_caller = context.service_caller
# Returns: {"type": "service", "service_name": "billing", ...} or None
```

### InternalServicePermission

**File**: `lys/apps/base/permissions.py`

Grants access to webservices marked with `INTERNAL_SERVICE` access level.

```python
class InternalServicePermission(PermissionInterface):
    @classmethod
    async def check_webservice_permission(cls, webservice_id, context):
        service_caller = context.service_caller

        # No service caller = let other permissions handle
        if service_caller is None:
            return None, None

        # Check if webservice allows internal service access
        webservice_config = context.app_manager.registry.webservices.get(webservice_id, {})
        access_levels = webservice_config.get("attributes", {}).get("access_levels", [])

        if INTERNAL_SERVICE_ACCESS_LEVEL not in access_levels:
            return None, None

        # Service authenticated and webservice allows internal access
        return True, None
```

### INTERNAL_SERVICE Access Level

**File**: `lys/core/consts/webservices.py`

```python
INTERNAL_SERVICE_ACCESS_LEVEL = "INTERNAL_SERVICE"
```

**Fixture**: `lys/apps/base/modules/access_level/fixtures.py`

```python
data_list = [
    {
        "id": INTERNAL_SERVICE_ACCESS_LEVEL,
        "attributes": {
            "enabled": True,
            "description": "Grants access for internal service-to-service communication."
        }
    }
]
```

---

## Webservice Registration Flow

### Trigger

Called automatically at startup in `AppManager._register_webservices_to_auth_server()`.

### Skip Conditions

Registration is skipped if:
- `gateway_server_url` is not configured
- `service_name` is not configured
- This is the Auth Server itself (has `webservice` entity in registry)

### Process

```
1. Business microservice starts
2. AppManager._register_webservices_to_auth_server() called
3. Generate service JWT token with AuthUtils
4. Collect webservices from registry.webservices
5. Call registerWebservices GraphQL mutation on Auth Server
6. Auth Server validates token via ServiceAuthMiddleware
7. InternalServicePermission grants access (INTERNAL_SERVICE level)
8. WebserviceService.register_webservices() upserts to database
9. Webservice.app_name set from service_caller.service_name
```

### GraphQL Mutation

```graphql
mutation RegisterWebservices($webservices: [WebserviceFixturesInput!]!) {
    registerWebservices(webservices: $webservices) {
        success
        registeredCount
        message
    }
}
```

### Webservice Entity

```python
class Webservice(AbstractWebservice):
    is_licenced: Mapped[bool]
    app_name: Mapped[str]  # Set from service_caller.service_name
    # ... access_levels relationship
```

---

## Defining Internal-Only Webservices

Use `access_levels=[INTERNAL_SERVICE_ACCESS_LEVEL]` on webservice definition:

```python
from lys.core.consts.webservices import INTERNAL_SERVICE_ACCESS_LEVEL

@register_mutation()
class WebserviceMutation(Mutation):
    @lys_field(
        ensure_type=RegisterWebservicesNode,
        access_levels=[INTERNAL_SERVICE_ACCESS_LEVEL],  # Internal only
        is_licenced=False,
        description="Register webservices from a business microservice."
    )
    async def register_webservices(self, info, webservices):
        # Only accessible via service JWT, not user JWT
        ...
```

---

## Configuration Checklist

### Business Microservice

```python
settings.service_name = "my-service"           # Required
settings.gateway_server_url = "http://gateway:4000"  # Required
settings.secret_key = "shared-secret"          # Must match Auth Server
```

### Auth Server

```python
settings.secret_key = "shared-secret"  # Must match business services

middlewares = [
    "lys.apps.base.middlewares.ServiceAuthMiddleware",   # Before UserAuthMiddleware
    "lys.apps.user_auth.middlewares.UserAuthMiddleware",
]

permissions = [
    "lys.apps.base.permissions.InternalServicePermission",  # First in chain
    "lys.apps.user_auth.permissions.AnonymousPermission",
    "lys.apps.user_auth.permissions.JWTPermission",
]
```

---

## Troubleshooting

### "Registration failed: HTTP 401"

- Verify `secret_key` matches between services
- Check `ServiceAuthMiddleware` is in Auth Server middlewares

### "Registration skipped: gateway_server_url not configured"

- Set `settings.gateway_server_url` in business microservice

### "Webservice not found in registry"

- Ensure webservices are defined with `@lys_field` or `@lys_connection`
- Check webservices module is loaded (in `__submodules__`)

### Service caller is None in permission check

- Verify `Authorization: Service <token>` header format
- Check token not expired (default 1 minute lifetime)
- Verify `ServiceAuthMiddleware` is registered before permission check

### Permission denied for internal webservice

- Verify webservice has `access_levels=[INTERNAL_SERVICE_ACCESS_LEVEL]`
- Check `InternalServicePermission` is in permissions list
- Verify permission order (InternalServicePermission should be first)