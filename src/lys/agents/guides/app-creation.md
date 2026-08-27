# Creating an app or a module (back)

Read `architecture.md` first. An app = a Python package of modules; a module =
one business domain (its entity + service + node + webservice + fixtures).

## PROCEDURE — new project app

1. Create the package (e.g. `myapp/apps/catalog/`):
   ```
   myapp/apps/catalog/
       __init__.py
       consts.py            # app constants (optional)
       permissions.py       # optional
       modules/
           __init__.py      # ← declare __submodules__ here
           product/
               __init__.py
               entities.py services.py nodes.py webservices.py
               inputs.py models.py fixtures.py   # as needed
   ```
2. `modules/__init__.py` — loading order is real:
   ```python
   from . import product
   from . import category

   __submodules__ = [category, product]   # dependency first
   ```
3. Register the app in **BOTH** `api/settings.py` and `worker/settings.py`,
   AFTER the lys apps (overrides rely on that order):
   ```python
   apps=[…, "lys.apps.licensing", …, "myapp.apps.catalog"],
   ```
   The worker loads it only if it runs its tasks or touches its entities —
   decide per process, then keep the lists in sync where both load it.
4. Build the components in order: `entity.md` → `service.md` → `node.md` →
   `webservice.md` (+ `fixtures` if the module seeds data).
5. Migrate (entities changed): `python main.py makemigrations -m "catalog app"`
   then run your project's own migration command.
6. Regenerate the front's GraphQL schema if webservices were added, using
   your project's schema-export tooling.
7. Self-check: boot the app and confirm it starts clean.

## RULES

- **R1 — One domain per module.** A module's name is its entity's name
  (`product/` hosts `Product`, `ProductService`, `ProductNode`).
- **R2 — Do not modify lys source.** Customize through registration overrides
  (re-register same name) or `override_webservice`/`disable_webservice` in your
  app. If a lys change is genuinely needed, it belongs in the lys repository.
- **R3 — Files are optional per module** but the five canonical files keep
  every module predictable — drop one only when it would be empty (e.g. a
  parametric entity may have no service file if the generic one suffices…
  actually register the service anyway: the registry name is the contract).
- **R4 — Consts live with their owner**: module `consts.py` for module codes,
  app `consts.py` for shared app-level values; never a "global consts" dumping
  ground.
- **R5 — Celery tasks** go in the module's `tasks.py`, registered in the celery
  `tasks=[…]` list of the process that runs them (`worker/settings.py`).
