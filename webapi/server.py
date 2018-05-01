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

async def connect_to_postgres(_app, loop, prepare=True):
    """Connect to postgres and expose the connection object"""
    logger.info("Connecting to postgres...")
    postgres = await asyncpg.connect(
        dsn=config.postgres.DSN,
        host=config.postgres.HOST,
        port=config.postgres.PORT,
        user=config.postgres.USER,
        database=config.postgres.DATABASE,
        password=config.postgres.PASSWORD,
        loop=loop
    )
    drivers.RDB = drivers.Postgres(postgres)
    logger.info("Connection to postgres established.")
    if prepare:
        await drivers.RDB.prepare()


async def connect_to_redis(_app, loop):
    """Connect to redis and expose the connection object"""
    logger.info("Connecting to redis...")
    if config.redis.DSN is not None:
        redispool = await aioredis.create_pool(
            address=config.redis.DSN,
            loop=loop
        )
    else:
        redispool = await aioredis.create_pool(
            address=(config.redis.HOST, config.redis.PORT),
            db=config.redis.DATABASE,
            password=config.redis.PASSWORD,
            loop=loop
        )
    drivers.KVS = drivers.Redis(redispool)
    logger.info("Connection to redis established.")


async def disconnect_from_postgres(_app, _loop):
    """Safely disconnect from postgres"""
    logger.info("Disconnecting from postgres...")
    await drivers.RDB.conn.close()
    logger.info("Disconnected from prostgres.")


async def disconnect_from_redis(_app, _loop):
    """Safely disconnect from redis"""
    logger.info("Disconnecting from redis...")
    drivers.KVS.redis.close()
    await drivers.KVS.redis.wait_closed()
    logger.info("Disconnected from redis")


# Register remote or local databases
if config.webapi.PRODUCTION:
    app.listener("before_server_start")(connect_to_postgres)
    app.listener("before_server_start")(connect_to_redis)
    app.listener("after_server_stop")(disconnect_from_postgres)
    app.listener("after_server_stop")(disconnect_from_redis)
else:
    drivers.RDB = drivers.SQLite()
    drivers.KVS = drivers.InMemory()

@app.route("/status")
async def server_status(_req):
    return text("Server running\n")

# Register routes
app.blueprint(authbp, url_prefix="/v1/auth")
