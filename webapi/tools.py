from typing import Union, Optional
from contextlib import contextmanager
import logging
from logging.handlers import BufferingHandler

logger = logging.getLogger(__name__)

def cast(typ, val):
    return real_type(typ)(val)


def real_type(typ):
    if typ.__class__ in [Union.__class__, Optional.__class__]:
        return typ.__args__[0]
    else:
        return typ


class DelayLogFor(BufferingHandler):
    def __init__(self, logger):
        self.logger = logger
        super().__init__(float('infinity'))

    def flush(self):
        self.acquire()
        try:
            for handler in self.delayed_handlers:
                for record in self.buffer:
                    if record.levelno >= max(self.logger.level, handler.level):
                        handler.handle(record)
            self.buffer = []
        finally:
            self.release()

    def __enter__(self):
        self.delayed_handlers = self.logger.handlers.copy()
        self.logger.handlers.clear()
        self.logger.addHandler(self)
        return self

    def __exit__(self, typ, val, traceback):
        self.logger.removeHandler(self)
        self.logger.handlers.extend(self.delayed_handlers)
        self.close()
