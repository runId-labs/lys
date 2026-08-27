# Emails and notifications (back) — the event system

User-facing side effects (emails, notifications) go through ONE Celery entry
point; never send SMTP or publish signals ad hoc.

## The flow

```
business code
    → trigger_event.delay(event_type, user_id,
                          emailing_id?, email_context?, notification_data?,
                          organization_data?, additional_user_ids?)
    → EventService.get_channels()          # {"email": bool, "notification": bool, "blocked": [...]}
    → EmailingBatchService / NotificationBatchService
    → SMTP (templates) / Redis signal (real-time toast + badge)
```

`trigger_event` is importable from `lys.apps.user_auth.modules.event.tasks`
and must be listed in the celery `tasks=[…]` of the process that runs it
(both boilerplate settings already declare it).


## PROCEDURE — create a new event / notification type (end to end)

Example: notify admins when a report is ready. Execute in order.

1. **Pick the code** (SCREAMING_SNAKE, shared identity): `REPORT_READY`.
2. **Declare the channels** — re-register the EventService in a project app
   (loaded after lys apps; base: `lys.apps.user_auth.modules.event.services`,
   or `lys.apps.licensing.modules.event.services` to keep the licensing events
   configured):
   ```python
   from lys.apps.licensing.modules.event.services import EventService as LicensingEventService
   from lys.core.registries import register_service

   @register_service()
   class EventService(LicensingEventService):
       @classmethod
       def get_channels(cls) -> dict[str, dict]:
           channels = super().get_channels()
           channels.update({
               "REPORT_READY": {
                   "email": False,           # notification only
                   "notification": True,
                   "blocked": [],            # channels the user cannot opt out of
               },
           })
           return channels
   ```
3. **Seed the type(s)** — notifications need a `NotificationType` row (emails
   an `EmailingType`). Copy the lys licensing pattern
   (`lys/apps/licensing/modules/notification/{fixtures,models}.py`): a project
   fixtures model extending `ParametricEntityFixturesModel` with
   `roles`/`severity_id`, then a fixture with
   `depends_on=["RoleFixtures", "NotificationSeverityFixtures"]`:
   ```python
   # myapp/…/notification/models.py
   from typing import List
   from lys.core.models.fixtures import ParametricEntityFixturesModel

   class NotificationTypeFixturesModel(ParametricEntityFixturesModel):
       class AttributesModel(ParametricEntityFixturesModel.AttributesModel):
           roles: List[str]
           severity_id: str
       attributes: AttributesModel

   # myapp/…/notification/fixtures.py
   from lys.apps.user_auth.modules.notification.consts import NOTIFICATION_SEVERITY_INFO
   from lys.apps.user_role.modules.notification.services import NotificationTypeService
   from lys.core.fixtures import EntityFixtures
   from lys.core.registries import register_fixture
   from .models import NotificationTypeFixturesModel

   @register_fixture(depends_on=["RoleFixtures", "NotificationSeverityFixtures"])
   class NotificationTypeFixtures(EntityFixtures[NotificationTypeService]):
       model = NotificationTypeFixturesModel
       delete_previous_data = False
       data_list = [
           {"id": "REPORT_READY",
            "attributes": {"enabled": True, "description": "A report is ready to review",
                           "roles": [], "severity_id": NOTIFICATION_SEVERITY_INFO}},
       ]
   ```
4. **Email content (only if channel email)**: `EmailingType` fixture with
   `subject`, `template`, `context_description` + the template file
   `templates/emails/{lang}/{template}.html` in BOTH api and worker + subject
   in `{lang}/translations.json`.
5. **Trigger it** where the fact happens:
   ```python
   from lys.apps.user_auth.modules.event.tasks import trigger_event
   trigger_event.delay("REPORT_READY", user_id, notification_data={"report_id": str(report.id)})
   ```
6. **Front labels + toast** — add the type to the switch in
   `NotificationListFeature` and `NotificationBellRestricted` (translations in
   both), and to the bell's `refreshNotificationTypes` if its arrival must
   refresh a badge/list (see `agents/guides/front/…` restricted-feature guide).
7. **Self-check**: boot the worker (`docker compose logs worker`), trigger the
   event in DEV, follow the log line (`Event REPORT_READY: …`) and check the
   toast/panel on the front; email channel → MailHog.

## RULES

- **R1 — One event type = one identity** shared by `EventService.get_channels()`
  key, `EmailingType.id` and `NotificationType.id`. Codes are SCREAMING_SNAKE
  (`USER_PASSWORD_RESET_REQUESTED`).
- **R2 — Channel configuration is data**: which events email/notify and who
  receives them lives in the EventService channels + fixtures, not in
  `if` statements at call sites.
- **R3 — Extending for project events**:
  1. subclass the lys `EventService` (base: `lys.apps.user_auth.modules.event.services`,
     richer: `lys.apps.licensing.modules.event.services`) and
     `channels.update({...})` in `get_channels()`;
  2. extend `EmailingTypeFixtures` (from
     `lys.apps.user_role.modules.emailing.fixtures`, `depends_on=["RoleFixtures"]`)
     with `subject`, `template`, `context_description` (dict — also drives
     context extraction), `roles`;
  3. add the template `templates/emails/{lang}/{template}.html` extending
     `_base.html` + the subject in `{lang}/translations.json` — in BOTH
     `api/templates/emails/` and `worker/templates/emails/` (the project
     template path replaces lys's, see the repo's templates).
- **R4 — Critical emails** (password reset & co: one recipient, no preference
  filtering): the caller pre-creates the emailing
  (`emailing_service.generate_emailing(...)`) and passes `emailing_id`.
- **R5 — User preferences** (`user_event_preference`) gate batch emails and
  notifications; blocked channels cannot be opted out. Don't bypass.
- **R6 — Front consumption**: notification types surface through the
  notification list/bell — their labels live in the front
  (`NotificationListFeature`/`NotificationBellRestricted` translations + the
  per-type formatters), extend there when adding a type.

## Self-check

Boot the app, trigger one event in DEV, and follow the chain in the worker
logs (email sent) and MailHog (content) — reference your project's README
for the local stack.
