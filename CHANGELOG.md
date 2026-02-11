# Changelog

All notable changes to this project will be documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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