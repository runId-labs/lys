# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Lys is a FastAPI library providing a Django-inspired modular framework for building GraphQL APIs with SQLAlchemy. It uses a component-based architecture with automatic registration, authentication, and permission systems.

## Codebase Map

### Core: `src/lys/core/`

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

### Apps: `src/lys/apps/`

| App | Modules | Extra Files |
|-----|---------|-------------|
| `base` | one_time_token, language, job, emailing, log, access_level, webservice | permissions, middlewares, consts, tasks |
| `user_auth` | access_level, emailing, notification, event, webservice, user, auth | permissions, middlewares, consts, errors, utils |
| `user_role` | access_level, auth, notification, role, user, webservice | consts, errors, models |
| `organization` | access_level, auth, user, client, notification, role, webservice | abstracts, permissions, consts |
| `file_management` | file_import, stored_file | — |
| `ai` | core, conversation, text_improvement | tasks |
| `licensing` | application, rule, plan, auth, checker, client, mollie, role, subscription, user, event, emailing, webservice | registries, tasks, consts, errors |

Each module lives at `src/lys/apps/{app}/modules/{module}/` and can contain: `entities.py`, `services.py`, `fixtures.py`, `nodes.py`, `webservices.py`.

## Registry Names

Names used with `app_manager.get_entity(name)` and `app_manager.get_service(name)` (= `__tablename__`):

- **base**: `one_time_token_status`, `one_time_token_type`, `language`, `access_level`, `emailing_status`, `emailing_type`, `emailing`, `job_status`, `job`, `cron_job_execution`, `migration_job_execution`, `log`, `webservice`
- **user_auth**: `user_status`, `gender`, `login_attempt_status`, `webservice_public_type`, `notification_type`, `user`, `user_private_data`, `user_refresh_token`, `user_one_time_token`, `user_emailing`, `user_email_address`, `user_audit_log_type`, `user_audit_log`, `user_login_attempt`, `user_event_preference`, `notification_batch`, `notification`
- **user_role**: `role`, `role_webservice`
- **organization**: `client`, `client_user_role`
- **file_management**: `stored_file_type`, `stored_file`, `file_import_type`, `file_import_status`, `file_import`
- **ai**: `ai_conversations`, `ai_messages`, `ai_message_feedback`
- **licensing**: `license_application`, `license_rule`, `license_plan`, `license_plan_version`, `license_plan_version_rule`, `subscription`

## Common Imports

### Registration Decorators
```python
from lys.core.registries import register_entity, register_service, register_fixture, register_node
from lys.core.registries import override_webservice, disable_webservice
from lys.core.graphql.registries import register_query, register_mutation
```

### Base Classes
```python
from lys.core.entities import Entity, ParametricEntity
from lys.core.services import EntityService
from lys.core.fixtures import EntityFixtures
from lys.core.graphql.nodes import EntityNode, ServiceNode, parametric_node
from lys.core.graphql.types import Query, Mutation
```

### GraphQL Decorators
```python
from lys.core.graphql.getter import lys_getter
from lys.core.graphql.connection import lys_connection
from lys.core.graphql.create import lys_creation
from lys.core.graphql.edit import lys_edition
from lys.core.graphql.delete import lys_delete
```

### Access Level Constants
```python
from lys.core.consts.webservices import CONNECTED_ACCESS_LEVEL, OWNER_ACCESS_LEVEL, INTERNAL_SERVICE_ACCESS_LEVEL
from lys.apps.user_role.consts import ROLE_ACCESS_LEVEL
from lys.apps.organization.consts import ORGANIZATION_ROLE_ACCESS_LEVEL
```

## Architecture Rules

### Entity UUID Fields — MANDATORY

All soft FK fields in `Entity` subclasses MUST use `Uuid(as_uuid=False)`:

```python
client_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), nullable=False, comment="Client reference (soft FK)")
```

This provides database-level UUID validation. `as_uuid=False` keeps the value as a string for JSON serialization. **Exception**: `ParametricEntity` subclasses use plain string IDs, not UUIDs.

### Accessing Entities and Services — MANDATORY

ALL entities and services MUST be accessed through `app_manager`. Direct imports WILL cause bugs (breaks registration, SQLAlchemy inspection, Celery workers).

```python
# CORRECT
entity = cls.app_manager.get_entity("client")
service = cls.app_manager.get_service("emailing")
own_entity = cls.entity_class  # shortcut in EntityService

# WRONG — DO NOT DO THIS
from lys.apps.organization.modules.client.entities import Client  # WILL FAIL
```

### Override Patterns

