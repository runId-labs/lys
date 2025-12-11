# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Lys is a FastAPI library that provides a Django-inspired modular framework for building GraphQL APIs with SQLAlchemy. It features a component-based architecture with automatic registration, authentication, and permission systems.

## Architecture

### Core Structure
- `src/lys/core/` - Core framework components
- `src/lys/apps/` - Application modules (base, organization, user_auth, user_role)

### Component-Based System
The framework uses a modular component system with these types:
- **entities** - SQLAlchemy models/database entities
- **services** - Business logic and data operations
- **fixtures** - Database seeding and initialization
- **nodes** - GraphQL query/mutation resolvers
- **webservices** - REST API endpoints

### App Structure
Apps follow this pattern:
```
src/lys/apps/{app_name}/
├── modules/
│   └── {module_name}/
│       ├── entities.py
│       ├── services.py
│       ├── fixtures.py
│       ├── nodes.py
│       └── webservices.py
└── __init__.py (with __submodules__ list)
```

### Key Classes
- `AppManager` - Main application orchestrator that loads components
- `Entity`/`ParametricEntity` - Base classes for database models
- `LysAppSettings` - Configuration management with environment-based settings
- Component registries automatically discover and register app components

## Development Commands

### Installation
```bash
pip install -e .
```

### Testing
```bash
# Run tests (pytest is in dev dependencies)
pytest

# Run tests with coverage
pytest --cov=src/lys
```

### Database Operations
The framework uses SQLAlchemy async with automatic database initialization via `DatabaseManager`.

### Development Environment
Set environment via `LysAppSettings.env`:
- `DEV` - Development mode with debug enabled
- `DEMO` - Demo environment
- `PREPROD` - Pre-production
- `PROD` - Production mode with security hardening

## Key Patterns

### Adding New Apps
1. Create app directory under `src/lys/apps/`
2. Add modules with component files (entities.py, services.py, etc.)
3. Register app in settings: `settings.add_app("lys.apps.your_app")`

### Component Registration
Components are automatically discovered and registered when modules are imported. Use decorators like `@register_entity`, `@register_service` to register components.

### Accessing Entities and Services - CRITICAL ARCHITECTURE RULE

**MANDATORY**: ALL entities and services MUST be accessed through `app_manager`. Direct imports of entities or services WILL cause bugs and failures.

**Standard Pattern** - Use `app_manager.get_entity()` and `app_manager.get_service()`:
```python
# In services/fixtures/nodes - access via app_manager
class UserService(EntityService[User]):
    async def example(cls, session: AsyncSession):
        # For the current service's entity - use cls.entity_class shortcut
        user = await session.get(cls.entity_class, user_id)

        # For other entities - use app_manager
        org_entity = cls.app_manager.get_entity("organizations")
        org = await session.get(org_entity, org_id)

        # For other services - use app_manager
        email_service = cls.app_manager.get_service("emailing")
        await email_service.send_welcome_email(user, session)
```

**NEVER do this** - Direct imports break the architecture:
```python
# WRONG - DO NOT DO THIS
from lys.apps.base.modules.emailing.entities import Emailing
emailing = await session.get(Emailing, emailing_id)  # WILL FAIL
```

**Why this is critical**:
- Direct imports bypass the registration system
- Causes SQLAlchemy inspection errors
- Breaks in Celery workers where the app context is different
- Violates the dependency injection pattern of the framework
- Prevents proper entity/service resolution

**The ONE correct pattern**:
- Use `app_manager.get_entity("name")` for entities
- Use `app_manager.get_service("name")` for services
- Use `cls.entity_class` in EntityService for the current entity (convenience shortcut)

### GraphQL Integration
- Uses Strawberry GraphQL with FastAPI
- Supports multiple schemas with automatic routing
- Security features: query depth limiting, alias limiting, schema introspection disabled in production

### Authentication & Permissions
- Built-in user authentication system in `user_auth` app
- JWT-based stateless permission checking for microservices architecture
- Role-based and organization-based access control
- Permission checking via JWT claims (no database queries on business servers)

## Documentation Reference

For detailed functional specifications, consult the `docs/FRS/` directory:

- **`docs/FRS/jwt_permissions.md`**: Complete JWT permission system documentation
  - Permission classes: AnonymousPermission, JWTPermission, OrganizationPermission
  - JWT claims structure (webservices, organizations)
  - AuthService inheritance chain for claims generation
  - Row-level filtering (OWNER, ORGANIZATION_ROLE)
  - Troubleshooting guide

- **`docs/FRS/auth.md`**: Authentication system
  - Login/logout flows, token refresh, rate limiting

- **`docs/FRS/webservice_management.md`**: Webservice configuration
  - Access levels, overrides, best practices

- **`docs/todos/`**: Implementation notes and migration guides

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
  - All imports at the top of the file (no imports inside functions unless absolutely necessary)
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

### Git and Version Control
- **CRITICAL**: Do NOT sign commits - no GPG signatures, no Co-Authored-By lines, no Generated with Claude Code footers
- Do NOT add any attribution, signature, or authorship metadata to commit messages
- Commit messages should contain ONLY the conventional commit format with description
- Use clear, descriptive commit messages in English
- Follow conventional commit format when applicable
- **IMPORTANT**: NEVER commit changes unless explicitly asked by the user with "commit" command
- Do NOT proactively stage files or create commits - wait for explicit user instruction

Example of correct commit message:
```
refactor: implement fixture loading strategy pattern

- Add FixtureLoadingStrategy base class
- Extract parametric and business loading logic into separate strategies
- Update EntityFixtures to use strategy pattern
```

Example of INCORRECT commit message (DO NOT DO THIS):
```
refactor: implement fixture loading strategy pattern

- Add FixtureLoadingStrategy base class

🤖 Generated with [Claude Code](https://claude.com/claude-code)
Co-Authored-By: Claude <noreply@anthropic.com>
```