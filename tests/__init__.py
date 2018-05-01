"""Configure logging and load default configuration"""

import logging
from webapi.config import expose_default

#logging.basicConfig(level=logging.DEBUG)
logging.basicConfig(filename="test.log")
logging.addLevelName(45, "SECURITY")

#expose_default()
expose_default(webapi={"PRODUCTION": True})
