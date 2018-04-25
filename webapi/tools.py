"""Several tools used accross by other modules"""

import logging
from datetime import datetime, timedelta
from distutils.util import strtobool
from logging.handlers import BufferingHandler
from os.path import abspath, dirname
from typing import Union, Optional, List
from uuid import uuid4
from asyncio import sleep, get_event_loop
import jwt as jwtlib

logger = logging.getLogger(__name__)


def find(func, iteratee):
    """Returns the first element that match the query"""
    for value in iteratee:
        if func(value):
            return value
    return None


def cast(val, typ, *types):
    """Cast a value to the given type. /!\\ Hack /!\\ """

    # get Optional
    if typ.__class__ in [Union.__class__, Optional.__class__] \
       and len(typ.__args__) == 2 \
       and typ.__args__[1] is None:
        typ = typ.__args__[0]

    # split Unions
    elif typ.__class__ == Union.__class__:
        return cast(val, *typ.__args__)

    # consume List
    if typ.__class__ == List.__class__:
        values = []
        for element in val:
            values.append(cast(element, typ.__args__[0]))
        return values

    # cast
    types = list(types) + [typ]
    for typ in types:
        try:
            return typ(val)
        except:
            continue

    raise TypeError("{} not castable in any of {{{}}}.".format(val, types))


def real_type(typ):
    """Escape the type from Union and Optional. /!\\ Hack /!\\ """
    if typ.__class__ in [Union.__class__, Optional.__class__]:
        return typ.__args__[0]
    return typ


def root():
    """Return the path of the package root"""
    return dirname(abspath(__file__))


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


def generate_token(key, iat=None, exp_delta=timedelta(minutes=5), typ="player",
                   tid=None, uid="00000000-0000-0000-0000-000000000000"):
    """Generate a JSON Web Token"""
    if iat is None:
        iat = datetime.utcnow()

    if tid is None:
        tid = str(uuid4())

    return jwtlib.encode({
        "iss": "webapi",
        "sub": "webgames",
        "iat": iat,
        "exp": iat + exp_delta,
        "tid": tid,
        "typ": typ,
        "uid": uid
    }, key, algorithm='HS256').decode()


def ask_bool(prompt):
    """Ask a question to the user, retry until the reply is valid"""
    while True:
        try:
            return strtobool(input("%s (yes/no) " % prompt).strip().casefold())
        except ValueError:
            continue


def fake_async(func):
    async def wrapped(*args, **kwargs):
        await sleep(0)
        return func(*args, **kwargs)
    return wrapped


def lruc(coro, loop=get_event_loop()):
    return loop.run_until_complete(coro)
