# Changelog

All notable changes to this project will be documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.6.0] - 2026-02-24

### Added
- Auto-creation of initial super user at startup via `_ensure_super_user()` in AppManager
- `super_user_email` and `super_user_language` settings in AppSettings for configurable super user provisioning
- Password is randomly generated with `secrets.token_urlsafe`; user must reset via forgot-password flow
- Production-grade code standards section in CLAUDE.md

### Changed
- Removed hardcoded super user from `UserDevFixtures` dev fixture
- Super user creation is now idempotent: skips if user already exists, never updates or deletes

## [0.5.0] - 2026-02-23

### Added
- AI streaming support via `chat_with_tools_streaming` with SSE (Server-Sent Events)
- `AIStreamChunk` dataclass for structured streaming responses from providers
- `MistralProvider.chat_stream()` for async streaming via httpx
- `GraphQLToolExecutor.register_special_tool()` for extensible special tool dispatch
- Guard clauses in `chat_with_tools_streaming` for JWT claim validation
- Unit tests for streaming helpers, providers, special tools, and conversation services

### Changed
- Extracted `_prepare_chat_context()` to eliminate setup duplication between streaming and non-streaming paths
- Refactored `GraphQLToolExecutor` special tools from if/elif chain to dictionary dispatch
- Refactored `MistralProvider._handle_error_status()` out of `_parse_response()`
- Sanitized error messages in `chat_with_tools` and `chat_with_tools_streaming` to prevent internal details leaking to clients
- Downgraded debug-level tool/stream logs from INFO to DEBUG
- Replaced hardcoded `provider="mistral"` with dynamic provider tracking from stream chunks
- Updated coverage badge from 79% to 80%

## [0.4.1] - 2026-02-22

### Changed
- Refactored `lys_delete` to use `create_strawberry_field_config` directly instead of `lys_typed_field`
- Materialized `stream`/`stream_scalars` results in `ThreadSafeSessionProxy` to prevent asyncpg concurrent operation errors
- Exposed `create_strawberry_field_config` as public API in `fields.py`
- Added coverage calculation step (unit + integration + e2e) with README badge update to commit workflow in CLAUDE.md
- `refactor:` commits now trigger a patch version bump

## [0.4.0] - 2026-02-13

### Added
- Alembic migration helper (`lys.core.migrations`) with `configure_alembic_env()` for standardized migration setup
- Alembic CLI wrappers: `run_migrate`, `run_makemigrations`, `run_db_status`, `run_db_stamp` with auto-discovery of `alembic.ini`
- Secure ZIP extraction utility (`lys.core.utils.zip`) with ZIP Slip, ZIP bomb, and per-file size protections
- Configurable `relay_max_results` on `AppSettings` (default 100), passed to `StrawberryConfig`
- `alembic>=1.15.0` dependency
- Unit tests for migrations, Alembic CLI wrappers, ZIP utilities, and relay_max_results
- `create_all_tables()` test helper in `tests/fixtures/database.py`

### Changed
- Removed `initialize_database()` from `DatabaseManager` (Alembic now handles schema migrations)
- Removed database initialization phase from `_app_lifespan`
- XSRF mismatch log no longer exposes token values
- Test fixtures use `create_all_tables()` helper instead of `initialize_database()`
- Updated coverage badge from 77% to 79%
- Updated README testing section with E2E tests and combined coverage commands

## [0.3.0] - 2026-02-12

### Added
- SSO authentication app (`sso`) with Google/Microsoft provider support
- `UserSSOLink` entity linking users to external SSO providers
- `SSOAuthService` with OAuth2 flow, session management via Redis key-value store
- SSO callback REST endpoints (link mode + signup mode)
- `create_client_with_sso_owner` in organization and licensing `ClientService`
- `CreateClientWithSSOInput` / `CreateClientWithSSOInputModel` for SSO signup
- `create_client_with_sso` GraphQL mutation (public, unlicenced)
- PubSubManager key-value operations: `set_key`, `get_key`, `delete_key`, `get_and_delete_key`
- `authlib` and `httpx` dependencies for OAuth2 flows
- Licensing `notification` module registered in `__submodules__`
- Unit tests for SSO endpoints, auth service, models, nodes, and pub/sub KV operations
- Integration tests for SSO link service
- Additional unit tests improving combined coverage to 77%

### Changed
- Email dispatch decoupled from batch creation: `_create_and_send_emails` renamed to `_create_emails`, sending delegated to `send_pending_email` Celery task
- `trigger_event` dispatches `send_pending_email.delay()` per email after session commit
- `send_pending_email` upgraded to `bind=True` with retry logic (`max_retries=3`)
- `UserService.create_user` accepts `password=None` for SSO-only users
- `AuthService.login` handles SSO-only users (no password) with constant-time rejection
- Notification dispatch failures in `trigger_event` now log and continue instead of retrying

## [0.2.0] - 2026-02-11

### Added
- Role-based and organization-scoped email dispatch via `EmailingBatchService` override chain
- `RecipientResolutionMixin` (base), `RoleRecipientResolutionMixin` (user_role), `OrganizationRecipientResolutionMixin` (organization)
- `emailing_type_role` association table linking `EmailingType` to `Role` (many-to-many)
- Extended `EmailingType` entity with `roles` relationship in user_role app
- `EmailingTypeFixtures` base class with `format_roles` for role-aware fixture loading
- `EmailingTypeFixturesModel` Pydantic model for fixture validation with optional `roles`
- Organization-scoped `EmailingBatchService` with `organization_data` parameter
- Per-recipient `private_data` enrichment in `_create_and_send_emails` / `_create_and_send_emails_sync`
- `trigger_event` Celery task: unified event handler for emails and notifications
- Jinja2 base template (`_base.html`) with blocks for consistent email layout
- Licensing emailing fixtures with `context_description` and role assignments
- 5 licensing email templates (EN/FR): license_granted, license_revoked, subscription_payment_success/failed, subscription_canceled
- Minimum 75% combined coverage threshold rule in CLAUDE.md
- Integration tests for role-based and organization-scoped batch dispatch
- Unit tests for all mixins, batch service, emailing entities, templates, fixtures, email context, and trigger_event task (220+ new tests)

