"""Configure logging and load default configuration"""

import logging
from os import getenv
from distutils.util import strtobool
import webapi.config

#logging.basicConfig(level=logging.DEBUG)
logging.basicConfig(filename="test.log", filemode="w")
logging.addLevelName(45, "SECURITY")


if strtobool(getenv("WEBAPI_TEST_USING_CONFIG", "no")):
    webapi.config.load_merge_validate_expose()
elif strtobool(getenv("WEBAPI_PRODUCTION", "no")):
    webapi.config.expose_default(webapi={"PRODUCTION": True})
else:
    webapi.config.expose_default()
