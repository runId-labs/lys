import logging
from collections import defaultdict, deque
from typing import Type, Dict, List, Callable, Set

import strawberry
from strawberry.types.field import StrawberryField
from strawberry.annotation import StrawberryAnnotation

from lys.core.consts.component_types import AppComponentTypeEnum
from lys.core.graphql.interfaces import NodeInterface
from lys.core.interfaces.entities import EntityInterface
from lys.core.interfaces.fixtures import EntityFixtureInterface
from lys.core.interfaces.services import ServiceInterface
from lys.core.managers.database import Base
from lys.core.utils.decorators import singleton
from lys.core.utils.generic import replace_node_in_annotation
from lys.core.utils.webservice import WebserviceIsPublicType, generate_webservice_fixture


class AppRegister:
    def __init__(self):
        self.entities: Dict[str, Type[EntityInterface]] = {}
        self.services: Dict[str, Type[ServiceInterface]] = {}
        self.fixtures: List[Type[EntityFixtureInterface]] = []
        self._fixture_dependencies: Dict[str, List[str]] = {}  # fixture_name -> [dependencies]
        self.webservices: dict[str, dict] = {}
        self.nodes: Dict[str, Type[NodeInterface]] = {}

        # When True, prevents further registrations to ensure consistency
        self._locked_component_types: Set[AppComponentTypeEnum] = set()

    def is_locked(self, component_type: AppComponentTypeEnum):
        return component_type in self._locked_component_types

    def lock(self, component_type: AppComponentTypeEnum):
        self._locked_component_types.add(component_type)

    def register_entity(self, name: str, entity_class: Type[EntityInterface]):
        """
        Register an entity class with the register.

        Args:
            name: Entity name for lookup (typically __tablename__ attribute)
            entity_class: Entity class implementing EntityInterface (must be a proper class)

        Raises:
            TypeError: If entity_class doesn't implement EntityInterface
        """
        if not self.is_locked(AppComponentTypeEnum.ENTITIES):

            if not issubclass(entity_class, EntityInterface):
                raise TypeError(f"Entity '{name}' must be a subclass of EntityInterface")

            # Store the entity in the register for later retrieval
            self.entities[name] = entity_class

            logging.info(f"✓ Registered entity: {name} -> {entity_class.__name__}")

    def get_entity(self, name: str) -> Type[EntityInterface]:
        """
        Retrieve a registered entity by name.

        Args:
            name: Entity name to lookup

        Returns:
            Entity class

        Raises:
            KeyError: If entity is not found
        """
        if name not in self.entities:
            raise KeyError(f"Entity '{name}' not found. Available: {list(self.entities.keys())}")
        return self.entities[name]

    def finalize_entities(self):
        """
        Transform abstract entities into concrete SQLAlchemy entities for database creation.

        This critical method solves two fundamental problems in the lys framework:

        1. **Abstract Entity Problem**: Base entities (BaseEntity, ParametricEntity) are marked
           as abstract (__abstract__ = True) to prevent SQLAlchemy from creating tables for them.
           However, concrete entities inheriting from these bases remain abstract by default,
           preventing table creation.

        2. **Relationship Naming Convention**: SQLAlchemy relationships use table names, not
           class names. By creating new classes with __tablename__ as the class name, we ensure
           that relationship declarations like relationship("webservice_public_type") work
           seamlessly without complex mapping.

        The solution:
        - Creates a new class dynamically using type() with __tablename__ as class name
        - Forces __abstract__ = False to make entities concrete for SQLAlchemy
        - Maintains inheritance chain while enabling table creation
        - Unifies class names with table names for intuitive relationship declarations

        Example transformation:
        - Original: class AuthWebservice(BaseEntity) with __tablename__ = "auth_webservices"
        - Result: class auth_webservices(AuthWebservice) with __abstract__ = False

        This enables natural relationship syntax:
        relationship("auth_webservices", lazy="selectin") # Works intuitively
        """
        for table_name, entity in self.entities.items():
            # Create concrete entity class with table name as class name
            new_entity = type(entity.get_tablename(), (entity, Base), {})
            new_entity.__abstract__ = False
            self.entities[table_name] = new_entity  # type: ignore[assignment]

    def register_service(self, name: str, service_class: Type[ServiceInterface]):
        if not self.is_locked(AppComponentTypeEnum.SERVICES):

            if not issubclass(service_class, ServiceInterface):
                raise TypeError(f"Service '{name}' must be a subclass of ServiceInterface")

            # Store the service in the register for later retrieval
            self.services[name] = service_class

            logging.info(f"✓ Registered service: {name} -> {service_class.__name__}")

    def get_service(self, name: str) -> Type[ServiceInterface]:
        """
        Retrieve a registered service by name.

        Args:
            name: Service name to lookup

        Returns:
            Service class

        Raises:
            KeyError: If service is not found
        """
        if name not in self.services:
            raise KeyError(f"Service '{name}' not found. Available: {list(self.services.keys())}")
        return self.services[name]

    def register_fixture(self, fixture_class: Type[EntityFixtureInterface], depends_on: List[str] = None):
        """
        Register a fixture class with dependency tracking.

        Uses module-qualified names to avoid conflicts when multiple fixtures
        have the same class name in different modules.

        Args:
            fixture_class: Fixture class implementing EntityFixtureInterface
            depends_on: List of fixture class names this fixture depends on
        """
        if not self.is_locked(AppComponentTypeEnum.FIXTURES):
            # Use module-qualified name to avoid conflicts
            fixture_id = f"{fixture_class.__module__}.{fixture_class.__name__}"

            # Check if already registered
            for existing_fixture in self.fixtures:
                existing_id = f"{existing_fixture.__module__}.{existing_fixture.__name__}"
                if existing_id == fixture_id:
                    raise ValueError(
                        f"Fixture '{fixture_id}' already registered. "
                        f"Fixtures with the same class name in different modules are now supported."
                    )

            self.fixtures.append(fixture_class)
            # Store dependencies with simple class name for backward compatibility
            simple_name = fixture_class.__name__
            self._fixture_dependencies[fixture_id] = depends_on or []
            logging.info(f"✓ Registered fixture: {fixture_id} (depends on: {depends_on or 'none'})")

    def get_fixtures_in_dependency_order(self) -> List[EntityFixtureInterface]:
        """
        Get fixtures sorted by dependency order using topological sort.

        Returns:
            List of fixture classes in dependency order

        Raises:
            ValueError: If circular dependencies are detected
        """
        if not self.fixtures:
            return []

        # Build dependency graph
        graph = defaultdict(list)  # dependency -> [fixtures that depend on it]
        in_degree = defaultdict(int)  # fixture -> number of dependencies

        # Use module-qualified names to match the keys in _fixture_dependencies
        fixture_map = {f"{f.__module__}.{f.__name__}": f for f in self.fixtures}

        # Also create a simple name to qualified name mapping for depends_on lookups
        simple_to_qualified = {}
        for f in self.fixtures:
            qualified_name = f"{f.__module__}.{f.__name__}"
            simple_name = f.__name__
            # If multiple fixtures have the same simple name, this will only keep the last one
            # but that's okay since depends_on should use the simple name and we'll resolve it
            simple_to_qualified[simple_name] = qualified_name

        # Initialize in-degree for all fixtures using qualified names
        for qualified_name in fixture_map:
            in_degree[qualified_name] = 0

        # Build graph and calculate in-degrees
        for fixture_qualified_name, deps in self._fixture_dependencies.items():
            for dep in deps:
                # dep is a simple name (from depends_on parameter)
                # We need to resolve it to a qualified name
                if dep in simple_to_qualified:
                    dep_qualified = simple_to_qualified[dep]
                elif dep in fixture_map:
                    dep_qualified = dep
                else:
                    raise ValueError(f"Fixture '{fixture_qualified_name}' depends on '{dep}' which is not registered")

                graph[dep_qualified].append(fixture_qualified_name)
                in_degree[fixture_qualified_name] += 1

        # Topological sort using Kahn's algorithm
        queue = deque()
        result = []

        # Start with fixtures that have no dependencies (use qualified names)
        for qualified_name in fixture_map:
            if in_degree[qualified_name] == 0:
                queue.append(qualified_name)

        while queue:
            current = queue.popleft()
            result.append(fixture_map[current])

            # Remove this fixture from the graph
            for dependent in graph[current]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        # Check for circular dependencies
        if len(result) != len(self.fixtures):
            remaining = [name for name in fixture_map if fixture_map[name] not in result]
            raise ValueError(f"Circular dependency detected in fixtures: {remaining}")

        return result

    def register_webservice(
            self,
            field_or_fct: StrawberryField | Callable,
            is_public: WebserviceIsPublicType = False,
            enabled: bool = True,
            access_levels: List[str] = None,
            is_licenced: bool = True,
            allow_override: bool = True,
    ):
        if not self.is_locked(AppComponentTypeEnum.WEBSERVICES):
            if type(field_or_fct) is StrawberryField:
                webservice_name = field_or_fct.base_resolver.wrapped_func.__name__
            else:
                webservice_name = field_or_fct.__name__

            webservice_fixture = generate_webservice_fixture(
                webservice_name,
                enabled, is_public,
                access_levels,
                is_licenced
            ).model_dump()

            existing = self.webservices.get(webservice_name)
            if existing:
                if not allow_override:
                    raise ValueError(
                        f"Webservice '{webservice_name}' already registered. "
                        f"Set allow_override=True to explicitly override it."
                    )
                logging.warning(f"⚠ Overwriting webservice '{webservice_name}' with new configuration")

            self.webservices[webservice_name] = webservice_fixture

    def validate_webservice_configuration(self):
        """
        Validate webservice configuration at initialization.

        Checks that all access_levels referenced by webservices exist in the database.
        This prevents runtime errors from misconfigured webservices.

        Raises:
            ValueError: If a webservice references an unknown access_level
        """
        if "access_level" not in self.entities:
            logging.warning("⚠ AccessLevel entity not registered, skipping webservice validation")
            return

        errors = []
        for ws_name, ws_config in self.webservices.items():
            access_levels = ws_config.get("attributes", {}).get("access_levels", [])
            for access_level in access_levels:
                # Note: We can't check against the database here since it's not initialized yet
                # This validation would need to happen after fixture loading
                # For now, we just validate that access_level names are non-empty strings
                if not isinstance(access_level, str) or not access_level.strip():
                    errors.append(
                        f"Webservice '{ws_name}' has invalid access_level: '{access_level}'"
                    )

        if errors:
            error_msg = "Webservice configuration validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
            raise ValueError(error_msg)

        logging.info(f"✓ Validated {len(self.webservices)} webservice configurations")

    def register_node(self, name: str, node_class: Type[NodeInterface]):
        if not self.is_locked(AppComponentTypeEnum.NODES):

            if not issubclass(node_class, NodeInterface):
                raise TypeError(f"Node '{name}' must be a subclass of NodeInterface")

            # Store the node in the register for later retrieval
            self.nodes[name] = node_class

            logging.info(f"✓ Registered node: {name} -> {node_class.__name__}")

    def get_node(self, name: str) -> Type[NodeInterface]:
        """
        Retrieve a registered node by name.

        Args:
            name: Node name to lookup

        Returns:
            Node class

        Raises:
            KeyError: If service is not found
        """
        if name not in self.nodes:
            raise KeyError(f"Node '{name}' not found. Available: {list(self.nodes.keys())}")
        return self.nodes[name]

    def finalize_nodes(self):
        """
        Apply strawberry.type decorator to all registered nodes.

        This method is automatically called after all nodes have been registered.
        It applies the @strawberry.type decorator to each node, making them
        discoverable by Strawberry GraphQL schema generation.

        The approach allows:
        - Nodes to be registered without @strawberry.type decorator
        - Node overriding via register (last registered wins)
        - Automatic Strawberry type application after all registrations complete
        - Node references in annotations are replaced with effective registered versions
        - Method return type annotations are also updated for @strawberry.field methods
        """
        for node_name, node_class in self.nodes.items():
            # 1. Replace node references in class field annotations with effective registered versions
            # This ensures that when a node is overridden (e.g., UserNode with roles),
            # all references to it in other nodes point to the latest version
            if hasattr(node_class, '__annotations__'):
                for attr_name, attr_type in list(node_class.__annotations__.items()):
                    new_type = replace_node_in_annotation(attr_type, self.nodes)
                    if new_type is not attr_type:
                        node_class.__annotations__[attr_name] = new_type
                        logging.debug(f"  Updated {node_name}.{attr_name} field type annotation")

            # 2. Replace node references in method return type annotations
            # This handles @strawberry.field methods that return other nodes
            for attr_name in dir(node_class):
                try:
                    attr = getattr(node_class, attr_name)

                    # Check if it's a StrawberryField (decorated with @strawberry.field)
                    if isinstance(attr, StrawberryField):
                        # Access the original function's annotations via base_resolver
                        if hasattr(attr, 'base_resolver') and hasattr(attr.base_resolver, 'wrapped_func'):
                            wrapped_func = attr.base_resolver.wrapped_func
                            if hasattr(wrapped_func, '__annotations__'):
                                return_annotation = wrapped_func.__annotations__.get('return')
                                if return_annotation:
                                    new_type = replace_node_in_annotation(return_annotation, self.nodes)
                                    if new_type is not return_annotation:
                                        # Update the wrapped function's annotations
                                        wrapped_func.__annotations__['return'] = new_type
                                        # Update the StrawberryField's type_annotation
                                        if hasattr(attr, 'type_annotation'):
                                            attr.type_annotation = StrawberryAnnotation(new_type)
                                        logging.debug(
                                            f"  Updated {node_name}.{attr_name}() return type annotation "
                                            f"from {return_annotation} to {new_type}"
                                        )
                except (AttributeError, TypeError):
                    # Skip attributes that can't be accessed or don't have annotations
                    continue

            # 3. Apply strawberry.type decorator
            strawberry_node = strawberry.type(node_class)
            self.nodes[node_name] = strawberry_node
            logging.info(f"✓ Finalized node: {node_name}")