### Changed
- Refactored all 16 email templates to extend `_base.html` with block inheritance
- `email_context` in licensing services now includes all template variables (front_url, client_name, plan_name, etc.)
- Registered `emailing` module in `user_role` and `organization` app `__submodules__`
- Updated coverage badge in README.md from 75% to 77%

### Fixed
- `RoleRecipientResolutionMixin` fallback to `Base.metadata.tables` when `user_role` is a raw Table (not a registered entity)
- `EmailingTypeFixturesModel.roles` now optional (default `[]`) to support emailing types without role dispatch
- Missing `await` on `session.execute()` for association table inserts in async context

## [0.1.0] - 2026-02-10

Initial release of the Lys framework.

### Added

**Core Framework**
- Component-based architecture with automatic registration (`@register_entity`, `@register_service`, `@register_fixture`, `@register_node`, `@register_query`, `@register_mutation`)
- `Entity` base class with auto-generated UUID primary keys and audit timestamps
- `ParametricEntity` base class for reference data with string IDs
- `EntityService` with built-in CRUD operations, field validation, and mass-assignment protection
- `EntityFixtures` with parametric (disable strategy) and business (delete strategy) fixture loading
- Component loading order: entities → services → fixtures → nodes → webservices
- Registry locking after each component phase for deterministic behavior
- Last-registered-wins override pattern for app composition
- `override_webservice()` and `disable_webservice()` for metadata modification
- `configure_component_types()` for selective loading (API server vs Celery worker)
- Parallel query execution via `EntityService.execute_parallel()`

**GraphQL API**
- Strawberry GraphQL integration with Relay support (Global IDs, cursor pagination)
- Five operation decorators: `@lys_getter`, `@lys_connection`, `@lys_creation`, `@lys_edition`, `@lys_delete`
- `@parametric_node` for auto-generated ParametricEntity nodes
- `EntityNode` and `ServiceNode` base classes with lazy relationship loading
- Pydantic input validation via Strawberry integration
- Order-by support with `order_by_attribute_map`
- Multiple schema support with automatic routing
- GraphQL federation schema support
- Schema export functionality
- Query depth limiting, alias limiting, schema introspection disabled in production

**Authentication (`user_auth` app)**
- JWT-based authentication with access and refresh tokens
- Cookie-based token transmission (HttpOnly, Secure, SameSite)
- XSRF token validation (enabled by default)
- Refresh token rotation (enabled by default)
- Progressive rate limiting on login attempts
- Login attempt tracking and audit trail
- User status management (enable/disable)
- Password reset with one-time tokens
- Email verification system
- JWT secret key strength validation at startup
- Constant-time password comparison and user enumeration prevention

**Role-Based Access Control (`user_role` app)**
- Role entity with webservice assignments
- Role-based permission checking via JWT claims
- `ROLE_ACCESS_LEVEL` for webservice access control

**Organization & Multi-Tenancy (`organization` app)**
- Client (tenant) entity with owner access
- `ClientUser` and `ClientUserRole` for organization membership
- `OrganizationPermission` with JWT-based organization-scoped access
- Row-level filtering by `client_id` for multi-tenant data isolation
- Tenant column safety check preventing accidental data leaks
- `ORGANIZATION_ROLE_ACCESS_LEVEL` for organization-scoped webservices

**Licensing (`licensing` app)**
- License plans and versioned plan rules
- Subscription management with user quotas
- License verification integrated into JWT claims
- Mollie payment integration
- `LicensingAuthService` filtering webservices by license status

**File Management (`file_management` app)**
- S3 storage integration with presigned URLs
- File import system with status tracking
- Thread-safe GraphQL sessions for file operations

**AI Integration (`ai` app)**
- AI conversation and message management
- GraphQL tool generation from webservices
- AI guardrails with confirmation workflow for risky operations
- Text improvement service
- Frontend navigation and actions support

**Notification System**
- Redis pub/sub for real-time notifications
- GraphQL subscriptions support
- Notification batching

**Service-to-Service Communication**
- `ServiceAuthMiddleware` and `InternalServicePermission`
- `ServiceAuthUtils` for short-lived service JWT tokens with instance identity
- Webservice registration flow at startup
- `INTERNAL_SERVICE_ACCESS_LEVEL` for internal-only endpoints

**Security**
- Pluggable permission chain (Anonymous → JWT → Organization)
- Row-level filtering (OWNER and ORGANIZATION_ROLE access)
- `SecurityHeadersMiddleware` for HTTP security headers
- Global API rate limiting middleware with Redis support
- Secure cookie defaults (HttpOnly, Secure, SameSite=Lax)
- HMAC-based XSRF token comparison
- Debug mode restricted to DEV environment
- SSL/TLS enforcement for PostgreSQL connections
- Audit logging on sensitive entity access and super user bypass
- Search input sanitization before ILIKE queries
- Open redirect and SSRF prevention on success URLs
- Random generation for dev fixture passwords

**Testing**
- 75% combined test coverage (unit + integration)
- pytest-forked integration for SQLAlchemy registry isolation
- Forked coverage collection via monkey-patched `forked_run_report`

**Documentation**
- Developer guides: creating an app, entities and services, GraphQL API, permissions
- FRS documentation: authentication, JWT permissions, internal service communication, webservice management