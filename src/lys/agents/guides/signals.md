# Real-time SSE signals (back)

Real-time front updates travel over Redis pub/sub → SSE (`/sse/signals`).
The api restricts each connected user to their OWN channel — the channel
contract is the whole security model.

## Channel contract

- **Channel**: `user:{user_id}` — a user receives only signals published on
  their channel (enforced by the SSE endpoint in `api/src/app.py`).
- **Message**: `signal` (SCREAMING_SNAKE name) + `params` (JSON-serializable
  dict).

## Publishing (from a service or task)

```python
# async context (service method with a session running)
if cls.app_manager.pubsub:
    await cls.app_manager.pubsub.publish(
        channel=f"user:{user_id}",
        signal="MY_THING_DONE",
        params={"id": str(thing.id), "status": "ok"},
    )

# sync context (celery task)
cls.app_manager.pubsub.publish_sync(channel=f"user:{user_id}", signal="MY_THING_DONE", params={...})
```

Reference implementation: `NotificationBatchService`
(`lys/apps/user_auth/modules/notification/services.py`) publishing
`NEW_NOTIFICATION`.

## RULES

- **R1 — Own channel only**: publish to `user:{id}` of the user(s) concerned;
  loop over recipients for fan-out. Never invent shared/global channels — the
  SSE endpoint will not deliver them.
- **R2 — Prefer the event system for user-facing effects** (notification
  toast, email): `trigger_event` publishes `NEW_NOTIFICATION` for you
  (see `emails-events.md`). Direct publishing is for data-refresh signals
  (`REFRESH_NODES` style) that a front component listens to.
- **R3 — Params are plain data**: ids and primitives the front can use to
  refetch — never entities, never secrets.
- **R4 — Signal names are a front contract**: the front subscribes by exact
  name (`useSignalSubscription`); renaming breaks consumers silently — treat
  like webservice names.
- **R5 — pubsub may be absent** (worker without redis config, tests): guard
  (`if cls.app_manager.pubsub:`) — publishing is best-effort, never a
  failure of the business operation.

## Front side

`useSignalSubscription((signal) => …, [deps])` from `lys-front/providers`;
debounce reloads it triggers (reference: `NotificationBellRestricted`,
`ImportListRestricted` with its `refreshNotificationTypes` prop).
