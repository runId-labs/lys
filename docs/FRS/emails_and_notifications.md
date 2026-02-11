# Emails and Notifications

## Table of Contents

1. [Overview](#overview)
2. [Key Concepts](#key-concepts)
3. [Event System](#event-system)
4. [Email Dispatch Flow](#email-dispatch-flow)
5. [Notification Dispatch Flow](#notification-dispatch-flow)
6. [Recipient Resolution](#recipient-resolution)
7. [Database Schema](#database-schema)
8. [Email Rendering](#email-rendering)
9. [User Preferences](#user-preferences)
10. [Use Cases](#use-cases)
11. [Security Considerations](#security-considerations)
12. [Configuration](#configuration)
13. [Extension Points](#extension-points)
14. [Testing Recommendations](#testing-recommendations)
15. [Troubleshooting](#troubleshooting)

## Overview

Lys provides a unified event-driven system for dispatching emails and notifications to users. A single event (e.g., "license granted", "payment failed") can trigger both an email and a real-time notification, each dispatched to recipients resolved by role membership and organization scope.

The system supports two email dispatch modes:

- **Critical emails**: Pre-created, single recipient, always sent (password reset, email verification, invitation)
- **Batch emails**: Multi-recipient, resolved by role and organization, filtered by user preferences

Notifications always follow the batch dispatch model with real-time delivery via Redis pub/sub.

## Key Concepts

### Event Type

A string identifier (e.g., `"LICENSE_GRANTED"`, `"USER_INVITED"`) that serves as the key linking:
- An `EmailingType` (email template configuration)
- A `NotificationType` (notification category)
- A channel configuration in `EventService.get_channels()`

### Channel

A delivery mechanism for an event. Two channels exist:
- **email**: SMTP-based email delivery
- **notification**: Real-time in-app notification via Redis pub/sub

Each event type defines which channels are enabled by default and which channels users cannot disable (blocked).

### Recipient Resolution

The process of determining which users receive an email or notification. Resolution is layered:

| Layer | Source | Condition |
|-------|--------|-----------|
| Base | `triggered_by_user_id` + `additional_user_ids` | Always |
| Role-based | Users with roles linked to the type entity | If `user_role` app is loaded |
| Organization-scoped | Users in specific organizations with matching roles | If `organization` app is loaded and `organization_data` is provided |

Results are deduplicated across all layers.

### Email Context

A dictionary of template variables shared across all email recipients for a single dispatch. Per-recipient personalization (`private_data.first_name`, `private_data.last_name`) is automatically injected by the batch service.

### Organization Data

A Pydantic-validated structure that scopes recipient resolution to specific organizations:

```json
{"client_ids": ["uuid-1", "uuid-2"]}
```

When provided, only users who belong to the specified organizations (via `client_user_role`) and have matching roles receive the dispatch.

## Event System

### Event Lifecycle

```
1. Service method triggers event
       │
       ▼
2. trigger_event Celery task executes
       │
       ├── Lookup channel config via EventService.get_channels()
       │
       ├── Email channel
       │   ├── Critical path (emailing_id provided)
       │   │   └── EmailingService.send_email() → SMTP
       │   │
       │   └── Batch path (no emailing_id)
       │       └── EmailingBatchService.dispatch_sync()
       │           ├── Resolve recipients (mixin chain)
       │           ├── Check user preferences (should_send_fn)
       │           ├── Create Emailing record per recipient
       │           └── Send via SMTP per recipient
       │
       └── Notification channel
           └── NotificationBatchService.dispatch_sync()
               ├── Resolve recipients (mixin chain)
               ├── Check user preferences (should_send_fn)
               ├── Create NotificationBatch + Notification per recipient
               └── Publish Redis signal per recipient
```

### Channel Configuration

Each event type is registered with `EventService.get_channels()`:

```python
{
    "LICENSE_GRANTED": {
        "email": True,         # Send email by default
        "notification": True,  # Send notification by default
        "blocked": [],         # User can toggle both channels
    },
    "USER_PASSWORD_RESET_REQUESTED": {
        "email": True,
        "notification": False,
        "blocked": ["email", "notification"],  # User cannot toggle
    },
}
```

**Configuration fields**:

| Field | Type | Description |
|-------|------|-------------|
| `email` | `bool` | Default: send email for this event |
| `notification` | `bool` | Default: send notification for this event |
| `blocked` | `list[str]` | Channels user cannot disable via preferences |

### Built-in Event Types

**User lifecycle** (`user_auth` app):

| Event | Email | Notification | Blocked |
|-------|-------|-------------|---------|
| `USER_INVITED` | Yes | No | `["email"]` |
| `USER_EMAIL_VERIFICATION_REQUESTED` | Yes | No | `["email"]` |
| `USER_PASSWORD_RESET_REQUESTED` | Yes | No | `["email", "notification"]` |

**Licensing** (`licensing` app):

| Event | Email | Notification | Blocked |
|-------|-------|-------------|---------|
| `LICENSE_GRANTED` | Yes | Yes | (none) |
| `LICENSE_REVOKED` | Yes | Yes | `["email", "notification"]` |
| `SUBSCRIPTION_PAYMENT_SUCCESS` | Yes | Yes | (none) |
| `SUBSCRIPTION_PAYMENT_FAILED` | Yes | Yes | `["email", "notification"]` |
| `SUBSCRIPTION_CANCELED` | Yes | Yes | (none) |

## Email Dispatch Flow

### Critical Email Path

Used for transactional emails where the recipient is known in advance and delivery is mandatory.

**Steps**:

1. Service creates `Emailing` record via `EmailingService.generate_emailing()`
   - Receives type_id, email_address, language_id, and context kwargs
   - Resolves `context_description` from `EmailingType` to build template context
   - Creates the `Emailing` entity with `WAITING` status
2. Service calls `trigger_event.delay(emailing_id=str(emailing.id))`
3. Celery task calls `EmailingService.send_email(emailing_id)` directly
4. No recipient resolution, no preference check, no batch

**Characteristics**:
- Single recipient (email address stored on the Emailing record)
- Always sent regardless of user preferences
- Retried up to 3 times on failure (60-second delay)
- Used for: password reset, email verification, user invitation

### Batch Email Path

Used for event-driven emails where recipients are resolved dynamically.

**Steps**:

1. Service calls `trigger_event.delay(event_type=..., email_context={...})`
2. Celery task calls `EmailingBatchService.dispatch_sync()`
3. Batch service fetches `EmailingType` by `type_id`
4. Mixin chain resolves recipient user IDs:
   - Base: `triggered_by_user_id` + `additional_user_ids`
   - Role: users with roles linked to the `EmailingType`
   - Organization: users in specified organizations with matching roles
5. For each recipient:
   - `should_send_fn(user_id)` checks user preference via `EventService.should_send()`
   - User entity is fetched for email address and language
   - Template context is enriched with per-recipient `private_data`
   - `Emailing` record is created with `WAITING` status
   - `EmailingService.send_email()` sends via SMTP
   - Status updated to `SENT` or `ERROR`

**Characteristics**:
- Multiple recipients resolved dynamically
- Filtered by user preferences (configurable channels)
- Per-recipient personalization (`private_data`)
- Language-specific template selection per recipient
- Each recipient gets their own `Emailing` record

### Email Sending

`EmailingService.send_email()` handles the SMTP delivery:

1. Opens a sync database session (separate from caller's session)
2. Loads the `Emailing` record with its `EmailingType`
3. Resolves the translated subject via `translations.json`
4. Renders the Jinja2 template with the stored context
5. Constructs a MIME multipart message (HTML)
6. Sends via SMTP (with optional STARTTLS and authentication)
7. Updates status to `SENT` on success, `ERROR` on failure

## Notification Dispatch Flow

**Steps**:

1. Service calls `trigger_event.delay(notification_data={...})`
2. Celery task calls `NotificationBatchService.dispatch_sync()`
3. Batch service creates a `NotificationBatch` record with event data
4. Mixin chain resolves recipient user IDs (same chain as emails)
5. For each recipient:
   - `should_send_fn(user_id)` checks user preference
   - Individual `Notification` record is created (linked to batch)
   - Redis signal `NEW_NOTIFICATION` is published to the recipient's channel

**Differences from email dispatch**:
- `NotificationBatch` entity groups all notifications from one event
- Individual `Notification` entities have `is_read` tracking
- Delivery is via Redis pub/sub (real-time) instead of SMTP
- No template rendering (frontend handles display from `data` JSON)

## Recipient Resolution

### Resolution Chain

The recipient resolution mixin chain is shared between `EmailingBatchService` and `NotificationBatchService`:

```
RecipientResolutionMixin (base app)
    └── _resolve_recipients_sync(app_manager, session, type_entity,
                                  triggered_by_user_id, additional_user_ids)
        → {triggered_by_user_id} ∪ {additional_user_ids}

RoleRecipientResolutionMixin (user_role app)
    └── _resolve_recipients_sync(...)
        → super() ∪ {users WHERE user_role.role_id IN type_entity.roles}

OrganizationRecipientResolutionMixin (organization app)
    └── _resolve_recipients_sync(..., organization_data=None)
        → if organization_data: {triggered_by} ∪ {additional}
            ∪ {users WHERE client_user_role.role_id IN type_entity.roles
               AND client_user_role.client_id IN organization_data.client_ids}
        → else: super() (falls back to role-based)
```

### Resolution Rules

| Scenario | Resolution |
|----------|-----------|
| No roles, no org data | Only `triggered_by_user_id` and `additional_user_ids` |
| Roles assigned, no org data | Base recipients + all users with matching roles globally |
| Roles assigned, org data provided | Base recipients + users with matching roles in specified organizations |
| No roles, org data provided | Only base recipients (org scoping requires roles) |

### Deduplication

All resolution layers produce deduplicated sets. A user appearing in multiple layers (e.g., triggering user who also has the required role) receives only one email/notification.

### Missing Data Handling

| Condition | Behavior |
|-----------|----------|
| `user_role` table not found | Role-based resolution skipped, warning logged |
| `client_user_role` entity not found | Organization resolution skipped, warning logged |
| Recipient user not found | Skipped, warning logged |
| Recipient has no email address | Skipped (emails only), warning logged |
| Recipient has no `private_data` | Email sent without `private_data` context enrichment |

## Database Schema

### Email Entities

```
emailing_status (ParametricEntity)
    ├── id: str (PK) — "WAITING", "SENT", "ERROR"
    └── enabled: bool

emailing_type (ParametricEntity)
    ├── id: str (PK) — e.g., "LICENSE_GRANTED"
    ├── subject: str — fallback subject line
    ├── template: str — template file name (e.g., "license_granted")
    ├── context_description: JSON — schema of template variables
    └── roles → [role] (M2M via emailing_type_role, added by user_role app)

emailing (Entity)
    ├── id: UUID (PK, auto-generated)
    ├── email_address: str — recipient address
    ├── context: JSON — template variables for this email
    ├── error: JSON — error details if sending failed
    ├── status_id: str (FK → emailing_status)
    ├── type_id: str (FK → emailing_type)
    ├── language_id: str (FK → language)
    ├── created_at: datetime
    └── updated_at: datetime

emailing_type_role (association table, added by user_role app)
    ├── emailing_type_id: str (PK, FK → emailing_type)
    ├── role_id: str (PK, FK → role)
    └── created_at: datetime
```

### Notification Entities

```
notification_type (ParametricEntity)
    ├── id: str (PK) — e.g., "LICENSE_GRANTED"
    └── roles → [role] (M2M via notification_type_role, added by user_role app)

notification_batch (Entity)
    ├── id: UUID (PK, auto-generated)
    ├── type_id: str (FK → notification_type)
    ├── triggered_by_user_id: str (FK → user, nullable)
    ├── data: JSON — event payload for frontend formatting
    ├── created_at: datetime
    └── updated_at: datetime

notification (Entity)
    ├── id: UUID (PK, auto-generated)
    ├── batch_id: UUID (FK → notification_batch, CASCADE)
    ├── user_id: str (FK → user, CASCADE)
    ├── is_read: bool (default: false)
    ├── created_at: datetime
    └── updated_at: datetime
```

### Event Preference Entity

```
user_event_preference (Entity)
    ├── id: UUID (PK, auto-generated)
    ├── user_id: str (FK → user)
    ├── event_type: str — event type key
    ├── channel: str — "email" or "notification"
    ├── enabled: bool
    ├── created_at: datetime
    └── updated_at: datetime
```

### Entity Relationships

```
EmailingType ──M2M── Role (via emailing_type_role)
EmailingType ──1:N── Emailing (via type_id)
EmailingStatus ──1:N── Emailing (via status_id)
Language ──1:N── Emailing (via language_id)

NotificationType ──M2M── Role (via notification_type_role)
NotificationType ──1:N── NotificationBatch (via type_id)
NotificationBatch ──1:N── Notification (CASCADE)
User ──1:N── Notification (CASCADE)

User ──1:N── UserEventPreference (via user_id)
```

## Email Rendering

### Template System

Emails use Jinja2 templates with a base template inheritance pattern.

**Template location**: `{settings.email.template_path}/{language_id}/{template_name}.html`

Example: `templates/emails/en/license_granted.html`

### Base Template

All templates extend `_base.html` which provides:

- Responsive HTML structure (max-width: 600px)
- Block system for content sections
- Default styling (Arial font, card layout, button styling)

**Available blocks**:

| Block | Purpose |
|-------|---------|
| `lang` | HTML lang attribute (default: `fr`) |
| `title` | Document title |
| `theme_color` | Heading and accent color (default: `#0d6efd`) |
| `heading` | Main heading text |
| `greeting` | Personalized greeting (e.g., "Hello John,") |
| `intro` | Introduction paragraph |
| `info_box` | Highlighted information section |
| `body` | Main content area |
| `cta` | Call-to-action button container |
| `cta_url` | Button link (default: `{{ front_url }}`) |
| `cta_color` | Button color (default: `#0d6efd`) |
| `cta_text` | Button label |
| `footer_section` | Footer container |
| `footer` | Footer text content |

### Subject Resolution

Email subjects are resolved in order:

1. `translations.json` lookup by template name and language
2. Fallback to `EmailingType.subject` field

Translation file path: `{template_path}/{language_id}/translations.json`

```json
{
    "license_granted": {
        "subject": "A new license has been granted to you"
    }
}
```

### Context Description

The `EmailingType.context_description` field documents the template variables and enables automatic context extraction from entity attributes:

```json
{
    "front_url": null,
    "client_name": null,
    "plan_name": null,
    "user": [{"private_data": ["first_name", "last_name"]}]
}
```

- Keys with `null` values represent scalar variables passed directly
- Keys with list values describe entity attribute paths for `compute_context()`

### Per-Recipient Enrichment

`EmailingBatchService` automatically injects `private_data` for each recipient:

```python
recipient_context["private_data"] = {
    "first_name": user.private_data.first_name,
    "last_name": user.private_data.last_name,
}
```

This enables personalized greetings (`{{ private_data.first_name }}`) in templates while sharing the base `email_context` across all recipients.

## User Preferences

### Preference Model

Each user can configure per-event, per-channel preferences:

| Field | Description |
|-------|-------------|
| `user_id` | The user |
| `event_type` | Event type key (e.g., `"LICENSE_GRANTED"`) |
| `channel` | `"email"` or `"notification"` |
| `enabled` | Whether the user wants this channel |

### Preference Resolution

When dispatching, the system resolves effective preferences per recipient:

1. Check `UserEventPreference` for explicit user preference
2. If no explicit preference: use default from `EventService.get_channels()`
3. If channel is in `blocked` list: always enabled, user cannot disable

### Blocked Channels

Blocked channels enforce delivery regardless of user preferences:

- `blocked: ["email"]` — email is always sent, user cannot opt out
- `blocked: ["email", "notification"]` — both channels mandatory
- `blocked: []` — user can configure both channels

Blocking is enforced at two levels:
- **Creation**: `UserEventPreferenceService.create_or_update()` rejects preferences for blocked channels
- **Dispatch**: `should_send_fn` respects defaults for events without explicit preferences

### Configurable Events API

`EventService.get_user_configurable_events()` returns events where at least one channel is not blocked, formatted for frontend settings UI:

```python
{
    "LICENSE_GRANTED": {
        "email": {"default": True, "configurable": True},
        "notification": {"default": True, "configurable": True},
    },
    "SUBSCRIPTION_PAYMENT_SUCCESS": {
        "email": {"default": True, "configurable": True},
        "notification": {"default": True, "configurable": True},
    },
}
```

## Use Cases

### UC-1: Password Reset Email (Critical Path)

**Preconditions**: User exists with a verified email address.

**Flow**:
1. User requests password reset via public endpoint
2. System creates a one-time token
3. System creates an `Emailing` record with the token and user data
4. `trigger_event.delay(event_type="USER_PASSWORD_RESET_REQUESTED", emailing_id=...)` is called
5. Celery worker sends the email directly via SMTP
6. No preference check (channel is blocked)

**Outcome**: User receives a password reset email with a token link.

### UC-2: License Granted (Batch Path, Role-Based)

**Preconditions**: `LICENSE_GRANTED` emailing type exists with no roles assigned. Licensing app is loaded.

**Flow**:
1. Admin grants a license to a user
2. Service calls `trigger_event.delay(event_type="LICENSE_GRANTED", user_id=target_user_id, email_context={...}, notification_data={...})`
3. Celery worker resolves recipients:
   - Base: only the target user (no roles assigned to this type)
4. For the target user: checks preference, creates `Emailing`, sends via SMTP
5. Notification batch is created with one `Notification` for the target user

**Outcome**: The target user receives one email and one notification.

### UC-3: Subscription Payment Failed (Batch Path, Role + Org Scoped)

**Preconditions**: `SUBSCRIPTION_PAYMENT_FAILED` emailing type has `LICENSE_ADMIN` role assigned. Multiple users exist with the `LICENSE_ADMIN` role in the client organization.

**Flow**:
1. Mollie webhook reports a failed payment
2. Service calls `trigger_event.delay(event_type="SUBSCRIPTION_PAYMENT_FAILED", user_id=admin_id, email_context={...}, organization_data={"client_ids": [client_id]})`
3. Celery worker resolves recipients:
   - Base: admin_id
   - Organization: users with `LICENSE_ADMIN` role in the specified client
4. For each resolved user: checks preference (blocked — always sends), creates `Emailing` with personalized `private_data`, sends via SMTP
5. Notification batch dispatched similarly

**Outcome**: All license administrators in the affected organization receive a personalized email and notification about the failed payment. Users cannot opt out (blocked channel).

### UC-4: User Opts Out of License Notifications

**Preconditions**: User has `LICENSE_GRANTED` events enabled (default).

**Flow**:
1. User disables the notification channel for `LICENSE_GRANTED` in settings
2. `UserEventPreferenceService.create_or_update(user_id, "LICENSE_GRANTED", "notification", False)` is called
3. Next time a license is granted and the user is a recipient:
   - `should_send_fn("notification")` returns `False` for this user
   - Notification is skipped for this user
   - Email is still sent (separate preference)

**Outcome**: User no longer receives in-app notifications for license grants, but still receives emails.

### UC-5: Event with Organization Scoping Fallback

**Preconditions**: Event is triggered without `organization_data`.

**Flow**:
1. Service calls `trigger_event.delay(event_type="SUBSCRIPTION_CANCELED", user_id=..., email_context={...})`
2. `OrganizationRecipientResolutionMixin._resolve_recipients_sync()` checks: `organization_data` is `None`
3. Falls back to `RoleRecipientResolutionMixin` (parent)
4. Resolves all users globally with roles linked to the emailing type

**Outcome**: Without organization scoping, all users with matching roles (globally) receive the dispatch. This is the fallback behavior when `organization_data` is not provided.

## Security Considerations

### Email Content

- Email contexts are stored in the database as JSON. Template variables should not contain sensitive data (passwords, tokens) beyond what is necessary for the email purpose.
- One-time tokens in password reset emails have limited validity and are single-use.
- The `private_data` enrichment only injects `first_name` and `last_name`, not sensitive fields.

### SMTP Security

- STARTTLS is enabled by default for SMTP connections
- SMTP credentials are stored in application settings (not in the database)
- The `send_email()` method uses a dedicated sync session, isolated from the caller's session

### Preference Enforcement

- Blocked channels cannot be disabled by users, enforced at both the preference creation and dispatch levels
- Security-critical events (password reset, license revoked, payment failed) have all channels blocked

### Recipient Isolation

- Each recipient gets their own `Emailing` record with their own context
- Per-recipient `private_data` is injected into a copy of the shared context (original context is not mutated)
- Template rendering happens per recipient with their language-specific template

### Access Control

- `Emailing` entities have empty `accessing_users()` and `accessing_organizations()` — they are not directly exposed via GraphQL queries
- `Notification` entities implement `accessing_users()` returning `[self.user_id]` — users can only see their own notifications
- `NotificationBatch` implements `accessing_users()` returning the triggering user

## Configuration

### Email Settings

```python
app_settings.configure(
    email=EmailSettings()
)
app_settings.email.server = "smtp.example.com"
app_settings.email.port = 587
app_settings.email.sender = "noreply@example.com"
app_settings.email.login = "smtp-user"
app_settings.email.password = "smtp-password"
app_settings.email.starttls = True
app_settings.email.template_path = "/templates/emails"
```

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `server` | `str` | `"localhost"` | SMTP server hostname |
| `port` | `int` | `587` | SMTP server port |
| `sender` | `str` | (required) | Sender email address |
| `login` | `str` | `None` | SMTP authentication login |
| `password` | `str` | `None` | SMTP authentication password |
| `starttls` | `bool` | `True` | Enable STARTTLS encryption |
| `template_path` | `str` | `"/templates/emails"` | Path to email templates directory |

### Celery Configuration

`trigger_event` is a Celery shared task. It requires:

- A Celery broker (Redis or RabbitMQ)
- The task module registered in settings: `celery.tasks = ["lys.apps.user_auth.modules.event.tasks"]`
- `app_manager` available on the Celery app instance (`current_app.app_manager`)

Task retry configuration:

| Setting | Value |
|---------|-------|
| `max_retries` | 3 |
| `default_retry_delay` | 60 seconds |
| `bind` | True (access to `self.retry()`) |

## Extension Points

### Adding a New Event Type

1. Define the event type constant
2. Register it in `EventService.get_channels()` (extend via subclass)
3. Create an `EmailingType` fixture with template name and context description
4. Create email templates for each supported language
5. Add translation entries for the email subject
6. Call `trigger_event.delay()` from the relevant service method

### Custom Recipient Resolution

Override `_resolve_recipients_sync()` or `_resolve_recipients()` on your batch service to add custom resolution logic. The mixin chain supports cooperative inheritance via `super()`.

### Custom Organization Levels

Override `validate_organization_data()` on `OrganizationRecipientResolutionMixin` to accept additional organization levels:

```python
class CustomOrganizationData(BaseModel):
    client_ids: Optional[List[str]] = None
    department_ids: Optional[List[str]] = None
```

The `_build_organization_filters()` method dynamically maps `{level}_ids` keys to entity attributes on `client_user_role` or `user`.

### Custom Email Context

Two approaches:

- **Direct context**: Pass `email_context` dict to `trigger_event.delay()` with all template variables
- **Entity-based context**: Use `EmailingService.compute_context()` with `context_description` to automatically extract values from entity attributes

### Extending EventService

Subclass `EventService` and override `get_channels()` to add app-specific events while preserving parent events via `super().get_channels()`. The last-registered-wins pattern ensures the most specific subclass is used.

## Testing Recommendations

### Unit Tests

- **Mixin resolution**: Test each mixin level independently with mocked sessions and entities
- **EmailingBatchService**: Test dispatch flow with mocked `_resolve_recipients_sync`, `send_email`, and user lookups
- **EventService**: Test `get_channels()` inheritance chain and `should_send()` preference resolution
- **Template rendering**: Render each template with complete context, verify no missing variables
- **Context completeness**: Verify each `trigger_event` call provides all variables listed in `context_description`
- **Fixture validation**: Verify `context_description` keys match template variables

### Integration Tests

- **Role-based dispatch**: Create users with roles, dispatch, verify correct number of `Emailing` records
- **Organization-scoped dispatch**: Create multi-tenant setup, dispatch with `organization_data`, verify recipient filtering
- **Preference filtering**: Create user preferences, dispatch, verify skipped recipients
- **Private data enrichment**: Dispatch to users with `private_data`, verify per-recipient context

### Key Constraints for Tests

- `send_email()` uses `get_sync_session()` which creates a separate sync engine — SQLite in-memory databases cannot share data between async and sync engines
- Integration tests require `--forked` for SQLAlchemy registry isolation
- The `emailing` module must be listed in `__submodules__` for each app that extends it

## Troubleshooting

### Emails Not Being Sent

**Symptom**: `trigger_event` completes but no emails are dispatched.

**Possible causes**:
- Event type not registered in `EventService.get_channels()` → add channel configuration
- `email` channel set to `False` for the event → set to `True`
- No `EmailingType` fixture for the event type → create fixture with matching ID
- No roles assigned to the emailing type and no `triggered_by_user_id` → assign roles or provide user_id
- User preference disabled the email channel → check `user_event_preference` table

### Recipients Not Resolved

**Symptom**: Emails created but sent to fewer recipients than expected.

**Possible causes**:
- `emailing` module not listed in app's `modules/__init__.py` `__submodules__` → add the import and list entry
- `user_role` is a raw SQLAlchemy Table, not a registered entity → mixin uses `Base.metadata.tables` fallback
- Roles not linked to the emailing type in fixtures → check `emailing_type_role` table
- `organization_data` not provided → resolution falls back to global role-based (no org filtering)
- Users don't have the required role in the specified organization → check `client_user_role` table

### Template Rendering Errors

**Symptom**: `Emailing` records created with `ERROR` status.

**Possible causes**:
- Missing template file at `{template_path}/{language_id}/{template_name}.html`
- Template references a variable not in the context → add to `email_context` or `context_description`
- `_base.html` not found → verify it exists at `{template_path}/_base.html`
- Language ID not matching template directory → check user's `language_id`

### Preferences Not Applied

**Symptom**: Users receive emails/notifications despite opting out.

**Possible causes**:
- Channel is in the `blocked` list for this event → blocked channels always send
- Preference record has wrong `event_type` or `channel` value
- `should_send_fn` not passed to `dispatch_sync()` → preferences not checked