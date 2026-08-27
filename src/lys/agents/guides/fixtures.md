# Fixtures (back)

Seed data registered at startup (after SERVICES, before NODES — see
`architecture.md`). Two families with different environment semantics.

## Parametric fixtures (reference data)

For `ParametricEntity` rows (statuses, types…). **Always loaded, every
environment.** `delete_previous_data=False` semantics: rows absent from
`data_list` are disabled (`enabled=False`), never deleted — safe to extend
across releases.

```python
from lys.core.fixtures import EntityFixtures
from lys.core.models.fixtures import ParametricEntityFixturesModel
from lys.core.registries import register_fixture


@register_fixture(depends_on=["RoleFixtures"])
class ProductTypeFixtures(EntityFixtures["ProductTypeService"]):
    model = ParametricEntityFixturesModel
    delete_previous_data = False
    data_list = [
        {"id": "STANDARD", "attributes": {"enabled": True, "description": "Standard product"}},
        {"id": "PREMIUM", "attributes": {"enabled": True, "description": "Premium product"}},
    ]
```

## Business fixtures (real entities)

For `Entity` rows (demo users, sample clients — reference:
`lys/apps/licensing/modules/client/fixtures.py`, real demo data). **Environment-gated**
via `_allowed_envs` — business fixtures never load in production regardless of
the list. Everything (including soft-FK columns) goes in `attributes`; the `id`
is optional (let it generate). Transformations like password hashing are
`format_<attr>` hooks:

```python
class DemoProductFixtures(EntityFixtures["ProductService"]):
    model = EntityFixturesModel
    delete_previous_data = True
    _allowed_envs = [EnvironmentEnum.DEV, EnvironmentEnum.DEMO]
    data_list = [
        {"attributes": {"name": "Demo product", "client_id": "<client-uuid>"}},
    ]
```

## RULES

- **R1 — Idempotency**: fixtures run at EVERY boot of every process — no
  duplicates, no destructive wipes of data you didn't seed.
  `delete_previous_data=True` only within fixtures that own their rows.
- **R2 — Load order via `depends_on`** (e.g. roles before role-typed rows);
  the registry resolves the chain.
- **R3 — Transformations are `format_<attr>` classmethods** (e.g.
  `format_password` hashing); never inline logic in `data_list`.
- **R4 — Creating through a service** (business rules must run): override
  `create_from_service(cls, attributes, session)`.
- **R5 — Extending a lys fixture** (adding a status, an access level):
  subclass the lys fixture with `delete_previous_data=False` and add rows —
  never rewrite the base list.
- **R6 — A fixtures.py may import lys service/entity classes** for the
  `EntityFixtures["XService"]` generic — the one sanctioned direct import
  (documented exception in `rules.md`; allow it in import-linter if flagged).

## Self-check

Boot the app and confirm it starts clean, then verify in DEV that a fresh
migrate + boot produces the seeded rows exactly once (re-boot → same count).
