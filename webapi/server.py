"""Setup sanic, redis and postgres"""

import logging
from asyncio import sleep
from typing import Optional
import aioredis
import asyncpg
from sanic import Sanic

app = Sanic(__name__, configure_logging=False)
from . import config
from . import middlewares
from .routes import auth

logger = logging.getLogger(__name__)

postgres: Optional[asyncpg.Connection] = None
@app.listener("before_server_start")
async def setup_postgres(_, loop):
    """Connect to postgres and expose the connection object"""
    global postgres
    if config.webapi.PRODUCTION:
        postgres = await asyncpg.connect(
            dsn=config.postgres.DSN,
            host=config.postgres.HOST,
            port=config.postgres.PORT,
            user=config.postgres.USER,
            database=config.postgres.DATABASE,
            password=config.postgres.PASSWORD,
            loop=loop
        )
        logger.info("Connection to postgres established.")
    else:
        logger.info("Running without postgres.")
        await sleep(0)
    


redis: Optional[aioredis.ConnectionsPool] = None
@app.listener("before_server_start")
async def setup_redis(_, loop):
    """Connect to redis and expose the connection object"""
    global redis
    if config.webapi.PRODUCTION:
        if config.redis.DSN is not None:
            redis = await aioredis.create_pool(
                address=config.redis.DSN,
                loop=loop
            )
        else:
            redis = await aioredis.create_pool(
                address=(config.redis.HOST, config.redis.PORT),
                db=config.redis.DATABASE,
                password=config.redis.PASSWORD,
                loop=loop
            )
        logger.info("Connection to redis established.")
    else:
        logger.info("Running without redis.")
        await sleep(0)

