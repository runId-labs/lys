from lys.core.graphql.interfaces import QueryInterface, MutationInterface, SubscriptionInterface
from lys.core.utils.decorators import singleton
from lys.core.configs import settings


class GraphqlRegistry:
    def __init__(self):
        self.queries: dict[str, list[type[QueryInterface]]] = {}
        self.mutations: dict[str, list[type[MutationInterface]]] = {}
        self.subscriptions: dict[str, list[type[SubscriptionInterface]]] = {}

    def register_query(self, schema_name, cls:type[QueryInterface]):
        if schema_name not in self.queries.keys():
            self.queries[schema_name] = []
        self.queries[schema_name].append(cls)

    def register_mutation(self, schema_name, cls: type[MutationInterface]):
        if schema_name not in self.mutations.keys():
            self.mutations[schema_name] = []
        self.mutations[schema_name].append(cls)

    def register_subscription(self, schema_name, cls: type[SubscriptionInterface]):
        if schema_name not in self.subscriptions.keys():
            self.subscriptions[schema_name] = []
        self.subscriptions[schema_name].append(cls)

    @property
    def is_empty(self):
        return len(self.queries.keys()) == 0 and len(self.mutations.keys()) == 0 \
            and len(self.subscriptions.keys()) == 0


@singleton
class LysGraphqlRegistry(GraphqlRegistry):
    pass


def register_query(register: GraphqlRegistry = None):
    """
    Register a GraphQL query class to the schema.

    The schema name is automatically retrieved from settings.graphql_schema_name.
    The class name must end with 'Query' (e.g., UserQuery, WebserviceQuery).

    Args:
        register: Optional GraphqlRegistry instance. If None, uses LysGraphqlRegistry singleton.

    Returns:
        Decorator function that registers the query class.

    Raises:
        ValueError: If class name doesn't end with 'Query'.
    """
    if register is None:
        register = LysGraphqlRegistry()

    def decorator(cls: type[QueryInterface]):
        if not cls.__name__.endswith("Query"):
            raise ValueError(
                f"Query class '{cls.__name__}' must end with 'Query' "
                f"(e.g., '{cls.__name__}Query'). This convention is required for "
                f"automatic operation_type detection in webservice registration."
            )
        register.register_query(settings.graphql_schema_name, cls)
        return cls

    return decorator


def register_mutation(register: GraphqlRegistry = None):
    """
    Register a GraphQL mutation class to the schema.

    The schema name is automatically retrieved from settings.graphql_schema_name.
    The class name must end with 'Mutation' (e.g., UserMutation, WebserviceMutation).

    Args:
        register: Optional GraphqlRegistry instance. If None, uses LysGraphqlRegistry singleton.

    Returns:
        Decorator function that registers the mutation class.

    Raises:
        ValueError: If class name doesn't end with 'Mutation'.
    """
    if register is None:
        register = LysGraphqlRegistry()

    def decorator(cls: type[MutationInterface]):
        if not cls.__name__.endswith("Mutation"):
            raise ValueError(
                f"Mutation class '{cls.__name__}' must end with 'Mutation' "
                f"(e.g., '{cls.__name__}Mutation'). This convention is required for "
                f"automatic operation_type detection in webservice registration."
            )
        register.register_mutation(settings.graphql_schema_name, cls)
        return cls

    return decorator


def register_subscription(register: GraphqlRegistry = None):
    """
    Register a GraphQL subscription class to the schema.

    The schema name is automatically retrieved from settings.graphql_schema_name.

    Args:
        register: Optional GraphqlRegistry instance. If None, uses LysGraphqlRegistry singleton.

    Returns:
        Decorator function that registers the subscription class.
    """
    if register is None:
        register = LysGraphqlRegistry()

    def decorator(cls: type[SubscriptionInterface]):
        register.register_subscription(settings.graphql_schema_name, cls)
        return cls

    return decorator