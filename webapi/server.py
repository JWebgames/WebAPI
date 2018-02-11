if __name__ == "__main__":
    raise ImportError("Start the module, not this file.")

import logging
import aioredis
import asyncpg
from sanic import Sanic
import config

logger = logging.getLogger(__name__)
app = Sanic()


postgres: asyncpg.Connection
@app.listener("before_server_start")
async def setup_postgres(app, loop):
    global postgres
    postgres = await asyncpg.connect(
        dsn=config.postgres.DSN,
        host=config.postgres.HOST,
        port=config.postgres.PORT,
        user=config.postgres.USER,
        database=config.postgres.DATABASE,
        password=config.postgres.PASSWORD
    )
    logger.info("Connection to postgres established.")
    

redis: aioredis.ConnectionsPool
@app.listener("before_server_start")
async def setup_redis(app, loop):
    global redis
    if config.redis.DSN is not None:
        redis = await aioredis.create_pool(address=config.redis.DSN)
    else:
        redis = await aioredis.create_pool(
            address=(config.redis.HOST, config.redis.PORT),
            db=config.redis.DATABASE,
            password=config.redis.PASSWORD
        )
    logger.info("Connection to redis established.")
