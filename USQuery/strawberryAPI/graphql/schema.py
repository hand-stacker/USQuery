import strawberry

from gqlauth.core.middlewares import JwtSchema
from strawberry.extensions import QueryDepthLimiter
from strawberry.schema.config import StrawberryConfig
from .queries import Query
from .mutations import Mutation

schema = JwtSchema(query=Query, mutation=Mutation,
        extensions=[QueryDepthLimiter(max_depth=5)],
        config=StrawberryConfig(batching_config={"max_operations": 3}))