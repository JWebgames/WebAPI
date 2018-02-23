"""Test runner for config module"""

import warnings
from unittest import TestCase
from secrets import token_urlsafe

from asyncpg.exceptions import IntegrityConstraintViolationError
from sanic import Sanic
from sanic.exceptions import SanicException, InvalidUsage
from ..server import app

ERROR_MESSAGE_1 = token_urlsafe(16)

@app.route("/http_error")
def raise_http_error(_req):
    """Raise a http error"""
    raise InvalidUsage(ERROR_MESSAGE_1)

@app.route("/sql_error")
def raise_sql_error(_req):
    """Raise a sql error"""
    raise IntegrityConstraintViolationError()

class TestExceptions(TestCase):
    """Test case for config.validate_cofig"""
    def test_safe_http(self):
        """Test against SanicException"""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            _, res = app.test_client.get("/http_error")
            self.assertEqual(res.status, 400)
            self.assertEqual(res.headers["content-type"], "application/json")
            self.assertIn("error", res.json)
            self.assertEqual(res.json["error"], ERROR_MESSAGE_1)

    #def test_safe_sql(self):
    #    """Test against IntegrityConstraintViolationError"""
    #    _, res = app.test_client.get("/sql_error")
    #    self.assertEqual(res.status, 400)
    #    self.assertEqual(res.headers["content-type"], "application/json")
    #    self.assertIn("error", res.json)
    #    self.assertEqual(res.json["error"], "sql error")
