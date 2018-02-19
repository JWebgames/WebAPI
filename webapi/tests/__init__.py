from ..config import expose_default
expose_default()

import logging
logging.basicConfig(filename="/dev/null", filemode="a")
