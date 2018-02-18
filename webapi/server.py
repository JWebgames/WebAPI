"""Setup sanic, redis and postgres"""

import logging
import aioredis
import asyncpg
from asyncpg.exceptions import IntegrityConstraintViolationError
from sanic import Sanic
from sanic.exceptions import SanicException
from sanic.response import json
from . import config
from .routes import auth


logger = logging.getLogger(__name__)
app = Sanic()


postgres: asyncpg.Connection
@app.listener("before_server_start")
async def setup_postgres(_, loop):
    """Connect to postgres and expose the connection object"""
    global postgres
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


redis: aioredis.ConnectionsPool
@app.listener("before_server_start")
async def setup_redis(_, loop):
    """Connect to redis and expose the connection object"""
    global redis
    if config.redis.DSN is not None:
        redis = await aioredis.create_pool(address=config.redis.DSN, loop=loop)
    else:
        redis = await aioredis.create_pool(
            address=(config.redis.HOST, config.redis.PORT),
            db=config.redis.DATABASE,
            password=config.redis.PASSWORD,
            loop=loop
        )
    logger.info("Connection to redis established.")


@app.exception(SanicException)
def safe_http_error(_, err):
    """
    Escape sanic exceptions

    return HTTP status code according to sanic's error with the error
    contained in the 'error' json field
    """
    logger.warning(str(err), exc_info=err)
    return json({"error": str(err)}, err.status_code)


@app.exception(IntegrityConstraintViolationError)
def safe_sql_error(_, err):
    """
    Escape postgres integrity violation

    return HTTP 400 'BadRequest' status code with the error contained in
    the 'error' field.
    """
    logger.warning(str(err), exc_info=err)
    return json({"error": err.args[0]}, 400)


app.blueprint(auth.bp)
