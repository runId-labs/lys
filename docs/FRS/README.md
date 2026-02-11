# Functional Requirements Specification (FRS)

This directory contains functional requirement specifications for the Lys framework components.

## About FRS

**FRS** (Functional Requirements Specification) documents describe the functional behavior and business logic of system components from a user and business perspective. These documents complement technical documentation by focusing on the "what" and "why" rather than the "how".

**French equivalent**: CdCF (Cahier des Charges Fonctionnel)

## Document Structure

Each FRS document follows this structure:

1. **Overview**: High-level description of the feature
2. **Key Concepts**: Core concepts and terminology
3. **Permission/Data Flow**: Step-by-step description of business logic
4. **Database Schema**: Entity relationships and data model
5. **Use Cases**: Real-world scenarios and examples
6. **Security Considerations**: Access control and data protection
7. **Performance Optimization**: Performance considerations and solutions
8. **API Reference**: Interface documentation for developers
9. **Configuration**: Setup and configuration instructions
10. **Extension Points**: How to extend and customize
11. **Testing Recommendations**: Test scenarios and strategies
12. **Troubleshooting**: Common issues and solutions
13. **Future Enhancements**: Planned improvements

## Available Documents

- **[auth.md](./auth.md)**: Authentication System
  - JWT token management
  - Login and logout flows
  - Rate limiting and security
  - Token refresh mechanism

- **[jwt_permissions.md](./jwt_permissions.md)**: JWT-Based Permission System
  - Stateless permission checking for microservices
  - Permission classes: AnonymousPermission, JWTPermission, OrganizationPermission
  - JWT claims structure (webservices, organizations)
  - AuthService inheritance chain for claims generation
  - Organization-based multi-tenant access control
  - Row-level filtering (OWNER, ORGANIZATION_ROLE)
  - License verification integration
  - Migration guide from database-based permissions

- **[webservice_management.md](./webservice_management.md)**: Webservice Management System
  - Webservice creation and registration
  - Metadata-only overrides (recommended)
  - Full implementation overrides
  - Webservice disabling
  - Best practices and patterns

- **[emails_and_notifications.md](./emails_and_notifications.md)**: Emails and Notifications
  - Unified event system (trigger_event Celery task)
  - Critical vs batch email dispatch
  - Recipient resolution (base, role-based, organization-scoped)
  - Email templates with Jinja2 inheritance
  - Notification dispatch via Redis pub/sub
  - User preferences and blocked channels
  - Database schema and entity relationships

## How to Use These Documents

### For Product Owners and Business Analysts

FRS documents help you:
- Understand system capabilities and limitations
- Validate business requirements
- Define acceptance criteria
- Communicate with technical teams

### For Developers

FRS documents provide:
- Context for technical implementation
- Use cases for testing
- Integration examples
- Extension guidelines

### For QA Engineers

FRS documents offer:
- Test scenarios and edge cases
- Expected behavior descriptions
- Security considerations
- Troubleshooting guides

## Contributing

When adding new features to the Lys framework:

1. **Create an FRS document** describing the functional requirements
2. **Use the existing documents as templates** for consistency
3. **Include diagrams and examples** to illustrate complex flows
4. **Add troubleshooting sections** based on common issues
5. **Update the README** to list the new document

## Related Documentation

- **[ADVANCED_PATTERNS.md](../ADVANCED_PATTERNS.md)**: Technical patterns and implementation details
- **[CLAUDE.md](../../CLAUDE.md)**: Development guidelines and architecture overview
- **Code documentation**: Inline docstrings and type hints in source files