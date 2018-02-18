"""Several tools used accross by other modules"""

import logging
from logging.handlers import BufferingHandler
from pathlib import Path
import sys
from typing import Union, Optional

logger = logging.getLogger(__name__)

def cast(typ, val):
    """Cast a value to the given type. /!\\ Hack /!\\"""
    return real_type(typ)(val)


def real_type(typ):
    """Escape the type from Union and Optional. /!\\ Hack /!\\"""
    if typ.__class__ in [Union.__class__, Optional.__class__]:
        return typ.__args__[0]
    return typ


def get_package_path():
    """Return the path of the package root"""
    return Path(sys.modules['__main__'].__file__).parent


class DelayLogFor(BufferingHandler):
    """Delai logging for a specific logger."""
    def __init__(self, delayed_logger: logging.Logger):
        self.delayed_logger = delayed_logger
        self.delayed_handlers = []
        super().__init__(float('infinity'))

    def flush(self):
        """Flush this BufferingHandler to all the delayed handlers."""
        self.acquire()
        try:
            for handler in self.delayed_handlers:
                for record in self.buffer:
                    if record.levelno >= handler.level:
                        handler.handle(record)
            self.buffer = []
        finally:
            self.release()

    def __enter__(self):
        """Replace the handlers by this BufferingHandler"""
        self.delayed_handlers.extend(self.delayed_logger.handlers)
        self.delayed_logger.handlers.clear()
        self.delayed_logger.addHandler(self)
        return self

    def __exit__(self, typ, val, traceback):
        """Restore the handlers and flush this BufferingHandler"""
        self.delayed_logger.removeHandler(self)
        self.delayed_logger.handlers.extend(self.delayed_handlers)
        self.close()
