from typing import Optional

import graphene
import strawberry
from strawberry import field
from strawberry.relay import PageInfo
from strawberry.types.object_type import type as strawberry_type

from lys.core.graphql.interfaces import QueryInterface, MutationInterface, SubscriptionInterface


@strawberry_type(description="Information to aid in pagination.")
class LysPageInfo(PageInfo):
    total_count: Optional[int] = field(
        description="Without pagination object count",
    )


class Query(QueryInterface, graphene.ObjectType):
    node = graphene.relay.Node.Field()


class DefaultQuery(Query):
    @strawberry.field(description="ping query")
    def ping(self) -> str:
        return "pong"


class Mutation(MutationInterface):
    pass


class Subscription(SubscriptionInterface):
    pass
