"""Helper modules, each function is callable before/after sanic
request/response in order to parse/validate/modify/... them"""

from enum import Enum
from functools import wraps
from ipaddress import ip_address
from logging import getLogger
from sqlite3 import IntegrityError as SQLiteIntegrityError
import jwt as jwtlib
from asyncpg.exceptions import IntegrityConstraintViolationError as PostgresIntegrityError
from sanic.exceptions import SanicException,\
                             InvalidUsage,\
                             Unauthorized,\
                             Forbidden
from sanic.response import json
from . import database
from .config import webapi
from .server import app

logger = getLogger(__name__)


class ClientType(Enum):
    """Enum of JWT user type"""
    ADMIN = "admin"
    PLAYER = "player"
    GAME = "game"
    WEBAPI = "webapi"
    MANAGER = "manager"

@app.middleware("request")
def set_real_ip(req):
    """Replace the actual IP with the real IP of the client"""
    if webapi.REVERSE_PROXY_IPS is None:
        return

    if ip_address(req.ip) in webapi.REVERSE_PROXY_IPS:
        header_xff = req.headers.get("X-Forwarded-For")
        if header_xff is not None:
            req.ip = header_xff.split(", ", 1)[0]
            return

        header_xri = req.headers.get("X-Real-IP")
        if header_xri is not None:
            req.ip = header_xri
            return


@app.exception(SanicException)
def safe_http(request, exception):
    """
    Escape sanic exceptions

    return HTTP status code according to sanic's error with the error
    contained in the 'error' json field
    """
    logger.warning(str(exception), exc_info=exception)
    return json({"error": str(exception)}, exception.status_code)


@app.exception(SQLiteIntegrityError, PostgresIntegrityError)
def safe_sql(request, exception):
    """
    Escape postgres integrity violation

    return HTTP 400 'BadRequest' status code with the error
    contained in the 'error' field.
    """
    logger.warning(str(exception), exc_info=exception)
    return json({"error": exception.args[0]}, 400)


def authenticate(allowed_client_types: set):
    """Wrapper wrapper"""
    def authenticate_wrapper(func):
        """Wrapper"""
        @wraps(func)
        async def authenticate_wrapped(req, *args, **kwargs):
            """
            Validate the JSON Web Token.
            Call decorated function with the JWT as keyword
            """
            bearer = req.headers.get("Authorization")
            if not bearer:
                logger.warning(f"Authorization header is missing (IP: {req.ip})")
                raise Unauthorized("Authorization header required")

            if not bearer.startswith("Bearer:"):
                logger.warning(f"Wrong authorization header type (IP: {req.ip})")
                raise Unauthorized("Bearer authorization type required")

            try:
                jwt = jwtlib.decode(bearer[7:].strip(), webapi.JWT_SECRET)
            except jwtlib.exceptions.InvalidTokenError:
                logger.log(45, f"Invalid token (IP: {req.ip})")
                raise Forbidden("Invalid token")

            if await database.KVS.is_token_revoked(jwt["tid"]):
                logger.log(45, f"Token has been revoked (IP: {req.ip})")
                raise Forbidden("Revoked token")

            if ClientType(jwt["typ"]) not in allowed_client_types:
                logger.log(45, 'Restricted access: "%s" not in {%s} (IP: %s)',
                           jwt["typ"], ", ".join(allowed_client_types), req.ip)
                raise Forbidden("Restricted access")

            return await func(req, *args, **kwargs, jwt=jwt)
        return authenticate_wrapped
    return authenticate_wrapper


def require_fields(fields: set):
    """Wrapper wrapper"""
    def require_fields_wrapper(func):
        """Wrapper"""
        @wraps(func)
        async def require_fields_wrapped(req, *args, **kwargs):
            """
            List JSON fields required.
            Call decorated function with every json key as keyword
            """
            header_ct = req.headers.get("Content-Type")
            if header_ct is None or "application/json" not in header_ct:
                raise InvalidUsage("JSON required")
            if not fields:
                pass
            if not isinstance(req.json, dict):
                raise InvalidUsage("JSON object required")
            if not req.json:
                raise InvalidUsage(f"Fields {fields} are missing")
            missings = fields - req.json.keys()
            if missings:
                raise InvalidUsage(f"Fields {missings} are missing")
            return await func(req, *args, **req.json, **kwargs)
        return require_fields_wrapped
    return require_fields_wrapper
