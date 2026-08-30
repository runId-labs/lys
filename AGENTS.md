# AGENTS.md — lys

FastAPI library providing a Django-inspired modular framework for building
GraphQL APIs with SQLAlchemy, Celery, Strawberry/Relay — component registries,
authentication, and permission systems.

## For agents working on lys itself

### Codebase map

#### Core: `src/lys/core/`

| Directory | Purpose |
|-----------|---------|
| `entities.py` | `Entity`, `ParametricEntity` base classes |
| `services.py` | `EntityService` base class |
| `fixtures.py` | `EntityFixtures` base class |
| `registries.py` | Registration decorators and `AppRegistry` |
| `graphql/` | Nodes, types, decorators, registries |
| `consts/` | Component types, environments, webservice constants |
| `interfaces/` | Abstract interfaces for permissions, services, fixtures |
| `utils/` | Auth utilities, database manager |

#### Apps: `src/lys/apps/`

| App | Modules | Extra Files |
|-----|---------|-------------|
| `base` | one_time_token, language, job, emailing, log, access_level, webservice | permissions, middlewares, consts, tasks |
| `user_auth` | access_level, emailing, notification, event, webservice, user, auth | permissions, middlewares, consts, errors, utils |
| `user_role` | access_level, auth, notification, role, user, webservice | consts, errors, models |
| `organization` | access_level, auth, user, client, notification, role, webservice | abstracts, permissions, consts |
| `file_management` | file_import, stored_file | — |
| `ai` | core, conversation, text_improvement | tasks |
| `licensing` | application, rule, plan, auth, checker, client, mollie, role, subscription, user, event, emailing, webservice | registries, tasks, consts, errors |

Each module lives at `src/lys/apps/{app}/modules/{module}/` and can contain:
`entities.py`, `services.py`, `fixtures.py`, `nodes.py`, `webservices.py`.

### Registry names

Names used with `app_manager.get_entity(name)` and `app_manager.get_service(name)`
(= `__tablename__`):

- **base**: `one_time_token_status`, `one_time_token_type`, `language`, `access_level`, `emailing_status`, `emailing_type`, `emailing`, `job_status`, `job`, `cron_job_execution`, `migration_job_execution`, `log`, `webservice`
- **user_auth**: `user_status`, `gender`, `login_attempt_status`, `webservice_public_type`, `notification_type`, `user`, `user_private_data`, `user_refresh_token`, `user_one_time_token`, `user_emailing`, `user_email_address`, `user_audit_log_type`, `user_audit_log`, `user_login_attempt`, `user_event_preference`, `notification_batch`, `notification`
- **user_role**: `role`, `role_webservice`
- **organization**: `client`, `client_user_role`
- **file_management**: `stored_file_type`, `stored_file`, `file_import_type`, `file_import_status`, `file_import`
- **ai**: `ai_conversation`, `ai_message`, `ai_message_feedback`
- **licensing**: `license_application`, `license_rule`, `license_plan`, `license_plan_version`, `license_plan_version_rule`, `license_currency`, `license_price_period`, `license_plan_version_price`, `subscription`

Adding/removing/renaming a registry name = update this list IN THE SAME commit.

### Common imports

#### Registration decorators

```python
from lys.core.registries import register_entity, register_service, register_fixture, register_node
from lys.core.registries import override_webservice, disable_webservice
from lys.core.graphql.registries import register_query, register_mutation
```

#### Base classes

```python
from lys.core.entities import Entity, ParametricEntity
from lys.core.services import EntityService
from lys.core.fixtures import EntityFixtures
from lys.core.graphql.nodes import EntityNode, ServiceNode, parametric_node
from lys.core.graphql.types import Query, Mutation
```

#### GraphQL decorators

```python
from lys.core.graphql.getter import lys_getter
from lys.core.graphql.connection import lys_connection
from lys.core.graphql.create import lys_creation
from lys.core.graphql.edit import lys_edition
from lys.core.graphql.delete import lys_delete
```

