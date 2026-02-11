# Emails and Notifications

This guide covers how to configure and send emails and notifications in Lys, including event-driven dispatch, role-based recipient resolution, organization scoping, templates, and user preferences.

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Event System](#event-system)
4. [Email Dispatch](#email-dispatch)
   - [Critical Emails](#critical-emails)
   - [Batch Emails](#batch-emails)
5. [Notification Dispatch](#notification-dispatch)
6. [Recipient Resolution](#recipient-resolution)
   - [Base Resolution](#base-resolution)
   - [Role-Based Resolution](#role-based-resolution)
   - [Organization-Scoped Resolution](#organization-scoped-resolution)
7. [Email Templates](#email-templates)
   - [Base Template](#base-template)
   - [Writing a Template](#writing-a-template)
   - [Template Context](#template-context)
   - [Translations](#translations)
8. [Emailing Types and Fixtures](#emailing-types-and-fixtures)
   - [Defining an Emailing Type](#defining-an-emailing-type)
   - [Assigning Roles to Emailing Types](#assigning-roles-to-emailing-types)
9. [Registering Events](#registering-events)
   - [Channel Configuration](#channel-configuration)
   - [Extending EventService](#extending-eventservice)
10. [Triggering Events](#triggering-events)
11. [User Preferences](#user-preferences)
12. [Complete Example](#complete-example)
13. [Next Steps](#next-steps)

## Overview

Lys provides a unified event system that coordinates both emails and notifications through a single entry point: the `trigger_event` Celery task. When an event is triggered, the system:

1. Looks up the event configuration (which channels are enabled)
2. Resolves recipients based on roles and organization membership
3. Checks per-user preferences
4. Creates and sends emails / notifications to each recipient

There are two email paths:

| Path | Use Case | Recipient Resolution |
|------|----------|---------------------|
| **Critical** | Password reset, email verification, invitation | Single pre-created recipient, always sent |
| **Batch** | License granted, payment success, subscription events | Multiple recipients resolved by role/organization |

Notifications always use the batch path.

## Architecture

The system is built on two parallel service hierarchies that share a common recipient resolution mixin chain:

```
RecipientResolutionMixin (base)
├── NotificationBatchService (user_auth)
│   ├── + RoleRecipientResolutionMixin (user_role)
│   └── + OrganizationRecipientResolutionMixin (organization)
│
└── EmailingBatchService (base)
    ├── + RoleRecipientResolutionMixin (user_role)
    └── + OrganizationRecipientResolutionMixin (organization)
```

Each app layer adds its resolution logic via the last-registered-wins override pattern. The `trigger_event` Celery task orchestrates both services.

### Key Entities

| Entity | Type | Purpose |
|--------|------|---------|
| `EmailingType` | ParametricEntity | Email template definition (subject, template name, context schema) |
| `Emailing` | Entity | Individual email record (recipient, context, status) |
| `EmailingStatus` | ParametricEntity | Email status (`WAITING`, `SENT`, `ERROR`) |
| `NotificationType` | ParametricEntity | Notification type definition |
| `NotificationBatch` | Entity | Group of notifications from one dispatch |
| `Notification` | Entity | Individual notification record |

## Event System

Events are the entry point for all emails and notifications. Each event type has a channel configuration that defines which channels (email, notification) are enabled by default and which ones the user can configure.

### How It Works

```
Service call (e.g., grant_license())
    │
    ▼
trigger_event.delay(
    event_type="LICENSE_GRANTED",
    user_id="...",
    email_context={...},
    notification_data={...},
)
    │
    ▼ (Celery worker)
EventService.get_channels()  ──→  {"email": True, "notification": True}
    │
    ├──→ EmailingBatchService.dispatch_sync()
    │       ├── resolve recipients (role/org)
    │       ├── filter by user preferences
    │       └── create Emailing + send SMTP
    │
    └──→ NotificationBatchService.dispatch_sync()
            ├── resolve recipients (role/org)
            ├── filter by user preferences
            └── create NotificationBatch + Notifications + publish signal
```

## Email Dispatch

### Critical Emails

Critical emails (password reset, email verification, user invitation) are pre-created with a known recipient before the event is triggered. They bypass recipient resolution and preference checks.

```python
# In a service method (e.g., request_password_reset):
emailing = await emailing_service.generate_emailing(
    type_id="USER_PASSWORD_RESET_REQUESTED",
    email_address=user.email_address.id,
    language_id=user.language_id,
    session=session,
    user=user,
    token=token,
    front_url=front_url,
)

# trigger_event with emailing_id → sends directly, no resolution
trigger_event.delay(
    event_type="USER_PASSWORD_RESET_REQUESTED",
    user_id=str(user.id),
    emailing_id=str(emailing.id),
)
```

When `emailing_id` is provided, `trigger_event` calls `EmailingService.send_email(emailing_id)` directly, without checking preferences or resolving recipients.

### Batch Emails

Batch emails are dispatched to multiple recipients resolved by role and organization. The `EmailingBatchService` handles creation and sending.

```python
# In a service method (e.g., cancel_subscription):
trigger_event.delay(
    event_type="SUBSCRIPTION_CANCELED",
    user_id=str(current_user.id),
    email_context={
        "client_name": client.name,
        "plan_name": plan_version.name,
        "effective_date": str(subscription.end_date),
        "front_url": settings.front_url,
    },
    notification_data={
        "subscription_id": str(subscription.id),
        "plan_name": plan_version.name,
    },
    organization_data={"client_ids": [str(client.id)]},
)
```

The `EmailingBatchService.dispatch_sync()` method:

1. Fetches the `EmailingType` by `type_id`
2. Resolves recipients via the mixin chain (role-based + org-scoped)
3. For each recipient:
   - Checks `should_send_fn` (user preference)
   - Fetches user entity for email address and language
   - Enriches context with per-recipient `private_data` (first_name, last_name)
   - Creates an `Emailing` record
   - Sends via SMTP

## Notification Dispatch

Notifications follow the same pattern as batch emails. The `NotificationBatchService` creates a `NotificationBatch` and individual `Notification` records for each resolved recipient, then publishes a Redis signal for real-time delivery.

```python
trigger_event.delay(
    event_type="LICENSE_GRANTED",
    user_id=str(user.id),
    notification_data={
        "license_name": plan_version.name,
        "client_name": client.name,
    },
)
```

The notification data is stored as JSON on each `Notification` record. The frontend uses this data for display formatting.

## Recipient Resolution

Recipient resolution determines who receives an email or notification. It is provided by a mixin chain that each app extends.

### Base Resolution

The base `RecipientResolutionMixin` resolves recipients from two explicit sources:

- `triggered_by_user_id` — the user who triggered the event
- `additional_user_ids` — extra users explicitly specified

Results are deduplicated.

```python
# Base resolution: just the triggering user and any explicit additions
class RecipientResolutionMixin:
    @classmethod
    def _resolve_recipients_sync(cls, app_manager, session, type_entity,
                                  triggered_by_user_id, additional_user_ids):
        recipient_ids = set()
        if triggered_by_user_id:
            recipient_ids.add(triggered_by_user_id)
        if additional_user_ids:
            recipient_ids.update(additional_user_ids)
        return list(recipient_ids)
```

### Role-Based Resolution

The `user_role` app extends resolution with role-based lookup. If the `EmailingType` (or `NotificationType`) has roles assigned, all users with those roles are included as recipients.

```python
class RoleRecipientResolutionMixin(RecipientResolutionMixin):
    @classmethod
    def _resolve_recipients_sync(cls, app_manager, session, type_entity, ...):
        # Start with base recipients
        recipient_ids = set(super()._resolve_recipients_sync(...))

        # Add users with matching roles
        role_ids = [role.id for role in type_entity.roles]
        if role_ids:
            # Query user_role table for users with these roles
            stmt = select(user_role_table.c.user_id).where(
                user_role_table.c.role_id.in_(role_ids)
            )
            result = session.execute(stmt)
            for row in result:
                recipient_ids.add(row[0])

        return list(recipient_ids)
```

### Organization-Scoped Resolution

The `organization` app adds multi-tenant scoping. When `organization_data` is provided (e.g., `{"client_ids": ["uuid1"]}`), recipients are resolved from the `client_user_role` table filtered by organization level.

```python
# Without organization_data → falls back to role-based resolution
trigger_event.delay(event_type="LICENSE_GRANTED", user_id="...",
                    email_context={...})

# With organization_data → filters by client membership
trigger_event.delay(event_type="SUBSCRIPTION_CANCELED", user_id="...",
                    email_context={...},
                    organization_data={"client_ids": [str(client.id)]})
```

The `OrganizationData` Pydantic model validates the structure:

```python
class OrganizationData(BaseModel):
    client_ids: Optional[List[str]] = None
```

To add custom organization levels (company, establishment), override `validate_organization_data()` with a custom Pydantic model.

## Email Templates

Email templates use Jinja2 with a base template for consistent layout.

### Base Template

All templates extend `_base.html`, which provides the HTML structure, CSS, and block system:

```html
<!-- templates/emails/_base.html -->
<html lang="{% block lang %}fr{% endblock %}">
<head>
    <title>{% block title %}{% endblock %}</title>
</head>
<body>
    <div>
        <h1 style="color: {% block theme_color %}#0d6efd{% endblock %}">
            {% block heading %}{% endblock %}
        </h1>
        <p>{% block greeting %}{% endblock %}</p>
        <p>{% block intro %}{% endblock %}</p>
        {% block info_box %}{% endblock %}
        {% block body %}{% endblock %}
        {% block cta %}
            <a href="{% block cta_url %}{{ front_url }}{% endblock %}">
                {% block cta_text %}{% endblock %}
            </a>
        {% endblock %}
        {% block footer_section %}
            <p>{% block footer %}{% endblock %}</p>
        {% endblock %}
    </div>
</body>
</html>
```

Available blocks:

| Block | Purpose | Default |
|-------|---------|---------|
| `lang` | HTML lang attribute | `fr` |
| `title` | Page title | (empty) |
| `theme_color` | Heading and accent color | `#0d6efd` |
| `heading` | Main heading text | (empty) |
| `greeting` | Greeting line (e.g., "Hello John,") | (empty) |
| `intro` | Introduction paragraph | (empty) |
| `info_box` | Highlighted information block | (empty) |
| `body` | Main content | (empty) |
| `cta` | Call-to-action button container | Button with `cta_url`, `cta_color`, `cta_text` |
| `cta_url` | Button link URL | `{{ front_url }}` |
| `cta_color` | Button background color | `#0d6efd` |
| `cta_text` | Button label | (empty) |
| `footer_section` | Footer container | Paragraph with `footer` block |
| `footer` | Footer text | (empty) |

### Writing a Template

Templates are organized by language: `templates/emails/{language_id}/{template_name}.html`.

Example — `templates/emails/en/license_granted.html`:

```html
{% extends "_base.html" %}
{% block lang %}en{% endblock %}
{% block title %}License Granted{% endblock %}
{% block heading %}New License Granted{% endblock %}
{% block greeting %}Hello {{ private_data.first_name }},{% endblock %}
{% block intro %}Good news! A new license has been granted to you:{% endblock %}
{% block info_box %}
    <div style="background-color: #ffffff; padding: 15px; border-left: 4px solid #0d6efd; margin: 20px 0;">
        <p style="margin: 0;"><strong>Organization:</strong> {{ client_name }}</p>
        <p style="margin: 10px 0 0 0;"><strong>License:</strong> {{ license_name }}</p>
    </div>
{% endblock %}
{% block body %}
    <p>You now have access to all features included in this license.</p>
{% endblock %}
{% block cta_text %}Access the platform{% endblock %}
{% block footer %}If you have any questions, please contact your administrator.{% endblock %}
```

Each template only overrides the blocks it needs. The base template handles the full HTML/CSS structure.

### Template Context

The template context is the dictionary of variables available in Jinja2. It comes from two sources:

1. **`email_context`** — provided by the service that triggers the event (shared across all recipients):

```python
email_context = {
    "client_name": "Acme Corp",
    "plan_name": "Professional",
    "amount": "29.99",
    "currency": "EUR",
    "front_url": "https://app.example.com",
}
```

2. **`private_data`** — automatically enriched per-recipient by `EmailingBatchService` from the user entity:

```python
# Injected automatically for each recipient
recipient_context["private_data"] = {
    "first_name": user.private_data.first_name,
    "last_name": user.private_data.last_name,
}
```

This means `{{ private_data.first_name }}` in templates is always personalized per recipient, even when the same `email_context` is shared.

### Translations

Email subjects are resolved from translation files at `templates/emails/{language_id}/translations.json`:

```json
{
    "license_granted": {
        "subject": "A new license has been granted to you"
    },
    "subscription_canceled": {
        "subject": "Your subscription has been canceled"
    }
}
```

The `EmailingService.get_subject()` method looks up the translated subject by template name and language, falling back to the `EmailingType.subject` field.

## Emailing Types and Fixtures

### Defining an Emailing Type

Each email template is backed by an `EmailingType` parametric entity. Define them as fixtures:

```python
# my_app/modules/emailing/consts.py
ORDER_CONFIRMED_EMAILING_TYPE = "ORDER_CONFIRMED"
ORDER_SHIPPED_EMAILING_TYPE = "ORDER_SHIPPED"
```

```python
# my_app/modules/emailing/fixtures.py
from lys.apps.user_role.modules.emailing.fixtures import (
    EmailingTypeFixtures as BaseEmailingTypeFixtures,
)
from lys.core.registries import register_fixture
from my_app.modules.emailing.consts import (
    ORDER_CONFIRMED_EMAILING_TYPE,
    ORDER_SHIPPED_EMAILING_TYPE,
)


@register_fixture(depends_on=["RoleFixtures"])
class EmailingTypeFixtures(BaseEmailingTypeFixtures):

    data_list = [
        {
            "id": ORDER_CONFIRMED_EMAILING_TYPE,
            "attributes": {
                "enabled": True,
                "subject": "order confirmed",
                "template": "order_confirmed",
                "context_description": {
                    "front_url": None,
                    "order_number": None,
                    "total_amount": None,
                },
            }
        },
        {
            "id": ORDER_SHIPPED_EMAILING_TYPE,
            "attributes": {
                "enabled": True,
                "subject": "order shipped",
                "template": "order_shipped",
                "context_description": {
                    "front_url": None,
                    "order_number": None,
                    "tracking_url": None,
                },
                "roles": ["WAREHOUSE_MANAGER"]
            }
        },
    ]
```

The `context_description` field documents which variables the template expects. It is also used by `EmailingService.compute_context()` to automatically extract values from entity attributes.

### Assigning Roles to Emailing Types

When an emailing type has a `roles` list in its fixture data, the `EmailingTypeFixtures.format_roles()` method populates the `emailing_type_role` association table during fixture loading.

```python
# This emailing type will be dispatched to all users with the WAREHOUSE_MANAGER role
{
    "id": "ORDER_SHIPPED",
    "attributes": {
        "enabled": True,
        "subject": "order shipped",
        "template": "order_shipped",
        "context_description": {...},
        "roles": ["WAREHOUSE_MANAGER"]
    }
}
```

Emailing types without `roles` (or with `roles: []`) are dispatched only to `triggered_by_user_id` and `additional_user_ids`.

## Registering Events

### Channel Configuration

Each event type must be registered in `EventService.get_channels()` with its channel configuration:

```python
{
    "ORDER_CONFIRMED": {
        "email": True,         # Send email by default
        "notification": True,  # Send notification by default
        "blocked": [],         # User can configure both channels
    }
}
```

| Key | Type | Description |
|-----|------|-------------|
| `email` | `bool` | Whether to send email by default |
| `notification` | `bool` | Whether to send notification by default |
| `blocked` | `list[str]` | Channels the user cannot disable (e.g., `["email"]` for mandatory emails) |

### Extending EventService

Create an `EventService` subclass that extends the parent channels with your app's events:

```python
# my_app/modules/event/consts.py
ORDER_CONFIRMED = "ORDER_CONFIRMED"
ORDER_SHIPPED = "ORDER_SHIPPED"
```

```python
# my_app/modules/event/services.py
from lys.apps.user_auth.modules.event.services import EventService as BaseEventService
from lys.core.registries import register_service
from my_app.modules.event import consts


@register_service()
class EventService(BaseEventService):

    @classmethod
    def get_channels(cls) -> dict[str, dict]:
        channels = super().get_channels()
        channels.update({
            consts.ORDER_CONFIRMED: {
                "email": True,
                "notification": True,
                "blocked": [],
            },
            consts.ORDER_SHIPPED: {
                "email": True,
                "notification": False,
                "blocked": [],
            },
        })
        return channels
```

The override chain ensures that all parent events (user lifecycle, licensing) are preserved alongside your custom events.

## Triggering Events

Call `trigger_event.delay()` from any service method to dispatch emails and notifications:

```python
from lys.apps.user_auth.modules.event.tasks import trigger_event


class OrderService(EntityService["Order"]):

    @classmethod
    async def confirm_order(cls, order_id: str, session: AsyncSession):
        order = await cls.get_by_id(order_id, session)
        order.status_id = "CONFIRMED"

        trigger_event.delay(
            event_type="ORDER_CONFIRMED",
            user_id=str(order.owner_id),
            email_context={
                "order_number": order.number,
                "total_amount": str(order.total),
                "front_url": cls.app_manager.settings.front_url,
            },
            notification_data={
                "order_id": str(order.id),
                "order_number": order.number,
            },
        )
```

### Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `event_type` | Yes | Event key matching `EventService.get_channels()` and `EmailingType.id` / `NotificationType.id` |
| `user_id` | Yes | Triggering user ID (included in recipients for base resolution) |
| `emailing_id` | No | Pre-created email ID — bypasses batch dispatch (critical emails only) |
| `email_context` | No | Template variables shared across all email recipients |
| `notification_data` | No | JSON payload stored on each notification |
| `organization_data` | No | Multi-tenant scoping (e.g., `{"client_ids": ["..."]}`) |
| `additional_user_ids` | No | Extra users to include beyond role/org resolution |

## User Preferences

Users can configure which channels they receive for non-blocked events. Preferences are stored in the `user_event_preference` entity and checked per-recipient during dispatch.

The `EventService.should_send()` method resolves the effective preference:

1. If the user has an explicit preference → use it
2. Otherwise → use the default from channel configuration

Blocked channels cannot be disabled by the user. This is enforced at both the preference creation level (`UserEventPreferenceService.create_or_update()`) and the dispatch level.

To get user-configurable events for a settings UI:

```python
event_service = app_manager.get_service("event")
configurable = event_service.get_user_configurable_events()
# Returns events where at least one channel is not blocked
```

## Complete Example

Adding a new "order shipped" email and notification to a custom app:

### 1. Define constants

```python
# my_app/modules/event/consts.py
ORDER_SHIPPED = "ORDER_SHIPPED"
```

```python
# my_app/modules/emailing/consts.py
ORDER_SHIPPED_EMAILING_TYPE = "ORDER_SHIPPED"
```

### 2. Register the event

```python
# my_app/modules/event/services.py
from lys.apps.licensing.modules.event.services import EventService as ParentEventService
from lys.core.registries import register_service
from my_app.modules.event import consts


@register_service()
class EventService(ParentEventService):
    @classmethod
    def get_channels(cls) -> dict[str, dict]:
        channels = super().get_channels()
        channels.update({
            consts.ORDER_SHIPPED: {
                "email": True,
                "notification": True,
                "blocked": [],
            },
        })
        return channels
```

### 3. Create the emailing type fixture

```python
# my_app/modules/emailing/fixtures.py
from lys.apps.user_role.modules.emailing.fixtures import (
    EmailingTypeFixtures as BaseEmailingTypeFixtures,
)
from lys.core.registries import register_fixture


@register_fixture(depends_on=["RoleFixtures"])
class EmailingTypeFixtures(BaseEmailingTypeFixtures):
    data_list = [
        {
            "id": "ORDER_SHIPPED",
            "attributes": {
                "enabled": True,
                "subject": "order shipped",
                "template": "order_shipped",
                "context_description": {
                    "front_url": None,
                    "order_number": None,
                    "tracking_url": None,
                },
                "roles": ["WAREHOUSE_MANAGER"],
            }
        },
    ]
```

### 4. Create email templates

**`templates/emails/en/order_shipped.html`**:

```html
{% extends "_base.html" %}
{% block lang %}en{% endblock %}
{% block title %}Order Shipped{% endblock %}
{% block heading %}Your Order Has Been Shipped{% endblock %}
{% block greeting %}Hello {{ private_data.first_name }},{% endblock %}
{% block intro %}Your order has been shipped and is on its way.{% endblock %}
{% block info_box %}
    <div style="background-color: #ffffff; padding: 15px; border-left: 4px solid #0d6efd; margin: 20px 0;">
        <p style="margin: 0;"><strong>Order:</strong> #{{ order_number }}</p>
    </div>
{% endblock %}
{% block cta_url %}{{ tracking_url }}{% endblock %}
{% block cta_text %}Track your order{% endblock %}
{% block footer %}If you have any questions, please contact your administrator.{% endblock %}
```

Create the equivalent `templates/emails/fr/order_shipped.html` for French.

### 5. Add translations

**`templates/emails/en/translations.json`** (add entry):

```json
{
    "order_shipped": {
        "subject": "Your order has been shipped"
    }
}
```

### 6. Trigger the event

```python
trigger_event.delay(
    event_type="ORDER_SHIPPED",
    user_id=str(order.owner_id),
    email_context={
        "order_number": order.number,
        "tracking_url": f"https://tracking.example.com/{order.tracking_id}",
        "front_url": settings.front_url,
    },
    notification_data={
        "order_id": str(order.id),
        "order_number": order.number,
    },
    organization_data={"client_ids": [str(order.client_id)]},
)
```

This will:
- Resolve all users with the `WAREHOUSE_MANAGER` role in the order's client organization
- Check each user's preference for the `ORDER_SHIPPED` event
- Send a personalized email (with `private_data.first_name`) to each recipient
- Create a notification for each recipient with the order data

## Next Steps

- [Permissions](permissions.md) — access control and row-level filtering
- [Creating an App](creating-an-app.md) — app structure and submodule registration
- [Entities and Services](entities-and-services.md) — defining entities and business logic