- **Last-registered-wins**: When two apps register the same component name, the later registration wins. This is how business apps extend built-in Lys apps.
- **`override_webservice(name, ...)`**: Modify existing webservice metadata (access_levels, is_public, is_licenced, enabled) without recreating the implementation.
- **`disable_webservice(name)`**: Disable a webservice by setting `enabled=False`.

## Development Commands

```bash
pip install -e .                                    # Install

pytest tests/unit/                                  # Unit tests only
pytest tests/integration/ --forked                  # Integration tests only

# Combined coverage (ALWAYS use this method — separate processes required)
pytest tests/unit/ --cov=src/lys --cov-report=
pytest tests/integration/ --forked --cov=src/lys --cov-append --cov-report=term-missing
```

Unit and integration tests cannot run in the same pytest process due to SQLAlchemy registry singleton isolation. Use `--cov-append` to accumulate coverage across both runs.

Test file structure: `tests/{unit,integration}/apps/{app_name}/test_{module}_{component}.py`

## Documentation Reference

Consult these docs by task:

- **Building permissions / access control** → `docs/FRS/jwt_permissions.md`, `docs/guides/permissions.md`
- **Authentication flows (login, logout, tokens)** → `docs/FRS/auth.md`
- **Service-to-service communication** → `docs/FRS/internal_service_communication.md`
- **Webservice configuration and access levels** → `docs/FRS/webservice_management.md`
- **Creating a new app** → `docs/guides/creating-an-app.md`
- **Defining entities and services** → `docs/guides/entities-and-services.md`
- **Building GraphQL queries/mutations** → `docs/guides/graphql-api.md`
- **Implementation notes and migrations** → `docs/todos/`

## Development Guidelines

### Language and Documentation Standards
- **Project language**: All code, comments, documentation, and commit messages must be in English
- **Communication style**: Use objective, factual language in all documentation and comments
- **No marketing language**: Avoid superlatives, promotional terms, or sales-oriented language
- **Technical precision**: Focus on functionality, behavior, and implementation details rather than subjective assessments

### Code Style Standards
- **PEP 8 Compliance**: All Python code MUST follow PEP 8 style guidelines
- **Line length**: Maximum 120 characters per line (project standard, extended from PEP 8's 79)
- **Indentation**: 4 spaces (no tabs)
- **Imports**:
  - Group imports in order: standard library, third-party, local application
  - Absolute imports preferred over relative imports
  - One import per line (except for `from x import a, b`)
  - All imports at the top of the file — **inline imports only when strictly necessary** (circular imports, conditional imports). Prefer top-level imports always.
- **Naming conventions**:
  - `snake_case` for functions, variables, and module names
  - `PascalCase` for class names
  - `UPPER_CASE` for constants
- **Whitespace**:
  - Two blank lines between top-level functions and classes
  - One blank line between methods in a class
  - No trailing whitespace
- **String quotes**: Use double quotes `"` for strings (project convention)
- **Type hints**: Use type hints for function signatures and class attributes where applicable

### Code Documentation
- Document what the code does, not how good it is
- Use clear, descriptive names for functions and variables
- Explain complex logic with technical comments, not value judgments
- Focus on usage patterns, parameters, return values, and side effects
- Use docstrings for all public modules, functions, classes, and methods (Google/NumPy style preferred)

## Git & Commit Workflow

### Git Rules
- **CRITICAL**: Do NOT sign commits — no GPG signatures, no Co-Authored-By lines, no Generated with Claude Code footers
- Do NOT add any attribution, signature, or authorship metadata to commit messages
- Commit messages should contain ONLY the conventional commit format with description
- **IMPORTANT**: NEVER commit changes unless explicitly asked by the user with "commit" command
- Do NOT proactively stage files or create commits — wait for explicit user instruction

### Commit Process

When the user validates code and asks to commit:

1. **Write/update tests** covering the changes (unit, integration, or e2e). Verify they pass.
2. **Determine commit type** using conventional commit format:
   ```
   type(scope): description

   - Detail bullet points
   ```
3. **Auto-detect version bump** from commit type and update `pyproject.toml` line 3:
   - `fix:` → patch bump (e.g., 0.1.0 → 0.1.1)
   - `feat:` → minor bump (e.g., 0.1.0 → 0.2.0)
   - `feat!:` or `BREAKING CHANGE` → major bump (e.g., 0.1.0 → 1.0.0)
   - `refactor:`, `docs:`, `chore:`, `test:`, `style:` → no version bump
4. **Commit** with conventional commit message (no signatures, no attribution).

Example of correct commit message:
```
feat: add product catalog module

- Add Product entity with category FK
- Add ProductService with search method
- Add GraphQL CRUD webservices
```
