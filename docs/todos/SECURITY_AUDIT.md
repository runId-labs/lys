# Security Audit - Pre-Production Remediation Guide

This document details every security finding from the pre-production audit of the Lys framework.
Each finding includes an explanation of the problem, the attack scenario, and a prototype solution
ready to be adapted and integrated.

---

## Table of Contents

| # | Section | Severity | Priority |
|---|---------|----------|----------|
| ~~C1~~ | ~~[Mollie Webhook Without Signature Verification](#c1-mollie-webhook-without-signature-verification)~~ | ~~CRITICAL~~ | INVALID |
| C2 | [Missing `aud`/`iss` Claims in JWT Tokens](#c2-missing-audiss-claims-in-jwt-tokens) | CRITICAL | Before prod |
| C3 | [Cross-Tenant Data Leak via Empty Organization Filters](#c3-cross-tenant-data-leak-via-empty-organization-filters) | CRITICAL | Before prod |
| C4 | [Open Redirect / SSRF via `success_url`](#c4-open-redirect--ssrf-via-success_url) | CRITICAL | Before prod |
| H1 | [XSRF Token Timing Attack](#h1-xsrf-token-timing-attack) | HIGH | Before prod |
| H2 | [User Enumeration via Login Error Messages](#h2-user-enumeration-via-login-error-messages) | HIGH | Before prod |
| H3 | [Refresh Token Reuse Without Rotation](#h3-refresh-token-reuse-without-rotation) | HIGH | Sprint+1 |
| H4 | [No Validation of JWT Secret Key Strength](#h4-no-validation-of-jwt-secret-key-strength) | HIGH | Before prod |
| H5 | [IDOR on Organization User Queries](#h5-idor-on-organization-user-queries) | HIGH | Before prod |
| H6 | [Default Credentials in Fixture Data](#h6-default-credentials-in-fixture-data) | HIGH | Before prod |
| H7 | [Inconsistent Password Hashing](#h7-inconsistent-password-hashing--done) | HIGH | Sprint+1 |
| H8 | [Service-to-Service Token Without Instance Identity](#h8-service-to-service-token-without-instance-identity) | HIGH | Sprint+1 |
| H9 | [No Audit Logging on Private Data Access](#h9-no-audit-logging-on-private-data-access) | HIGH | Sprint+1 |
| M1 | [Missing HTTP Security Headers](#m1-missing-http-security-headers) | MEDIUM | Before prod |
| M2 | [No Global API Rate Limiting](#m2-no-global-api-rate-limiting) | MEDIUM | Sprint+1 |
| M3 | [Debug Mode Active in DEMO Environment](#m3-debug-mode-active-in-demo-environment) | MEDIUM | Before prod |
| M4 | [Insecure Cookie Defaults](#m4-insecure-cookie-defaults) | MEDIUM | Before prod |
| M5 | [Mass Assignment in EntityService.create()](#m5-mass-assignment-in-entityservicecreate) | MEDIUM | Sprint+2 |
| M6 | [Unbounded Search Parameters](#m6-unbounded-search-parameters) | MEDIUM | Sprint+1 |
| M7 | [Internal Error Details Exposed in Mollie Responses](#m7-internal-error-details-exposed-in-mollie-responses) | MEDIUM | Before prod |
| M8 | [Super User Bypass Without Audit Trail](#m8-super-user-bypass-without-audit-trail) | MEDIUM | Sprint+1 |
| M9 | [No SSL/TLS Enforcement for Database Connections](#m9-no-ssltls-enforcement-for-database-connections) | MEDIUM | Sprint+1 |

---

## ~~C1. Mollie Webhook Without Signature Verification~~ — INVALID

**Status:** Withdrawn — not a real vulnerability.

### Why This Was Wrong

The original audit assumed Mollie signs webhooks with a shared secret (like Stripe does).
This is incorrect. Mollie does **not** provide webhook signature verification.
There is no `X-Mollie-Signature` header and no webhook secret in the Mollie dashboard.

See: https://docs.mollie.com/docs/webhooks

### How Mollie Webhooks Are Already Secured

Mollie's security model is different from Stripe's:

1. The webhook only sends the resource ID (e.g., `id=tr_12345`), never the status or data
2. The handler **re-fetches** the full resource from the Mollie API using the authenticated API key
3. Even if an attacker sends a forged webhook, the handler fetches the real status from Mollie

This "fetch-back" pattern is Mollie's documented security approach. The existing code already
implements it correctly (fetching via `mollie_client.payments.get()`, `customer.subscriptions.get()`,
etc.). Additionally, Redis idempotency prevents replay of already-processed resource IDs.

---

## C2. Missing `aud`/`iss` Claims in JWT Tokens

**Files:**
- `src/lys/apps/user_auth/utils.py:46-77`
- `src/lys/apps/user_auth/modules/auth/services.py:407-434`
- `src/lys/core/utils/auth.py:28-68`

### The Problem

JWT tokens are generated without `aud` (audience) and `iss` (issuer) claims.

- `iss` (issuer) identifies **who signed the token** (e.g., the auth server)
- `aud` (audience) identifies **for which type of consumer the token is intended**

Without these claims, there is no way to distinguish between different types of tokens.
All tokens (user access, service-to-service, refresh) are signed with the same key and
accepted interchangeably. This creates three concrete attack vectors:

**1. Service token used as user token:**
A service-to-service token (which may have elevated privileges) could be sent as a
user access token. The `type` field is checked in `ServiceAuthMiddleware`, but the
user auth middleware does not reject tokens that have `type: "service"`.

**2. Refresh token used as access token:**
If both are signed identically, a refresh token (valid 24h) could bypass the short
access token lifetime (5min).

**3. Cross-application token reuse:**
If two separate Lys deployments share the same `secret_key` by mistake, tokens from
App A are valid on App B.

**Important clarification:** In the Lys microservices architecture, the frontend does not
know which backend service handles the request. A user authenticates once and the same
access token must be accepted by all business microservices (billing, user, inventory, etc.).
The goal is NOT to restrict tokens per microservice, but to separate tokens by **flow type**.

### Current Code

```python
# src/lys/apps/user_auth/modules/auth/services.py - generate_access_token()
claims["exp"] = int(round(time.time())) + (expire_minutes * 60)
claims["xsrf_token"] = xsrf_token.decode("ascii")
# No "aud" or "iss" set

# src/lys/apps/user_auth/utils.py - decode()
return jwt.decode(access_token, self.secret_key, algorithms=[algorithm])
# No audience/issuer validation
```

### Proto Solution

Use `aud` to separate **token types**, not individual microservices:

| Token type | `iss` | `aud` | Accepted by |
|------------|-------|-------|-------------|
| User access token | `"lys-auth"` | `"lys-api"` | All business microservices |
| Service-to-service | service name | `"lys-internal"` | ServiceAuthMiddleware only |
| Refresh token | `"lys-auth"` | `"lys-auth-refresh"` | Refresh endpoint only |

This way, user access tokens work across all microservices (the frontend flow is unchanged),
but a service token cannot be used as a user token, and a refresh token cannot be used as
an access token.

**User auth side** (`src/lys/apps/user_auth/utils.py`):

```python
class AuthUtils:
    ALLOWED_ALGORITHMS = ["HS256", "HS384", "HS512"]

    def __init__(self, config: dict):
        # ... existing init ...
        self.issuer = config.get("jwt_issuer", "lys-auth")
        self.api_audience = "lys-api"
        self.refresh_audience = "lys-auth-refresh"

    def encode(self, claims: dict, audience: str = None, algorithm: str = None) -> str:
        algorithm = algorithm or self.algorithm
        claims["iss"] = self.issuer
        claims["aud"] = audience or self.api_audience
        return jwt.encode(claims, self.secret_key, algorithm=algorithm)

    def decode(self, access_token: str, audience: str = None, algorithm: str = None) -> dict:
        algorithm = algorithm or self.algorithm
        return jwt.decode(
            access_token,
            self.secret_key,
            algorithms=[algorithm],
            audience=audience or self.api_audience,
            issuer=self.issuer,
            options={
                "verify_exp": True,
                "verify_aud": True,
                "verify_iss": True,
            }
        )
```

**Token generation** (`src/lys/apps/user_auth/modules/auth/services.py`):

```python
# Access token: audience = "lys-api" (accepted by all business services)
access_token = auth_utils.encode(claims)  # default audience

# Refresh token: audience = "lys-auth-refresh" (accepted only by refresh endpoint)
refresh_claims = {"sub": user.id, "exp": refresh_exp}
refresh_token = auth_utils.encode(refresh_claims, audience="lys-auth-refresh")
```

**Refresh endpoint** (`src/lys/apps/user_auth/modules/auth/webservices.py`):

```python
# Only accepts refresh tokens, rejects access tokens and service tokens
claims = auth_utils.decode(refresh_token_value, audience="lys-auth-refresh")
```

**Service-to-service side** (`src/lys/core/utils/auth.py`):

```python
class AuthUtils:
    INTERNAL_AUDIENCE = "lys-internal"

    def generate_token(self, expiration_minutes: int = 1) -> str:
        now = int(time.time())
        payload = {
            "type": "service",
            "service_name": self.service_name,
            "iat": now,
            "exp": now + (expiration_minutes * 60),
            "iss": self.service_name,
            "aud": self.INTERNAL_AUDIENCE,
        }
        return jwt.encode(payload, self.secret_key, algorithm=ALGORITHM)

    def decode_token(self, token: str) -> dict:
        payload = jwt.decode(
            token,
            self.secret_key,
            algorithms=[ALGORITHM],
            audience=self.INTERNAL_AUDIENCE,
            options={"verify_exp": True, "verify_aud": True}
        )
        if payload.get("type") != "service":
            raise jwt.InvalidTokenError("Invalid token type")
        return payload
```

**What this prevents:**

| Attack | Without aud/iss | With aud/iss |
|--------|-----------------|--------------|
| Service token used as user token | Accepted | Rejected (`lys-internal` != `lys-api`) |
| Refresh token used as access token | Accepted | Rejected (`lys-auth-refresh` != `lys-api`) |
| Token from another Lys app | Accepted (same key) | Rejected (different `iss`) |
| User token on another business service | Accepted (intended) | Accepted (intended, same `aud`: `lys-api`) |

---

## C3. Cross-Tenant Data Leak via Empty Organization Filters

**Files:**
- `src/lys/core/entities.py:50-59`
- `src/lys/apps/organization/permissions.py:98-130`

### The Problem

The base `Entity` class returns an empty list for `organization_accessing_filters()`:

```python
class Entity(Base):
    @classmethod
    def organization_accessing_filters(cls, organizations, session):
        return []  # No filter = no restriction = ALL data visible
```

When `OrganizationPermission.add_statement_access_constraints()` applies these filters,
an empty list means **no WHERE clause is added** to the query. The result: a user from
Organization A sees data from Organization B, C, D, etc.

This is a **multi-tenant isolation failure**. Any new entity that forgets to override this
method silently exposes all data across all tenants.

### Attack Scenario

1. Developer creates a new `Invoice` entity, forgets to implement `organization_accessing_filters()`
2. User from Organization A queries invoices
3. The query has no organization filter
4. User A sees invoices from all organizations

### Why NOT `raise NotImplementedError` on Entity Base

The first instinct is to make `organization_accessing_filters()` raise `NotImplementedError`
on `Entity`, forcing every entity to implement it. The problem: many entities are legitimately
global (Log, Notification, LoginAttempt, all ParametricEntity subclasses...). They would all
need a boilerplate `return []`. Worse, a developer who just wants to silence the error writes
`return []` without thinking about it, and there is no way to distinguish an intentional
`return []` (global entity) from a lazy one (forgot to add real filters).

### Proto Solution: Overridable `_tenant_columns` + Runtime Safety Check

The approach: add a `_tenant_columns` class attribute on `Entity` that the permission layer
reads at runtime. If an entity has columns matching its tenant columns but returns no filters,
the query is blocked. Each entity can override the attribute to opt in, opt out, or declare
custom tenant columns.

**Step 1: Add `_tenant_columns` and `_user_columns` on Entity**

```python
# src/lys/core/entities.py

class Entity(Base):
    # Tenant columns for the safety check in OrganizationPermission.
    # Override in subclasses to:
    #   - None (default) → auto-detect from OrganizationPermission.DEFAULT_TENANT_COLUMNS
    #   - set()          → opt out ("I have client_id but it's not a tenant scope")
    #   - {"col_name"}   → use custom column(s) as tenant indicator
    _tenant_columns: set[str] | None = None

    # Same pattern for user-level filtering
    _user_columns: set[str] | None = None

    @classmethod
    def organization_accessing_filters(cls, organizations, session):
        return []

    @classmethod
    def user_accessing_filters(cls, connected_user, session):
        return []
```

**Step 2: Runtime safety check in OrganizationPermission**

```python
# src/lys/apps/organization/permissions.py

class OrganizationPermission:
    DEFAULT_TENANT_COLUMNS = {"client_id", "organization_id", "company_id", "establishment_id"}

    @classmethod
    async def add_statement_access_constraints(cls, stmt, entity_type, access_type, session):
        organizations = access_type.get(ORGANIZATION_ROLE_ACCESS_KEY, {})
        filters = entity_type.organization_accessing_filters(organizations, session)

        # Determine which columns to check for this entity
        if entity_type._tenant_columns is not None:
            # Entity explicitly declares its tenant columns (can be empty set to opt out)
            tenant_columns = entity_type._tenant_columns
        else:
            # Auto-detect from global default
            tenant_columns = cls.DEFAULT_TENANT_COLUMNS

        entity_columns = {c.name for c in entity_type.__table__.columns}
        matched = tenant_columns & entity_columns

        if matched and not filters:
            raise SecurityError(
                f"{entity_type.__name__} has tenant columns {matched} but "
                f"organization_accessing_filters() returned no filters. "
                f"Either implement the filters or set _tenant_columns = set() to opt out."
            )

        if filters:
            stmt = stmt.where(or_(*filters))

        return stmt
```

**Step 3: Entity usage examples**

```python
# Case 1: Standard tenant entity (auto-detected via client_id in DEFAULT_TENANT_COLUMNS)
# _tenant_columns = None (default) → auto-detect → finds client_id → filters required
class Invoice(Entity):
    client_id: Mapped[str] = mapped_column(Uuid(as_uuid=False))

    @classmethod
    def organization_accessing_filters(cls, organizations, session):
        return [cls.client_id.in_(organizations.get("client", []))]


# Case 2: Entity with client_id that is NOT a tenant scope (e.g., audit log)
# _tenant_columns = set() → explicit opt out → no check
class AuditLog(Entity):
    client_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), comment="Who triggered it")
    _tenant_columns = set()  # "I have client_id but it's not tenant filtering"


# Case 3: Entity with a custom tenant column not in the global default list
# _tenant_columns = {"partner_org_id"} → check on this column instead
class PartnerData(Entity):
    partner_org_id: Mapped[str] = mapped_column(Uuid(as_uuid=False))
    _tenant_columns = {"partner_org_id"}

    @classmethod
    def organization_accessing_filters(cls, organizations, session):
        return [cls.partner_org_id.in_(organizations.get("partner", []))]


# Case 4: Global entity (no tenant column at all) → nothing to check, no override needed
class Notification(Entity):
    message: Mapped[str] = mapped_column()
    # No client_id, no _tenant_columns override → auto-detect finds nothing → OK
```

**Decision matrix:**

| Entity has tenant column? | `_tenant_columns` value | Returns filters? | Result |
|---------------------------|-------------------------|------------------|--------|
| No (Notification, Log...) | `None` (default)        | No (`[]`)        | OK, global entity |
| Yes (`client_id`)         | `None` (default)        | Yes              | OK, filters applied |
| Yes (`client_id`)         | `None` (default)        | No (`[]`)        | **SecurityError** (forgot to implement) |
| Yes (`client_id`)         | `set()` (opt out)       | No (`[]`)        | OK, explicit opt out |
| Yes (custom column)       | `{"custom_col"}`        | Yes              | OK, custom filters applied |

The key property: `_tenant_columns = set()` is an **explicit opt out**. In code review,
when you see this, you know the developer made a conscious decision. A forgotten implementation
is caught automatically by the runtime check. The global `DEFAULT_TENANT_COLUMNS` set can be
extended in subclasses of `OrganizationPermission` if new tenant column names are introduced.

---

## C4. Open Redirect / SSRF via `success_url`

**Files:**
- `src/lys/apps/licensing/modules/mollie/webservices.py:227-241`
- `src/lys/apps/licensing/modules/mollie/inputs.py:23`

### The Problem

When a user subscribes to a plan, they provide a `success_url` that Mollie will redirect to
after payment. This URL is passed directly to Mollie without any validation.

**Open Redirect:** An attacker creates a payment with `success_url=https://evil.com/phishing`.
After payment, the user is redirected to the attacker's site. Since the redirect comes from
Mollie (trusted), the user trusts the destination.

**SSRF:** If the `success_url` is used server-side for any callback or verification,
the server can be tricked into making requests to internal services
(`http://169.254.169.254/metadata`, `http://localhost:8080/admin`).

### Proto Solution

```python
# src/lys/core/utils/validators.py

from urllib.parse import urlparse
import ipaddress


class UrlValidationError(ValueError):
    pass


def validate_redirect_url(url: str, allowed_domains: list[str] = None) -> str:
    """
    Validate that a URL is safe to use as a redirect target.

    Rules:
    - Must be a valid URL with https scheme
    - Must not point to a private/internal IP address
    - If allowed_domains is provided, hostname must match one of them
    """
    try:
        parsed = urlparse(url)
    except Exception:
        raise UrlValidationError("Invalid URL format")

    # Scheme must be https
    if parsed.scheme != "https":
        raise UrlValidationError("URL must use HTTPS")

    # Must have a hostname
    if not parsed.hostname:
        raise UrlValidationError("URL must have a hostname")

    # Block private IP ranges
    try:
        ip = ipaddress.ip_address(parsed.hostname)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise UrlValidationError("URL must not point to a private IP address")
    except ValueError:
        pass  # Not an IP address, hostname is fine

    # Block suspicious hostnames
    blocked_hostnames = {"localhost", "127.0.0.1", "0.0.0.0", "metadata.google.internal"}
    if parsed.hostname.lower() in blocked_hostnames:
        raise UrlValidationError("URL hostname is not allowed")

    # Domain whitelist (if configured)
    if allowed_domains:
        if not any(
            parsed.hostname == domain or parsed.hostname.endswith(f".{domain}")
            for domain in allowed_domains
        ):
            raise UrlValidationError(
                f"URL hostname must match one of: {', '.join(allowed_domains)}"
            )

    return url
```

Usage in the webservice:

```python
# src/lys/apps/licensing/modules/mollie/webservices.py

from lys.core.utils.validators import validate_redirect_url

@strawberry.mutation
async def subscribe_to_plan(self, info, input: SubscribeToPlanInput) -> SubscriptionResult:
    # Validate success_url before passing to Mollie
    allowed_domains = app_manager.settings.plugins.get("payment", {}).get(
        "allowed_redirect_domains", []
    )
    validate_redirect_url(input.success_url, allowed_domains or None)

    # ... proceed with subscription ...
```

The `allowed_redirect_domains` configuration lets each deployment define which domains are
acceptable (e.g., `["myapp.com", "staging.myapp.com"]`).

---

## H1. XSRF Token Timing Attack

**File:** `src/lys/apps/user_auth/middlewares.py:87`

### The Problem

The XSRF token comparison uses Python's `!=` operator:

```python
if xsrf_token != expected_xsrf:
    raise LysError(...)
```

Python's `!=` on strings compares character by character and returns `False` as soon as it
finds a mismatch. This means the comparison takes longer when more characters match.

An attacker can exploit this by measuring response time:
- Send XSRF token starting with `a...` -> fast rejection (first char wrong)
- Send XSRF token starting with `7...` -> slightly slower (first char right, second wrong)
- Continue character by character until the full token is reconstructed

This is a **timing side-channel attack**. It's harder to exploit over the network (noise),
but still a recognized vulnerability (CWE-208).

### Proto Solution

One-line fix using `hmac.compare_digest()` which runs in constant time:

```python
# src/lys/apps/user_auth/middlewares.py

import hmac

# Replace line 87:
# BEFORE:
if xsrf_token != expected_xsrf:
# AFTER:
if not hmac.compare_digest(xsrf_token, expected_xsrf):
```

`hmac.compare_digest()` always compares all bytes regardless of where the first mismatch is,
making the execution time constant and preventing timing analysis.

---

## H2. User Enumeration via Login Error Messages

**File:** `src/lys/apps/user_auth/modules/auth/services.py:142-224`

### The Problem

The login flow produces different responses depending on the user's state:

| State | Error Message | Timing |
|-------|--------------|--------|
| User does not exist | "unknown user with login..." | Fast (no bcrypt) |
| User is disabled | "user has been blocked" | Fast (no bcrypt) |
| Rate limited | "Too many failed attempts" + timer | Fast (no bcrypt) |
| Wrong password | "unknown user with login..." | Slow (bcrypt comparison) |
| Correct password | Success | Slow (bcrypt comparison) |

Even though some error messages are identical, the **timing difference** reveals whether the
user exists: bcrypt takes ~100-300ms, while a "user not found" response is nearly instant.

An attacker can enumerate valid accounts by measuring response time.

### Proto Solution

The key principle: **make all login attempts take the same amount of time**, regardless of
whether the user exists.

```python
# src/lys/apps/user_auth/modules/auth/services.py

import bcrypt

# Pre-computed bcrypt hash of a dummy password, used when user doesn't exist.
# This ensures bcrypt runs even for non-existent users, equalizing response time.
_DUMMY_HASH = bcrypt.hashpw(b"dummy-password-for-timing", bcrypt.gensalt()).decode("utf-8")

GENERIC_LOGIN_ERROR = "Invalid credentials"


@classmethod
async def authenticate_user(cls, login: str, password: str, session: AsyncSession):
    user = await cls.get_user_from_login(login, session)

    if user is None:
        # Run bcrypt anyway to equalize timing
        bcrypt.checkpw(password.encode("utf-8"), _DUMMY_HASH.encode("utf-8"))
        raise LysError(
            UNKNOWN_USER_ERROR,
            GENERIC_LOGIN_ERROR  # Same message regardless of reason
        )

    # Check rate limiting BEFORE revealing user status
    if cls.auth_utils.config.get("login_rate_limit_enabled", True):
        await cls._check_rate_limit(user, session)

    # Check password (bcrypt runs here for real users)
    if not cls.user_service.check_password(user, password):
        await cls._record_failed_attempt(user, session)
        raise LysError(
            UNKNOWN_USER_ERROR,
            GENERIC_LOGIN_ERROR  # Same message as user-not-found
        )

    # Check user status AFTER password validation
    if user.status_id != ENABLED_USER_STATUS:
        raise LysError(
            BLOCKED_USER_ERROR,
            GENERIC_LOGIN_ERROR  # Same message again
        )

    # Success
    await cls._record_successful_login(user, session)
    return user
```

The key changes:
1. **Dummy bcrypt** when user not found (equalizes timing)
2. **Generic error message** for all failure cases
3. **Rate limiting checked before status** (prevents enumeration of disabled users)

---

## H3. Refresh Token Reuse Without Rotation

**File:** `src/lys/apps/user_auth/modules/auth/webservices.py:73-84`

### The Problem

```python
refresh_token_used_once = auth_utils.config.get("refresh_token_used_once", False)
```

By default, the same refresh token can be reused indefinitely during its 24h lifetime.
If a refresh token is stolen (via XSS, network interception, log exposure), the attacker
can generate unlimited access tokens for 24 hours. The legitimate user has no way to know
their token was compromised.

With rotation enabled, each use of a refresh token generates a new one and invalidates the
old one. If the attacker uses the stolen token, the legitimate user's next refresh fails,
alerting them. If the legitimate user refreshes first, the attacker's token is invalid.

### Proto Solution

Change the default to `True`:

```python
# src/lys/apps/user_auth/modules/auth/webservices.py

refresh_token_used_once = auth_utils.config.get("refresh_token_used_once", True)  # Changed default
```

Additionally, implement **reuse detection** to revoke all tokens when a used refresh token
is reused (sign of theft):

```python
# src/lys/apps/user_auth/modules/refresh_token/services.py

@classmethod
async def refresh(cls, refresh_token_id: str, session: AsyncSession):
    token = await session.get(cls.entity_class, refresh_token_id)

    if token is None:
        # Token doesn't exist. Could have been rotated and then reused.
        # This is a potential token theft indicator.
        logger.warning(
            f"SECURITY: Refresh token {refresh_token_id} reused after rotation. "
            f"Possible token theft. Revoking all tokens for this user."
        )
        # Revoke all refresh tokens for the user associated with this token
        # (requires storing user_id in a revoked tokens log)
        await cls._revoke_all_user_tokens(refresh_token_id, session)
        raise LysError(INVALID_TOKEN_ERROR, "Token has been revoked")

    # Rotate: create new token, delete old one
    new_token = await cls.create(session, user_id=token.user_id)
    await cls.delete(session, token.id)
    return new_token
```

---

## H4. No Validation of JWT Secret Key Strength

**Files:**
- `src/lys/core/configs.py:231`
- `src/lys/apps/user_auth/utils.py:30-33`

### The Problem

The secret key is optional in settings and has no length/entropy validation:

```python
# configs.py
self.secret_key: Optional[str] = None  # Can start the app without a key

# utils.py
if not self.secret_key:
    raise ValueError("JWT secret_key is required")
# No length check - "abc" would be accepted
```

For HS256, the secret must be at least 256 bits (32 bytes) to be secure. A short key can
be brute-forced, allowing token forgery.

### Proto Solution

```python
# src/lys/core/configs.py

MIN_SECRET_KEY_LENGTH = 32  # 256 bits minimum for HS256


class AppSettings:
    def __init__(self):
        # ... existing code ...
        self.secret_key: Optional[str] = None

    def validate(self):
        """Call this at startup to ensure configuration is valid."""
        # ... existing validations ...

        if self.secret_key is None:
            raise ValueError(
                "CRITICAL: secret_key is not configured. "
                "Set it via environment variable or settings. "
                "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )

        if len(self.secret_key.encode("utf-8")) < MIN_SECRET_KEY_LENGTH:
            raise ValueError(
                f"CRITICAL: secret_key must be at least {MIN_SECRET_KEY_LENGTH} bytes "
                f"(current: {len(self.secret_key.encode('utf-8'))} bytes). "
                f"Generate a secure key with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
```

Call `settings.validate()` early in `AppManager` initialization:

```python
# src/lys/core/managers/app.py - in setup() or __init__()

self.settings.validate()
```

---

## H5. IDOR on Organization User Queries

**File:** `src/lys/apps/organization/modules/user/webservices.py:116-150`

### The Problem

The `all_client_users(client_id=...)` query accepts any `client_id` from the caller. The
organization filtering happens at the query level via `organization_accessing_filters()`,
but if those filters are misconfigured (see C3), an attacker can query users from any
organization.

Even with correct filters, the defense is implicit (row-level filtering). An explicit
check is more robust and easier to audit.

### Proto Solution

Add an explicit check before executing the query:

```python
# src/lys/apps/organization/modules/user/webservices.py

@strawberry.field
async def all_client_users(
    self,
    info: Info,
    client_id: GlobalID,
    # ...
) -> list[UserType]:
    connected_user = info.context.connected_user

    # Explicit organization access check
    user_organizations = connected_user.get("organizations", {})
    accessible_client_ids = set()
    for org_level, orgs in user_organizations.items():
        for org_id in orgs:
            accessible_client_ids.add(org_id)

    if client_id.node_id not in accessible_client_ids:
        raise LysError(
            PERMISSION_DENIED_ERROR,
            f"You do not have access to this organization"
        )

    # Proceed with existing query logic...
```

This is a **defense-in-depth** approach: even if row-level filtering fails, the explicit
check blocks unauthorized access.

---

## H6. Default Credentials in Fixture Data

**File:** `src/lys/apps/user_auth/modules/user/fixtures.py:137-179`

### The Problem

Three test users are created with the password `"password"`:
- `enabled_user@lys-test.fr`
- `disabled_user@lys-test.fr`
- `super_user@lys-test.fr`

These are gated by `_allowed_envs = [EnvironmentEnum.DEV]`, but:
- A misconfigured `env` variable could load them in production
- There is no secondary safety check
- The `super_user` account with password `"password"` is particularly dangerous

### Proto Solution

Add a runtime guard and use random passwords:

```python
# src/lys/apps/user_auth/modules/user/fixtures.py

import secrets


class UserDevFixtures(EntityFixtures):
    _allowed_envs = [EnvironmentEnum.DEV]

    @classmethod
    def _generate_dev_password(cls) -> str:
        """Generate a random password for dev fixtures. Printed to console for developer use."""
        password = secrets.token_urlsafe(16)
        return password

    async def load(self, session):
        # Double-check environment as safety net
        if self.app_manager.settings.env not in self._allowed_envs:
            logger.error(
                "SECURITY: Attempted to load dev fixtures outside DEV environment. Aborting."
            )
            return

        dev_password = self._generate_dev_password()
        logger.info(f"Dev fixtures loaded with password: {dev_password}")

        users = [
            {
                "email": "enabled_user@lys-test.fr",
                "password": dev_password,
                "status_id": ENABLED_USER_STATUS,
            },
            # ... other users with same dev_password ...
        ]
        # ... create users ...
```

This way, even if fixtures load accidentally, the password is random and unknown.

---

## H7. Inconsistent Password Hashing — DONE

**File:** `src/lys/apps/user_auth/modules/user/services.py`

### The Problem

Password hashing was done two different ways:
- **User creation:** Uses `AuthUtils.hash_password(password)` (centralized)
- **Password update:** Uses `bcrypt.gensalt()` + `bcrypt.hashpw()` directly (inline)

If `AuthUtils.hash_password()` is later updated (e.g., to increase bcrypt rounds, add
pepper, or switch to argon2), the inline code in `update_password()` would not benefit
from the change. Similarly, password verification used inline `bcrypt.checkpw()` instead
of the existing `cls.check_password()` method.

### Fix Applied

Replaced both inline bcrypt calls in `update_password()` with the centralized utilities:

- `bcrypt.checkpw()` replaced with `cls.check_password(user, current_password)`
- `bcrypt.gensalt()` + `bcrypt.hashpw()` replaced with `AuthUtils.hash_password(new_password)`

All password hashing and verification now goes through a single code path, ensuring
consistency if the algorithm or parameters are changed in the future.

---

## H8. Service-to-Service Token Without Instance Identity

**File:** `src/lys/core/utils/auth.py:40-47`

### The Problem

Service tokens contain `service_name` and `type` but no instance identifier. If the
"billing-service" runs on 3 instances and one is compromised, the attacker's tokens are
indistinguishable from legitimate ones.

### Proto Solution

Add an instance identifier:

```python
# src/lys/core/utils/auth.py

class AuthUtils:
    def __init__(self, secret_key: str, service_name: str = None, instance_id: str = None):
        self.secret_key = secret_key
        self.service_name = service_name or "unknown"
        self.instance_id = instance_id or str(uuid4())[:8]

    def generate_token(self, expiration_minutes: int = 1) -> str:
        now = int(time.time())
        payload = {
            "type": "service",
            "service_name": self.service_name,
            "instance_id": self.instance_id,  # Added
            "iat": now,
            "exp": now + (expiration_minutes * 60),
        }
        return jwt.encode(payload, self.secret_key, algorithm=ALGORITHM)
```

This enables tracing which specific instance made each call, useful for incident response.

---

## H9. No Audit Logging on Private Data Access

**File:** `src/lys/apps/user_auth/modules/user/entities.py:160-175`

### The Problem

When `user_accessing_filters()` is applied and a user tries to access another user's private
data, the query simply returns no results. There is no log of the attempt. An attacker can
iterate through user IDs without detection.

### Proto Solution

Add logging in the permission layer:

```python
# src/lys/core/permissions.py (or in the access constraint method)

@classmethod
async def add_statement_access_constraints(cls, stmt, entity_type, access_type, session):
    # ... existing filter logic ...

    # Log access attempts on sensitive entities
    sensitive_entities = {"UserPrivateData", "User"}  # Configurable
    if entity_type.__name__ in sensitive_entities:
        logger.info(
            f"Access to {entity_type.__name__} by user={connected_user_id} "
            f"with access_type={access_type}"
        )

    return stmt
```

---

## M1. Missing HTTP Security Headers

**Location:** No security headers middleware exists

### The Problem

The application does not set standard HTTP security headers. This leaves users vulnerable to:
- **Clickjacking** (no `X-Frame-Options`)
- **MIME sniffing** (no `X-Content-Type-Options`)
- **Protocol downgrade** (no `Strict-Transport-Security`)

### Proto Solution

```python
# src/lys/core/middlewares.py

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Adds standard security headers to all HTTP responses.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"

        # HSTS only on HTTPS
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )

        return response
```

Register it in the middleware list in settings:

```python
settings.middlewares = [
    "lys.core.middlewares.SecurityHeadersMiddleware",
    # ... other middlewares ...
]
```

---

## M2. No Global API Rate Limiting

### The Problem

Login has rate limiting, but the rest of the API does not. An attacker can:
- Hammer GraphQL queries to cause DoS
- Brute-force resource IDs (UUIDs are long but still enumerable)
- Scrape data at high speed

### Proto Solution

Use `slowapi` for REST endpoints and a custom middleware for GraphQL:

```python
# src/lys/core/middlewares.py

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Simple IP-based rate limiter using in-memory storage.
    For production, replace with Redis-backed storage.
    """

    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self._requests: dict[str, list[float]] = {}  # IP -> [timestamps]

    async def dispatch(self, request: Request, call_next) -> Response:
        client_ip = request.client.host
        now = time.time()
        window_start = now - 60

        # Clean old entries and count recent requests
        timestamps = self._requests.get(client_ip, [])
        timestamps = [t for t in timestamps if t > window_start]

        if len(timestamps) >= self.requests_per_minute:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests"},
                headers={"Retry-After": "60"}
            )

        timestamps.append(now)
        self._requests[client_ip] = timestamps

        return await call_next(request)
```

For production, this should use Redis as backend to work across multiple instances.

---

## M3. Debug Mode Active in DEMO Environment

**File:** `src/lys/core/configs.py:248-265`

### The Problem

```python
@property
def debug(self) -> bool:
    return self.env in (EnvironmentEnum.DEV, EnvironmentEnum.DEMO)
```

DEMO environment gets `debug=True`, which enables stack traces in error responses, verbose
DEBUG logging (which may contain sensitive data like JWT claims), and GraphQL IDE.

### Proto Solution

```python
# src/lys/core/configs.py

@property
def debug(self) -> bool:
    return self.env == EnvironmentEnum.DEV  # Only DEV, not DEMO
```

---

## M4. Insecure Cookie Defaults

**File:** `src/lys/apps/user_auth/modules/auth/services.py:479-489`

### The Problem

Cookie security flags are loaded from configuration with no defaults:

```python
secure=cls.auth_utils.config.get("cookie_secure"),      # None if not set
httponly=cls.auth_utils.config.get("cookie_http_only"),   # None if not set
samesite=cls.auth_utils.config.get("cookie_same_site"),   # None if not set
```

If the auth plugin is not fully configured, cookies are sent without security flags:
- Without `secure`: cookies sent over HTTP (interceptable)
- Without `httponly`: JavaScript can read cookies (XSS → token theft)
- Without `samesite`: cookies sent with cross-origin requests (CSRF)

### Proto Solution

Set secure defaults:

```python
# src/lys/apps/user_auth/modules/auth/services.py

@classmethod
async def set_cookie(cls, response, key, value, path):
    response.set_cookie(
        key=key,
        value=value,
        path=path,
        secure=cls.auth_utils.config.get("cookie_secure", True),         # Default: secure
        httponly=cls.auth_utils.config.get("cookie_http_only", True),     # Default: httponly
        samesite=cls.auth_utils.config.get("cookie_same_site", "Lax"),   # Default: Lax
        domain=cls.auth_utils.config.get("cookie_domain"),
        expires=datetime.now(UTC) + timedelta(weeks=1),
    )
```

`Lax` is used instead of `Strict` for `samesite` because `Strict` can break legitimate
navigation flows (e.g., clicking a link from an email). `Lax` prevents CSRF on POST while
still allowing GET navigation.

---

## M5. Mass Assignment in EntityService.create()

**File:** `src/lys/core/services.py:133-138`

### The Problem

```python
@classmethod
async def create(cls, session: AsyncSession, **kwargs) -> T:
    entity = cls.entity_class(**kwargs)
    session.add(entity)
    await session.flush()
    return entity
```

Any keyword argument is passed directly to the entity constructor. If a caller passes
`is_super_user=True` or `status_id="ENABLED"`, the entity is created with those values.

The webservice layer uses Pydantic models that filter input fields, so this is not directly
exploitable from the API. But it's a risk if `create()` is called from internal code with
unsanitized data.

### Proto Solution

This is lower priority because the Pydantic layer provides protection. To add defense-in-depth,
consider a field whitelist pattern:

```python
# src/lys/core/services.py

class EntityService(Generic[T]):
    # Override in subclasses to restrict which fields can be set via create()
    _create_allowed_fields: set[str] | None = None  # None = all fields allowed (current behavior)

    @classmethod
    async def create(cls, session: AsyncSession, **kwargs) -> T:
        if cls._create_allowed_fields is not None:
            unexpected = set(kwargs.keys()) - cls._create_allowed_fields
            if unexpected:
                logger.warning(
                    f"Unexpected fields in {cls.__name__}.create(): {unexpected}. Ignoring."
                )
                kwargs = {k: v for k, v in kwargs.items() if k in cls._create_allowed_fields}

        entity = cls.entity_class(**kwargs)
        session.add(entity)
        await session.flush()
        return entity
```

---

## M6. Unbounded Search Parameters

**Files:**
- `src/lys/apps/user_auth/modules/user/webservices.py:154-163`
- `src/lys/apps/organization/modules/user/webservices.py:81-89`

### The Problem

Search parameters are used in `ILIKE` queries without length validation. A very long search
string with wildcards generates an expensive database query that can cause DoS.

### Proto Solution

```python
# src/lys/core/utils/validators.py

MAX_SEARCH_LENGTH = 200


def validate_search_input(search: str | None) -> str | None:
    """Validate and sanitize search input before use in database queries."""
    if search is None:
        return None

    if len(search) > MAX_SEARCH_LENGTH:
        raise LysError(
            (400, "SEARCH_TOO_LONG"),
            f"Search term must be {MAX_SEARCH_LENGTH} characters or less"
        )

    # Strip SQL wildcards that could be injected to cause expensive LIKE queries
    # (SQLAlchemy parameterizes, but performance matters)
    search = search.replace("%", "").replace("_", "")

    return search
```

Usage:

```python
if search:
    search = validate_search_input(search)
    search_pattern = f"%{search.lower()}%"
    stmt = stmt.where(
        or_(
            email_entity.id.ilike(search_pattern),
            private_data_entity.first_name.ilike(search_pattern),
        )
    )
```

---

## M7. Internal Error Details Exposed in Mollie Responses

**File:** `src/lys/apps/licensing/modules/mollie/webservices.py:152-156`

### The Problem

```python
except Exception as e:
    raise HTTPException(status_code=500, detail=str(e))
```

The full exception message is returned to the caller. This can reveal internal paths,
database errors, API keys, or other sensitive information.

### Proto Solution

```python
except MollieError as e:
    logger.error(f"Mollie error for resource {resource_id}: {e}")
    raise HTTPException(status_code=502, detail="Payment provider error")

except Exception as e:
    logger.exception(f"Unexpected error processing webhook {resource_id}: {e}")
    raise HTTPException(status_code=500, detail="Internal processing error")
```

---

## M8. Super User Bypass Without Audit Trail

**File:** `src/lys/apps/user_auth/permissions.py:116`

### The Problem

```python
if connected_user.get("is_super_user", False):
    return True, None  # Full access, no log
```

Super user actions are invisible. No audit log records what resources they accessed or
modified. This is a compliance risk (SOC 2, ISO 27001) and makes incident investigation
impossible.

### Proto Solution

```python
# src/lys/apps/user_auth/permissions.py

if connected_user.get("is_super_user", False):
    logger.info(
        f"AUDIT: Super user {connected_user.get('sub')} accessed "
        f"webservice={webservice_name}"
    )
    return True, None
```

For a more complete solution, implement a dedicated audit service that stores super user
actions in the database with timestamp, user ID, action, resource, and IP address.

---

## M9. No SSL/TLS Enforcement for Database Connections

**File:** `src/lys/core/managers/database.py`

### The Problem

Database connections are established without SSL by default. In a cloud environment,
traffic between the application and database may traverse untrusted networks.

### Proto Solution

Add SSL configuration support:

```python
# src/lys/core/managers/database.py

def _get_engine_kwargs(self, async_mode: bool = True) -> dict:
    kwargs = {
        # ... existing kwargs ...
    }

    # SSL configuration for production
    connect_args = self.settings.connect_args or {}
    if self.settings.type == "postgresql" and not connect_args.get("ssl"):
        if self.app_manager.settings.env in (EnvironmentEnum.PREPROD, EnvironmentEnum.PROD):
            connect_args["ssl"] = "require"

    if connect_args:
        kwargs["connect_args"] = connect_args

    return kwargs
```

---

## Checklist

| ID | Finding | Status |
|----|---------|--------|
| ~~C1~~ | ~~Mollie webhook signature verification~~ | INVALID |
| C2 | Add `aud`/`iss` to JWT tokens | [x] |
| C3 | Multi-tenant filter safety (introspection + runtime check) | [x] |
| C4 | Validate `success_url` | [x] |
| H1 | `hmac.compare_digest` for XSRF + enabled by default + skip safe methods | [x] |
| H2 | Generic login errors + dummy bcrypt | [x] |
| H3 | Refresh token rotation by default | [x] |
| H4 | Secret key validation at startup | [x] |
| ~~H5~~ | ~~Explicit organization check on user queries~~ | SKIPPED (covered by C3) |
| H6 | Random passwords in fixtures + env guard | [x] |
| H7 | Centralize password hashing | [x] |
| H8 | Instance identity in service tokens | [ ] |
| H9 | Audit logging on private data access | [ ] |
| M1 | Security headers middleware | [ ] |
| M2 | Global API rate limiting | [ ] |
| M3 | Debug mode only in DEV | [ ] |
| M4 | Secure cookie defaults | [ ] |
| M5 | Mass assignment protection | [ ] |
| M6 | Bounded search parameters | [ ] |
| M7 | Generic error messages in Mollie endpoint | [x] |
| M8 | Super user audit trail | [ ] |
| M9 | Database SSL/TLS | [ ] |