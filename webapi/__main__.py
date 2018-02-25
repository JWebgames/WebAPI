"""Entrypoint load configuration, setup logging and start the server"""

import logging
from argparse import ArgumentParser
from sys import argv, exit as sysexit
from . import config
from .exceptions import ConfigError
from .tools import DelayLogFor

def start():
    """Let's go !"""
    cmdparser = ArgumentParser()
    cmdparser.add_argument("command", choices=[
        "run", "dryrun", "showconfig", "exportconfig"])
    command = cmdparser.parse_args(argv[1:2]).command

    if command in ["showconfig", "exportconfig"]:
        logging.root.level = logging.FATAL
        if command == "showconfig":
            config.show()
        elif command == "exportconfig":
            config.export_default_config()
        sysexit(0)

    logging.root.level = logging.NOTSET
    logging.addLevelName(45, "SECURITY")

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
        stdout.level = logging._nameToLevel[config.webapi.LOG_LEVEL]
    if should_exit:
        sysexit(1)

    from . import server
    if command == "run":
        server.app.run(host=config.webapi.HOST, port=config.webapi.PORT)

start()
