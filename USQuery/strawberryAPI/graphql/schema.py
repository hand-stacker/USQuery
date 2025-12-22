import strawberry
from strawberry.extensions import QueryDepthLimiter
from strawberry.schema.config import StrawberryConfig
from .queries import Query

schema = strawberry.Schema(query=Query,
        extensions=[QueryDepthLimiter(max_depth=5)],
        config=StrawberryConfig(batching_config={"max_operations": 3}))