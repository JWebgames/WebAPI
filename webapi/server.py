"""Setup sanic, redis and postgres"""

import logging
from uuid import uuid4
import aioredis
import asyncpg
import scrypt
from aiohttp import ClientSession
from sanic import Sanic
from sanic.response import text

app = Sanic(__name__, configure_logging=False)
from . import config
from .tools import lruc
from .storage import drivers
from .routes.auth import bp as authbp
from .routes.games import bp as gamesbp
from .routes.groups import bp as groupsbp
from .routes.msgqueues import bp as msgqueuesbp, close_all_connections

logger = logging.getLogger(__name__)
http_client = None

async def connect_to_postgres(_app, loop):
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

@app.listener("before_server_start")
async def connect_to_messager(_app, _loop):
    logger.info("Connecting to messager...")
    drivers.MSG = drivers.Messager()
    logger.info("Connection to messager established.")


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

@app.listener("after_server_stop")
async def disconnect_from_messager(_app, _loop):
    logger.info("Disconnecting from manager...")
    drivers.MSG.close()
    logger.info("Disconnected from manager")

@app.listener("before_server_start")
async def start_http_client(_app, loop):
    global http_client
    http_client = ClientSession(loop=loop)

@app.listener("after_server_stop")
async def stop_http_client(_app, _loop):
    await http_client.close()


# Register remote or local databases
if config.webapi.PRODUCTION:
    logger.info("Running in production mode")
    app.listener("before_server_start")(connect_to_postgres)
    app.listener("before_server_start")(connect_to_redis)
    app.listener("after_server_stop")(disconnect_from_postgres)
    app.listener("after_server_stop")(disconnect_from_redis)
else:
    logger.info("Running in development mode")
    drivers.RDB = drivers.SQLite()
    drivers.KVS = drivers.InMemory()

    # Feed database with some data
    for toto in ["toto1", "toto2", "admin"]:
        toto_id = uuid4()
        lruc(drivers.RDB.create_user(
            toto_id, toto, "%s@example.com" % toto,
            scrypt.encrypt(b"salt", "password", maxtime=0.01)))
        lruc(drivers.RDB.set_user_admin(toto_id, True))
    lruc(drivers.RDB.create_game("bomberman", toto_id, 4))
    lruc(drivers.RDB.create_game("stupid-game", toto_id, 4))

# Register others functions
app.listener("before_server_stop")(close_all_connections)

@app.route("/status")
async def server_status(_req):
    return text("Server running\n")

# Register routes
app.blueprint(authbp, url_prefix="/v1/auth")
app.blueprint(gamesbp, url_prefix="/v1/games")
app.blueprint(groupsbp, url_prefix="/v1/groups")
app.blueprint(msgqueuesbp, url_prefix="/v1/msgqueues")