#### Access level constants

```python
from lys.core.consts.webservices import CONNECTED_ACCESS_LEVEL, OWNER_ACCESS_LEVEL, INTERNAL_SERVICE_ACCESS_LEVEL
from lys.apps.user_role.consts import ROLE_ACCESS_LEVEL
from lys.apps.organization.consts import ORGANIZATION_ROLE_ACCESS_LEVEL
```

### Architecture rules

The consolidated MUST/NEVER list (singular table names, `Uuid(as_uuid=False)`
soft FKs, `app_manager`-only access, override patterns, environment rules)
lives in `agents/guides/rules.md` — update that guide IN THE SAME commit as
any behavior change. The per-topic guides (`entity.md`, `service.md`,
`node.md`, `webservice.md`, `permissions.md`, …) own the detailed contracts.

### Development commands

```bash
pip install -e .                                    # Install

pytest tests/unit/                                  # Unit tests only
pytest tests/integration/ --forked                  # Integration tests only
pytest tests/e2e/ --forked                          # E2E tests only

# Combined coverage (ALWAYS use this method — separate processes required)
pytest tests/unit/ --cov=src/lys --cov-report=
pytest tests/integration/ --forked --cov=src/lys --cov-append --cov-report=
pytest tests/e2e/ --forked --cov=src/lys --cov-append --cov-report=term-missing
```

Unit, integration, and e2e tests cannot run in the same pytest process due
to SQLAlchemy registry singleton isolation. Use `--cov-append` to accumulate
coverage across all three runs.

**Coverage threshold**: combined coverage (unit + integration + e2e) MUST
remain at or above **75%**. Do not merge changes that lower coverage below
this threshold.

Test file structure: `tests/{unit,integration}/apps/{app_name}/test_{module}_{component}.py`

### Documentation reference

Consult these docs by task:

- **Permissions / access control** → `docs/FRS/jwt_permissions.md`, `docs/guides/permissions.md`
- **Authentication flows (login, logout, tokens)** → `docs/FRS/auth.md`
- **Service-to-service communication** → `docs/FRS/internal_service_communication.md`
- **Webservice configuration and access levels** → `docs/FRS/webservice_management.md`
- **Creating a new app** → `docs/guides/creating-an-app.md`
- **Entities and services** → `docs/guides/entities-and-services.md`
- **GraphQL queries/mutations** → `docs/guides/graphql-api.md`
- **Emails, notifications, events** → `docs/guides/emails-and-notifications.md`, `docs/FRS/emails_and_notifications.md`
- **Implementation notes and migrations** → `docs/todos/`

Agent runbooks for the same topics: `src/lys/agents/guides/` (shipped in the
wheel — a guide that drifts from the code is a bug).

### Development guidelines

#### Production-grade code standards

- **Production mindset**: all code MUST be production-ready — no shortcuts,
  no "good enough for now"; every implementation targets real deployments.
- **No hardcoded values**: anything that may vary between environments or
  projects MUST be configurable via `AppSettings` (ultimately from `.env`).
  Never hardcode secrets, URLs, emails, credentials.
- **Security by default**: OWASP practices; `secrets` for randomness; bcrypt
  for passwords; never log sensitive data; validate and sanitize external
  inputs.
- **Follow lys architecture**: `app_manager` for entity/service access,
  registry system, component lifecycle — never bypass with direct imports or
  ad-hoc patterns.
- **Idempotent operations**: startup hooks and data initialization safe to
  run repeatedly (no duplicates, no data loss).
- **Fail safely**: handle errors without exposing internals; log with
  context but never leak sensitive information.

#### Language and documentation standards

- **Project language**: all code, comments, documentation, and commit
  messages in English.
- Objective, factual language — no marketing terms, no superlatives;
  focus on functionality, behavior and implementation details.

#### Code style standards

