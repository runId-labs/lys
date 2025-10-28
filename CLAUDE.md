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

**Correct approach** - Always use `app_manager` registry:
```python
# In services - use cls.entity_class for your own entity
emailing = session.get(cls.entity_class, emailing_id)

# Get other services by name
email_service = cls.get_service_by_name("emailing")
user_service = app_manager.get_service("user")
```

**NEVER do this** - Direct imports break the architecture:
```python
# WRONG - DO NOT DO THIS
from lys.apps.base.modules.emailing.entities import Emailing
emailing = session.get(Emailing, emailing_id)  # WILL FAIL
```

**Why this is critical**:
- Direct imports bypass the registration system
- Causes SQLAlchemy inspection errors
- Breaks in Celery workers where the app context is different
- Violates the dependency injection pattern of the framework
- Prevents proper entity/service resolution

**Rule**: If you need an entity or service, get it from `app_manager` or use `cls.entity_class`/`cls.get_service_by_name()`. No exceptions.

### GraphQL Integration
- Uses Strawberry GraphQL with FastAPI
- Supports multiple schemas with automatic routing
- Security features: query depth limiting, alias limiting, schema introspection disabled in production

### Authentication & Permissions
- Built-in user authentication system in `user_auth` app
- Role-based and organization-based access control
- Permission checking via `check_permission()` method on entities

## Development Guidelines

### Language and Documentation Standards
- **Project language**: All code, comments, documentation, and commit messages must be in English
- **Communication style**: Use objective, factual language in all documentation and comments
- **No marketing language**: Avoid superlatives, promotional terms, or sales-oriented language
- **Technical precision**: Focus on functionality, behavior, and implementation details rather than subjective assessments

### Code Documentation
- Document what the code does, not how good it is
- Use clear, descriptive names for functions and variables
- Explain complex logic with technical comments, not value judgments
- Focus on usage patterns, parameters, return values, and side effects

### Git and Version Control
- Do not sign commits when creating commits
- Use clear, descriptive commit messages in English
- Follow conventional commit format when applicable