"""Configure logging and load default configuration"""

import logging
from webapi.config import expose_default

#logging.basicConfig(level=logging.DEBUG)
logging.basicConfig(filename="/dev/null")
logging.addLevelName(45, "SECURITY")

expose_default()
