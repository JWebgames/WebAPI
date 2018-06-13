"""Setup sanic, redis and postgres"""

import logging
from uuid import uuid4
import aiodocker
import aioredis
import asyncpg
import scrypt
from aiohttp import ClientSession
from sanic import Sanic
from sanic.response import text

from . import config
from .tools import lruc, Ref

APP = Sanic(__name__, configure_logging=False)
HTTP = Ref()
CTR = Ref()
KVS = Ref()
RDB = Ref()
MSG = Ref()
from .storage import drivers
from .routes.auth import bp as authbp
from .routes.games import bp as gamesbp
from .routes.groups import bp as groupsbp
from .routes.msgqueues import bp as msgqueuesbp, close_all_connections

logger = logging.getLogger(__name__)

async def connect_to_postgres(_app, loop):
    """Connect to postgres and expose the connection object"""
    logger.info("Connecting to postgres...")
    postgres = await asyncpg.create_pool(
        host=config.postgres.HOST,
        port=config.postgres.PORT,
        user=config.postgres.USER,
        database=config.postgres.DATABASE,
        password=config.postgres.PASSWORD,
        loop=loop
    )
    RDB(drivers.Postgres(postgres))
    logger.info("Connection to postgres established.")


async def connect_to_redis(_app, loop):
    """Connect to redis and expose the connection object"""
    logger.info("Connecting to redis...")
    redispool = await aioredis.create_pool(
        address=config.redis.DSN,
        password=config.redis.PASSWORD,
        loop=loop)
    KVS(drivers.Redis(redispool))
    logger.info("Connection to redis established.")


@APP.listener("before_server_start")
async def connect_to_messager(_app, _loop):
    """Connect to intermediate messager"""
    logger.info("Using ZeroMQ messager...")
    MSG(drivers.Messager())


@APP.listener("before_server_start")
async def start_http_and_docker_client(_app, loop):
    """Create a shared http client"""
    logger.info("Opening HTTP clients...")
    HTTP(ClientSession(loop=loop))
    CTR(drivers.Docker(aiodocker.Docker()))
    logger.info("Clients opened.")


async def disconnect_from_postgres(_app, _loop):
    """Safely disconnect from postgres"""
    logger.info("Disconnecting from postgres...")
    await RDB.pool.close()


async def disconnect_from_redis(_app, _loop):
    """Safely disconnect from redis"""
    logger.info("Disconnecting from redis...")
    KVS.redis.close()
    await KVS.redis.wait_closed()


@APP.listener("after_server_stop")
async def disconnect_from_messager(_app, _loop):
    """Disconnect from intermediate messager"""
    logger.info("Disconnecting from manager...")
    MSG.close()


@APP.listener("after_server_stop")
async def stop_http_and_docket_client(_app, _loop):
    """Close shared http client"""
    logger.info("Closing HTTP client...")
    await CTR.docker.close()
    await HTTP.close()


def prepare_web_server():
    """Setup databases drivers, web server listeners and http routes"""
    # Register remote or local databases
    if config.webapi.PRODUCTION:
        logger.info("Running in production mode")
        APP.listener("before_server_start")(connect_to_postgres)
        APP.listener("before_server_start")(connect_to_redis)
        APP.listener("after_server_stop")(disconnect_from_postgres)
        APP.listener("after_server_stop")(disconnect_from_redis)
    else:
        logger.info("Running in development mode")
        RDB(drivers.SQLite())
        KVS(drivers.InMemory())

        # Feed database with some data
        for toto in ["toto1", "toto2", "admin"]:
            toto_id = uuid4()
            lruc(RDB.create_user(
                toto_id, toto, "%s@example.com" % toto,
                scrypt.encrypt(b"salt", "password", maxtime=0.01)))
        lruc(RDB.set_user_admin(toto_id, True))
        lruc(RDB.create_game("shifumi", toto_id, 2, "shifumi-server", [22451]))

    # Register others functions
    APP.listener("before_server_stop")(close_all_connections)

    @APP.route("/status")
    async def server_status(_req):
        """Liveness route"""
        return text("Server running\n")

    # Register routes
    APP.blueprint(authbp, url_prefix="/v1/auth")
    APP.blueprint(gamesbp, url_prefix="/v1/games")
    APP.blueprint(groupsbp, url_prefix="/v1/groups")
    APP.blueprint(msgqueuesbp, url_prefix="/v1/msgqueues")