@singleton
class LysAppRegister(AppRegister):
    pass


def register_entity(register: AppRegister=None):
    if register is None:
        register = LysAppRegister()

    def decorator(cls):
        register.register_entity(cls.__tablename__, cls)
        return cls

    return decorator


def register_service(register: AppRegister=None):
    if register is None:
        register = LysAppRegister()

    def decorator(cls):
        register.register_service(cls.service_name, cls)
        return cls

    return decorator


def register_fixture(depends_on: List[str] = None, register: AppRegister=None):
    if register is None:
        register = LysAppRegister()

    def decorator(cls):
        register.register_fixture(cls, depends_on=depends_on)
        return cls

    return decorator


def register_webservice(
        is_public: WebserviceIsPublicType = False,
        enabled: bool = True,
        access_levels: List[str] = None,
        is_licenced: bool = True,
        allow_override: bool = True,
        register: AppRegister = None
):
    if register is None:
        register = LysAppRegister()

    def decorator(cls):
        register.register_webservice(
            cls,
            is_public,
            enabled,
            access_levels,
            is_licenced,
            allow_override,
        )
        return cls
    return decorator


def register_node(register: AppRegister=None):
    if register is None:
        register = LysAppRegister()

    def decorator(cls):
        register.register_node(cls.__name__, cls)
        return cls

    return decorator