- **PEP 8**, line length ≤ 120, 4 spaces, double quotes, type hints.
- **Imports**: stdlib → third-party → local; absolute preferred; top of
  file (inline only when strictly necessary).
- **Naming**: `snake_case` functions/variables/modules, `PascalCase`
  classes, `UPPER_CASE` constants.
- **Whitespace**: two blank lines between top-level definitions, one
  between methods, no trailing whitespace.
- **Docstrings** on public modules/functions/classes/methods (Google/NumPy
  style) — document behavior, parameters, returns, side effects.

### Git & commit workflow

#### Git rules

- **CRITICAL**: Do NOT sign commits — no GPG signatures, no Co-Authored-By
  lines, no agent-generated attribution footers.
- Commit messages contain ONLY the conventional commit format with
  description.
- **R3 — ⛔ NO COMMIT. NO PUSH. NO DB DELETE. NO DB MODIFY. ⛔**
  **WITHOUT AN EXPLICIT, UNAMBIGUOUS "COMMIT" OR "PUSH" INSTRUCTION FROM THE USER.**
  Implementing is NOT committing. A compliment is NOT a commit order.
  A nod of approval is NOT a push order. A design agreement is NOT a push order.
  If you are unsure whether the user just gave you permission to commit or
  push: **ASK. DO NOT GUESS. DO NOT ASSUME.**
  This rule has ZERO tolerance. Violating it is a breach of trust.
  Applies to: git commit, git push, database DROP/DELETE/TRUNCATE/ALTER,
  file deletion outside the current task scope.

#### Commit process

When the user validates code and asks to commit:

1. **Write/update tests** covering the changes (unit, integration, or e2e).
   Verify they pass.
2. **Run combined coverage** and update the README badge:
   ```bash
   pytest tests/unit/ --cov=src/lys --cov-report=
   pytest tests/integration/ --forked --cov=src/lys --cov-append --cov-report=
   pytest tests/e2e/ --forked --cov=src/lys --cov-append --cov-report=term-missing
   ```
   - Parse the **total coverage percentage** from the output.
   - Read the current badge from `README.md` line 3.
   - **If coverage increased or stayed the same**: update the badge (green
     ≥75%, yellow 60-74%, red <60%).
   - **If coverage decreased**: alert the user with old and new values; only
     update the badge if explicitly approved.
3. **Determine commit type** using conventional commit format:
   ```
   type(scope): description

   - Detail bullet points
   ```
4. **Update `CHANGELOG.md`** under `[Unreleased]` (Added / Changed / Fixed /
   Removed).
5. **Auto-detect version bump** from commit type, update `pyproject.toml`:
   - `fix:`, `refactor:` → patch
   - `feat:` → minor
   - `feat!:` / `BREAKING CHANGE` → major
   - `docs:`, `chore:`, `test:`, `style:` → none
6. **If the version was bumped, archive `[Unreleased]` in the CHANGELOG** —
   MANDATORY:
   - Rename `## [Unreleased]` to `## [{new_version}] - {today YYYY-MM-DD}`.
   - Insert a fresh empty `## [Unreleased]` heading above it.
   - Verify: `grep -n "^## " CHANGELOG.md | head -5` shows `[Unreleased]`
     then the new dated release.
   - Why: without this, `[Unreleased]` accumulates across releases and the
     CHANGELOG stops mapping to git tags. This has happened before — do not
     skip.
7. **Commit** (no signatures, no attribution). The single commit includes
   code, tests, CHANGELOG (with `[Unreleased]` archived if step 6 applied),
   `pyproject.toml`, `README.md` (if badge updated) — and the matching
   agent guide when a documented behavior changed.
8. **If version was bumped**: `git tag v{new_version}` and tell the user to
   run `git push origin main --tags` to push code + tag and trigger the PyPI
   publication.

Example of correct commit message:
```
feat: add product catalog module

- Add Product entity with category FK
- Add ProductService with search method
- Add GraphQL CRUD webservices
```

