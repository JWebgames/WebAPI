import logging
from .tools import DelayLogFor
from . import config
from . import server

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

with DelayLogFor(logging.root):
    config.load_merge_expose()
    stdout.level = logging._nameToLevel[config.webapi.LOG_LEVEL]

server.app.run(host=config.webapi.HOST, port=config.webapi.PORT)