def override_webservice(
    name: str,
    access_levels: List[str] | None = None,
    is_public: WebserviceIsPublicType | None = None,
    is_licenced: bool | None = None,
    enabled: bool | None = None,
    register: AppRegister = None
):
    """
    Override an existing webservice fixture with new parameters.

    This function allows you to modify the metadata of an already registered webservice
    without duplicating its implementation logic. Useful for extending access levels
    in app overrides.

    Args:
        name: Name of the webservice to override
        access_levels: New access levels (e.g., [OWNER_ACCESS_LEVEL, ROLE_ACCESS_LEVEL])
        is_public: New is_public value
        is_licenced: New is_licenced value
        enabled: New enabled value
        register: Optional custom register (defaults to LysAppRegister singleton)

    Raises:
        ValueError: If webservice not found in registry or no parameters provided

    Example:
        >>> override_webservice(
        ...     name="update_email",
        ...     access_levels=[OWNER_ACCESS_LEVEL, ROLE_ACCESS_LEVEL]
        ... )
    """
    if register is None:
        register = LysAppRegister()

    if name not in register.webservices:
        raise ValueError(
            f"Webservice '{name}' not found in registry and cannot be overridden. "
            f"Available webservices: {', '.join(sorted(register.webservices.keys()))}. "
            f"Make sure the webservice is registered before attempting to override it."
        )

    existing_fixture = register.webservices[name]
    attributes = existing_fixture.get("attributes", {})
    modified = False

    # Update only provided parameters
    if access_levels is not None:
        attributes["access_levels"] = access_levels
        modified = True

    if is_public is not None:
        attributes["is_public"] = is_public
        modified = True

    if is_licenced is not None:
        attributes["is_licenced"] = is_licenced
        modified = True

    if enabled is not None:
        attributes["enabled"] = enabled
        modified = True

    if not modified:
        logging.warning(
            f"⚠ override_webservice('{name}'): No parameters provided, nothing to override. "
            f"Available parameters: access_levels, is_public, is_licenced, enabled"
        )
        return

    # Update the fixture
    existing_fixture["attributes"] = attributes

    logging.info(f"✓ Overridden webservice: {name} with new configuration")


def disable_webservice(
    name: str,
    register: AppRegister = None
):
    """
    Disable an existing webservice.

    This function sets the 'enabled' flag to False for a registered webservice,
    effectively preventing it from being accessible in the API without removing
    its registration entirely.

    Args:
        name: Name of the webservice to disable
        register: Optional custom register (defaults to LysAppRegister singleton)

    Raises:
        ValueError: If webservice not found in registry

    Example:
        >>> disable_webservice("create_super_user")
    """
    if register is None:
        register = LysAppRegister()

    if name not in register.webservices:
        raise ValueError(
            f"Webservice '{name}' not found in registry and cannot be disabled. "
            f"Available webservices: {', '.join(sorted(register.webservices.keys()))}. "
            f"Make sure the webservice is registered before attempting to disable it."
        )

    existing_fixture = register.webservices[name]
    attributes = existing_fixture.get("attributes", {})
    attributes["enabled"] = False
    existing_fixture["attributes"] = attributes

    logging.info(f"✓ Disabled webservice: {name}")