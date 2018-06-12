"""Helper modules, each function is callable before/after sanic
request/response in order to parse/validate/modify/... them"""

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
from .storage import drivers
from . import config
from .server import app
from .exceptions import WebAPIError
from .storage.models import ClientType

logger = getLogger(__name__)

@app.middleware("request")
def set_real_ip(req):
    """Replace the actual IP with the real IP of the client"""
    header_xff = req.headers.get("X-Forwarded-For")
    if header_xff is not None:
        req.ip = header_xff.split(", ", 1)[0]
        return

    header_xri = req.headers.get("X-Real-IP")
    if header_xri is not None:
        req.ip = header_xri

@app.exception(WebAPIError)
def safe_webapi(request, exception):
    """
    Escape API exceptions

    return HTTP 400 'BadRequest' status code with the error
    contained in the 'error' field.
    """
    logger.log(45, "Impossible action on normal use (IP: %s)",
                   request.ip, exc_info=True)
    return json({"error": str(exception)}, 400)


@app.exception(SanicException)
def safe_http(request, exception):
    """
    Escape sanic exceptions

    return HTTP status code according to sanic's error with the error
    contained in the 'error' json field
    """
    logger.debug(str(exception), exc_info=True)
    return json({"error": str(exception)}, exception.status_code)


@app.exception(SQLiteIntegrityError, PostgresIntegrityError)
def safe_sql(request, exception):
    """
    Escape postgres integrity violation

    return HTTP 400 'BadRequest' status code with the error
    contained in the 'error' field.
    """
    logger.debug(str(exception), exc_info=True)
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
                jwt = jwtlib.decode(bearer[7:].strip(), config.webapi.JWT_SECRET, algorithms=['HS256'])
            except jwtlib.exceptions.InvalidTokenError as exc:
                logger.log(45, f"Invalid token (IP: {req.ip})")
                raise Forbidden("Invalid token") from exc

            if await drivers.KVS.is_token_revoked(jwt["jti"]):
                logger.log(45, f"Token has been revoked (IP: {req.ip})")
                raise Forbidden("Revoked token")

            if ClientType(jwt["typ"]) not in allowed_client_types:
                logger.log(45, 'Restricted access: "%s" not in {%s} (IP: %s)',
                           jwt["typ"], ", ".join(map(str, allowed_client_types)), req.ip)
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
                return await func(req, *args, **kwargs)
            if not isinstance(req.json, dict):
                raise InvalidUsage("JSON object required.")

            template = "Fields {{{}}} are missing"
            if not req.json:
                raise InvalidUsage(template.format(", ".join(fields)))
            missing_keys = fields - req.json.keys()
            if missing_keys:
                raise InvalidUsage(template.format(", ".join(missing_keys)))
            missing_values = [key for key in (req.json.keys() & fields)
                              if req.json[key] is None 
                                 or (type(req.json[key]) is str
                                     and not req.json[key].strip())]
            if missing_values:
                raise InvalidUsage(template.format(", ".join(missing_values)))
            return await func(req, *args, **req.json, **kwargs)
        return require_fields_wrapped
    return require_fields_wrapper
