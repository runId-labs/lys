# Celery tasks (back)

Background work runs as Celery tasks in the worker. Reference: the lys task
`lys/apps/base/tasks.py` (`send_pending_email`) and the boilerplate's beat
schedule in `worker/settings.py`.

## RULES

- **R1 — `@shared_task`**, standard Celery options (`bind=True`,
  `max_retries`, `default_retry_delay`). Retry with backoff on transient
  failures (reference: `send_pending_email`'s `self.retry(...)`).
- **R2 — Real task pattern** (copy from `lys/apps/base/tasks.py` and
  `lys/apps/user_auth/modules/event/tasks.py`): reach the manager through
  celery's `current_app`, open a **sync** session when a service needs one:
  ```python
  from celery import shared_task, current_app

  @shared_task(bind=True, max_retries=3, default_retry_delay=60)
  def refresh_products(self, client_id: str):
      app_manager = current_app.app_manager
      service = app_manager.get_service("product")
      with app_manager.database.get_sync_session() as session:
          return service.refresh_all(client_id, session)
  ```
  Prefer service methods that manage their own session
  (`emailing_service.send_email(emailing_id)` takes none) — open one only for
  services whose signature requires it.
- **R3 — Register the module** in the celery `tasks=[...]` list of every
  process that executes it (`worker/settings.py`, and `api/settings.py` if the
  api also runs tasks).
- **R4 — Beat schedule** lives in `worker/settings.py`
  (`app_settings.celery.beat_schedule`): stable entry names
  (`"<action>-daily"`), `crontab` schedules, task = full dotted path. Native
  sprint-folder cadence does not apply — carry-over of missed runs is not
  automatic: schedule defensively (idempotent tasks).
- **R5 — Tasks are thin**: same rule as webservices — resolve services through
  the app manager, keep invariants in services so api and worker share them.
- **R6 — Execution tracking (optional)**: lys's base job entities
  (`cron_job_execution`, `migration_job_execution`) + `JobMixin` track runs of
  scheduled jobs — use them when a scheduled task needs an audit trail, not
  for fire-and-forget work.

## ✅ / ❌

| ✅ | ❌ |
|----|----|
| `trigger_event.delay("REPORT_READY", user_id, …)` from a service | Sending SMTP / publishing Redis signals by hand in the task |
| `self.retry(exc=e, countdown=60)` on transient DB errors | Silent `except: pass` |
| Task registered in `worker/settings.py` tasks list | Task module importable only from the api |
