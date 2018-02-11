from typing import Union, Optional
from contextlib import contextmanager
import logging
from logging.handlers import MemoryHandler

logger = logging.getLogger(__name__)

def cast(typ, val):
    return real_type(typ)(val)


def real_type(typ):
    if typ.__class__ in [Union.__class__, Optional.__class__]:
        return typ.__args__[0]
    else:
        return typ


@contextmanager
def delai_log(target, before_flush=None):
    buffer = MemoryHandler(10000, flushLevel=logging.NOTSET, target=target)
    logging.root.addHandler(buffer)
    yield
    if before_flush is not None:
        print("bou")
        before_flush()
    logging.root.addHandler(target)
    buffer.close()
    logging.root.removeHandler(buffer)
