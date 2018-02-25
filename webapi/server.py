"""Setup sanic, redis and postgres"""

import logging
from asyncio import sleep
from typing import Optional
import aioredis
import asyncpg
from sanic import Sanic

app = Sanic(__name__, configure_logging=False)
from . import config
from . import database
from .middlewares import safe_http, safe_sql
from .routes.auth import bp as authbp

logger = logging.getLogger(__name__)


async def setup_postgres(_, loop):
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
    database.RDB = database.Postgres(pgconn)
    logger.info("Connection to postgres established.")
    

async def setup_redis(_, loop):
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
    database.KVS = database.Redis(redisconn)
    logger.info("Connection to redis established.")


# Register remote or local databases
if config.webapi.PRODUCTION:
    app.listener("before_server_start")(setup_postgres)
    app.listener("before_server_start")(setup_redis)
else:
    database.RDB = database.SQLite()
    database.KVS = database.InMemory()

# Register routes
app.blueprint(authbp, url_prefix="/v1/auth")
