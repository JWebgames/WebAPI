"""Entrypoint load configuration, setup logging and start the server"""

import asyncio
import atexit
import logging
import ssl
from argparse import ArgumentParser
from functools import partial
from sys import argv, exit as sysexit
from . import config
from .exceptions import ConfigError
from .tools import DelayLogFor


def setup():
    """Setup logging and load configuration"""
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
    """Register function to dispatcher"""
    dispatcher[func.__name__] = func
    return func

@register
def showconfig():
    """Show current configuration and exit"""
    config.show()
    sysexit(0)

@register
def exportconfig():
    """Show default configuration and exit"""
    config.export_default_config()
    sysexit(0)

@register
def run():
    """Start foreground server"""
    setup()
    from . import server
    server.prepare_web_server()

    ssl_context = None
    if config.webapi.SSL_KEY_PATH and config.webapi.SSL_CERT_PATH:
        ssl_context = ssl.create_default_context(
            purpose=ssl.Purpose.CLIENT_AUTH)
        ssl_context.load_cert_chain(
            config.webapi.SSL_CERT_PATH,
            config.webapi.SSL_KEY_PATH,
            config.webapi.SSL_KEY_PASS)

    server.APP.run(
        host=config.webapi.HOST,
        port=config.webapi.PORT,
        debug=not config.webapi.PRODUCTION,
        ssl=ssl_context,
        access_log=not config.webapi.PRODUCTION)

@register
def dryrun():
    """Load server and exit"""
    setup()
    from . import server
    server.prepare_web_server()
    loop = asyncio.get_event_loop()
    future = asyncio.gather(server.connect_to_postgres(None, loop),
                            server.connect_to_redis(None, loop))
    try:
        loop.run_until_complete(future)
    except:
        logger.warning("Was not able to connect to databases...")
    else:
        future = asyncio.gather(server.disconnect_from_postgres(None, loop),
                                server.disconnect_from_redis(None, loop))
        atexit.register(partial(loop.run_until_complete, future))

@register
def wizard():
    """Start a CLI wizard to help configure the databases"""
    setup()
    from . import admin
    admin.wizard()


cmdparser = ArgumentParser()
cmdparser.add_argument("command", choices=[
    "run", "dryrun", "showconfig", "exportconfig", "wizard"])
cli = cmdparser.parse_args(argv[1:2])
dispatcher[cli.command]()
