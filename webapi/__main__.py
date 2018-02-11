import logging
from logging.handlers import MemoryHandler
import config
import server

logger = logging.getLogger(__name__)

# setup logging
logging.root.level = logging.NOTSET
logging.addLevelName(45, "SECURITY")

logging.getLogger("sanic.error").handlers.clear()
logging.getLogger("sanic.access").handlers.clear()

buffer = MemoryHandler(1000000)
logging.root.addHandler(buffer)

config.load_merge_expose()

stdout = logging.StreamHandler()
stdout.formatter = logging.Formatter(
    "{asctime} [{levelname}] <{name}:{funcName}> {message}", style="{")
stdout.level=logging.INFO
logging.root.removeHandler(buffer)
buffer.setTarget(stdout)
buffer.close()
logging.root.addHandler(stdout)

logger.debug("debug")
logger.info("info")
logger.warning("warning")

# server.app.run(host=config.webapi.HOST, port=config.webapi.PORT)
