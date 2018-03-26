"""Setup sanic, redis and postgres"""

import logging
import aioredis
import asyncpg
from sanic import Sanic
from sanic.response import text

app = Sanic(__name__, configure_logging=False)
from . import config
from .storage import drivers
from .routes.auth import bp as authbp

logger = logging.getLogger(__name__)


async def setup_postgres(_app, loop):
    """Connect to postgres and expose the connection object"""
    postgres = await asyncpg.connect(
        dsn=config.postgres.DSN,
        host=config.postgres.HOST,
        port=config.postgres.PORT,
        user=config.postgres.USER,
        database=config.postgres.DATABASE,
        password=config.postgres.PASSWORD,
        loop=loop
    )
    drivers.RDB = database.Postgres(postgres)
    logger.info("Connection to postgres established.")


async def setup_redis(_app, loop):
    """Connect to redis and expose the connection object"""
    if config.redis.DSN is not None:
        redisconn = await aioredis.create_pool(
            address=config.redis.DSN,
            loop=loop
        )
    else:
        redisconn = await aioredis.create_pool(
            address=(config.redis.HOST, config.redis.PORT),
            db=config.redis.DATABASE,
            password=config.redis.PASSWORD,
            loop=loop
        )
    drivers.KVS = database.Redis(redisconn)
    logger.info("Connection to redis established.")


# Register remote or local databases
if config.webapi.PRODUCTION:
    app.listener("before_server_start")(setup_postgres)
    app.listener("before_server_start")(setup_redis)
else:
    drivers.RDB = database.SQLite()
    drivers.KVS = database.InMemory()

@app.routes("/status")
await def server_status(_req):
    return text("Server running\n")

# Register routes
app.blueprint(authbp, url_prefix="/v1/auth")
