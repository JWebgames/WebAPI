"""Entrypoint load configuration, setup logging and start the server"""

import asyncio
import atexit
import logging
import ssl
from argparse import ArgumentParser
from functools import partial
from getpass import getpass
from sys import argv, exit as sysexit
from asyncpg.exceptions import PostgresConnectionError, InvalidAuthorizationSpecificationError
from . import config
from .exceptions import ConfigError
from .tools import DelayLogFor, ask_bool


def setup():
    logging.root.level = logging.NOTSET
    logging.addLevelName(45, "SECURITY")

    global logger
    logger = logging.getLogger(__name__)
    stdout = logging.StreamHandler()
    stdout.formatter = logging.Formatter(
        "{asctime} [{levelname}] <{name}:{funcName}> {message}", style="{")
    logging.root.handlers.clear()
    logging.root.addHandler(stdout)

    should_exit = False
    with DelayLogFor(logging.root):
        try:
            config.load_merge_validate_expose()
        except ConfigError:
            should_exit = True
            logger.exception("Configuration error...")
        else:
            stdout.level = logging._nameToLevel[config.webapi.LOG_LEVEL]
    if should_exit:
        sysexit(1)


dispatcher = {}
def register(func):
    dispatcher[func.__name__] = func
    return func

@register
def showconfig():
    config.show()
    sysexit(0)

@register
def exportconfig():
    config.export_default_config()
    sysexit(0)
    
@register
def run():
    setup()
    from . import server
    ssl_context = None
    if config.webapi.SSL_KEY_PATH and config.webapi.SSL_CERT_PATH:
        ssl_context = ssl.create_default_context(
            purpose=ssl.Purpose.CLIENT_AUTH)
        ssl_context.load_cert_chain(
            config.webapi.SSL_CERT_PATH,
            config.webapi.SSL_KEY_PATH,
            config.webapi.SSL_KEY_PASS)

    server.app.run(
        host=config.webapi.HOST,
        port=config.webapi.PORT,
        debug=not config.webapi.PRODUCTION,
        ssl=ssl_context,
        access_log=not config.webapi.PRODUCTION)

@register
def dryrun():
    setup()
    from . import server
    loop = asyncio.get_event_loop()
    future = asyncio.gather(server.connect_to_postgres(None, loop, False),
                            server.connect_to_redis(None, loop))
    try:
        loop.run_until_complete(future)
    except:
        logger.warning("Was not able to connect to databases...", exc_info=True)
    else:
        future = asyncio.gather(server.disconnect_from_postgres(None, loop),
                                server.disconnect_from_redis(None, loop))
        atexit.register(partial(loop.run_until_complete, future))

@register
def wizard():
    setup()
    from . import admin
    admin.wizard()


cmdparser = ArgumentParser()
cmdparser.add_argument("command", choices=[
    "run", "dryrun", "showconfig", "exportconfig", "wizard"])
cli = cmdparser.parse_args(argv[1:2])
dispatcher[cli.command]()
