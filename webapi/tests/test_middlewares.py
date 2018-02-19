"""Test runner for config module"""

from unittest import TestCase

from asyncpg.exceptions import IntegrityConstraintViolationError
from sanic import Sanic
from sanic.exceptions import SanicException, NotFound

from ..config import webapi
from ..middlewares import safe_http,\
                          safe_sql

app = Sanic(configure_logging=False)

@app.route("/http_error")
def raise_sanic_error(_req):
    raise NotFound("http error")

@app.route("/sql_error")
def raise_integrity_constraint_violation_error(_req):
    raise IntegrityConstraintViolationError()

app.exception(SanicException)(safe_http)
app.exception(IntegrityConstraintViolationError)(safe_sql)

class TestExceptions(TestCase):
    """Test case for config.validate_cofig"""

    def test_safe_http(self):
        _, res = app.test_client.get("/http_error")
        self.assertEqual(res.status, 404)
        self.assertEqual(res.headers["content-type"], "application/json")
        self.assertIn("error", res.json)
        self.assertEqual(res.json["error"], "http error")
    
    #def test_safe_sql(self):
    #    _, res = app.test_client.get("/sql_error")
    #    self.assertEqual(res.status, 400)
    #    self.assertEqual(res.headers["content-type"], "application/json")
    #    self.assertIn("error", res.json)
    #    self.assertEqual(res.json["error"], "sql error")
