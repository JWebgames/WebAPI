import logging
#logging.basicConfig(level=logging.DEBUG)
logging.basicConfig(filename="/dev/null")
logging.addLevelName(45, "SECURITY")

from ..config import expose_default
expose_default()
