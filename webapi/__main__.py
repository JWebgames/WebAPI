"""Entrypoint load configuration, setup logging and start the server"""

import logging
from sys import exit
from . import config
from . import server
from .exceptions import ConfigError
from .tools import DelayLogFor

logger = logging.getLogger(__name__)

# setup logging
logging.root.level = logging.NOTSET
logging.addLevelName(45, "SECURITY")

stdout = logging.StreamHandler()
stdout.formatter = logging.Formatter(
    "{asctime} [{levelname}] <{name}:{funcName}> {message}", style="{")
logging.root.handlers.clear()
logging.root.addHandler(stdout)

logging.getLogger("sanic.error").handlers.clear()
logging.getLogger("sanic.access").handlers.clear()

should_exit = False
with DelayLogFor(logging.root):
    try:
        config.load_merge_validate_expose()
    except ConfigError:
        should_exit = True
        logger.exception("Configuration error...")
    stdout.level = logging._nameToLevel[config.webapi.LOG_LEVEL]
if should_exit:
    exit(1)

if not config.dryrun:
	server.app.run(host=config.webapi.HOST, port=config.webapi.PORT)
