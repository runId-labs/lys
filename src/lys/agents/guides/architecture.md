# Back architecture — lys apps, modules and components

> Framework knowledge kept self-contained in this boilerplate (synced from the
> lys guides). Read before ANY back change.

## What a lys project is

FastAPI + SQLAlchemy + Strawberry GraphQL (Relay) + Celery, organized in **apps**
(registrable in `settings.py`) that contain **modules** (business domains), each
module exposing **components**: entities, services, fixtures, nodes, webservices.
Everything registers itself at import time via decorators into locked registries;
the `AppManager` is the only way to reach a component at runtime.

## App / module structure

```
my_apps/myapp/                     # a Python package = an app
    __init__.py
    consts.py                      # app constants (optional)
    permissions.py                 # custom permission classes (optional)
    modules/
        __init__.py                # declares __submodules__ (loading order!)
        product/
            __init__.py
            entities.py            # SQLAlchemy models          (ENTITIES)
            services.py            # business logic             (SERVICES)
            fixtures.py            # seed data                  (FIXTURES)
            nodes.py               # GraphQL types              (NODES)
            webservices.py         # queries / mutations        (WEBSERVICES)
            inputs.py              # strawberry inputs (optional)
            models.py              # pydantic validation models (optional)
            consts.py              # module constants (optional)
            tasks.py               # celery tasks (optional)
```

## Loading pipeline (hard semantics)

Components load globally, one type at a time, then that registry is **locked**:

```
ENTITIES → SERVICES → FIXTURES → NODES → WEBSERVICES
```

- Within a type: apps in `settings.apps` order, modules in `__submodules__` order.
- Consequence 1: any service can safely use `get_entity` on ANY entity — all
  entities exist before the first service loads.
- Consequence 2: `__submodules__` order matters for readability and fixtures;
  list a dependency module before its dependent.
- Consequence 3: after startup, no new registration is possible.

## Overrides — last-registered-wins

Registering a component with an existing name REPLACES it (nodes, services,
webservices…). This is how a project customizes a lys app without forking it:
re-register `UserNode` after `lys.apps.user_auth` and the whole schema uses
your version. For webservice metadata only, use
`override_webservice(name, …)` / `disable_webservice(name)` from
`lys.core.registries`.

**Node-specific** — nodes extend **by subclassing** the base node class
(inherited fields/resolvers keep working; see `node.md` → "Extending an
existing node"). Avoid full field-by-field rewrites: they drift from the base.
Webservices and services override by re-registration (same contract, new
implementation).

## Registration (settings.py)

```python
app_settings.configure(
    apps=[
        "lys.apps.base", "lys.apps.user_auth", …   # lys first
        "myapp.apps.myapp",                        # project apps AFTER (so overrides win)
    ],
    …
)
```

API and worker share the database and the app list — keep both `settings.py`
in sync (the worker may load fewer component types, see
`configure_component_types`, but the APPS list must match).

## Next reading

`entity.md`, `service.md`, `node.md`, `webservice.md`, `app-creation.md`,
`rules.md` — plus your project's own migration-workflow docs.
