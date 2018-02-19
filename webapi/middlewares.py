"""Helper module, call functions before/after sanic req/res"""

from logging import getLogger
from sanic.response import json

logger = getLogger(__name__)

def safe_http(request, exception):
    """
    Escape sanic exceptions

    return HTTP status code according to sanic's error with the error
    contained in the 'error' json field
    """
    logger.warning(str(exception), exc_info=exception)
    return json({"error": str(exception)}, exception.status_code)


def safe_sql(request, exception):
    """
    Escape postgres integrity violation

    return HTTP 400 'BadRequest' status code with the error contained in
    the 'error' field.
    """
    logger.warning(str(exception), exc_info=exception)
    return json({"error": exception.args[0]}, 400)
