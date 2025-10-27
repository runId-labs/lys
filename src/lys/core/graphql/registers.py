from lys.core.graphql.interfaces import QueryInterface, MutationInterface, SubscriptionInterface
from lys.core.utils.decorators import singleton


class GraphqlRegister:
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
class LysGraphqlRegister(GraphqlRegister):
    pass


def register_query(schema_name, register:GraphqlRegister=None):
    if register is None:
        register = LysGraphqlRegister()

    def decorator(cls: type[QueryInterface]):
        register.register_query(schema_name, cls)

    return decorator


def register_mutation(schema_name, register:GraphqlRegister=None):
    if register is None:
        register = LysGraphqlRegister()

    def decorator(cls: type[MutationInterface]):
        register.register_mutation(schema_name, cls)

    return decorator


def register_subscription(schema_name, register:GraphqlRegister=None):
    if register is None:
        register = LysGraphqlRegister()

    def decorator(cls: type[SubscriptionInterface]):
        register.register_subscription(schema_name, cls)

    return decorator