## For agents working on a consuming project

The same guides ship inside the installed package. Resolve the location with:

```bash
python -c "import lys, pathlib; print(pathlib.Path(lys.__file__).parent / 'agents' / 'guides')"
```

| Topic | Guide |
|-------|-------|
| Apps, modules, loading pipeline | `architecture.md` |
| Creating an app or module | `app-creation.md` |
| Entities | `entity.md` |
| Services | `service.md` |
| GraphQL nodes (incl. override by subclassing) | `node.md` |
| Webservices (queries, mutations, the five decorators) | `webservice.md` |
| Permissions (chain, access levels, row filtering) | `permissions.md` |
| Fixtures | `fixtures.md` |
| Emails, events, notifications | `emails-events.md` |
| Celery tasks | `tasks.md` |
| Real-time signals | `signals.md` |
| AI / chatbot integration | `ai.md` |
| Allowed / forbidden (consolidated rules) | `rules.md` |

Project structure, migrations workflow and verification commands belong to
the consuming project's own AGENTS.md, not here.

## Quality bar — the three-lens review (MANDATORY)

Every piece of code produced, every business rule implemented, every review
delivered is held to **industry-grade standard** — not student-project level.
When writing, reviewing, or discussing an implementation, evaluate through
these three lenses, in this order:

### Lens 1 — Cleanliness (structural quality)

Does the code meet the structural standards of the industry and this framework?

- Framework conventions respected (registration, app_manager access, naming,
  no raw values — see the agent guides).
- Industry code standards: PEP 8, separation of responsibilities,
  single-responsibility functions, no dead code, no copy-paste duplication.
- Architecture: the right concern in the right module, no lateral
  dependencies between apps that should be independent.
- A reviewer seeing this code in a premium product would not flag it.

### Lens 2 — Correctness (industry-grade logic)

Is the logic what the industry expects from a **paid, production-grade
framework** — no more, no less?

- **No simplistic shortcuts**: school-project patterns (hardcoded edge
  cases, single-user assumptions, happy-path-only logic) are unacceptable.
- **No over-engineering either**: speculative abstractions, unnecessary
  configurability, gold-plating are equally unacceptable. The equilibrium
  IS the industry standard.
- **Use existing wheels**: if the language, the standard library, or an
  established package already solves the problem, use it. Reinventing a
  (worse) version of a solved problem is a defect, not a contribution.
- **No atypical behavior**: the framework should behave the way a competent
  practitioner expects it to. Surprising behavior (even if technically
  correct) is a design flaw.
- **If the developer (or agent) is drifting** toward either extreme
  (naive or baroque), the review must say so explicitly.

### Lens 3 — Safety (attack surface AND data integrity)

Is the code safe against both malicious input AND its own failure paths?

- **Attack surface**: the strict industry definition — injection, access
  control, information leakage, authentication/authorization bypass. Every
  input validated; every output that varies by user checked.
- **Data integrity** (the one reviews forget): read the code as a sequence
  of state changes and ask *"if an exception hits HERE, what does the
  database look like?"*
  - Is the ordering of writes correct? (Save A then B, not B then A.)
  - Is there a window where half the data is saved and the other half
    is lost?
  - Does a rollback leave the system in a coherent state?
  - Are concurrent accesses to the same data serialized or guarded?
  - If the answer to any of these is "half the data is gone" or "both
    halves written twice", that is a safety defect, not a style issue.

### Applying the lenses

| Situation | What to do |
|-----------|------------|
| Writing new code | Self-check all three lenses before reporting done |
| Reviewing code | Evaluate through each lens explicitly; a review that only checks cleanliness is incomplete |
| Designing a feature | Discuss correctness (lens 2) first; safety (lens 3) shapes the design; cleanliness (lens 1) shapes the implementation |
| User asks "is this good?" | Answer per-lens, not with a global "yes" or "no" |
