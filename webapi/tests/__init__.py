import logging
from ..config import expose_default

expose_default()
logging.basicConfig(filename="/dev/null", filemode="a")
