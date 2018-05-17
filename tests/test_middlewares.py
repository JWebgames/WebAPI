"""Test runner for config module"""

import warnings
from asyncio import coroutine, get_event_loop
from datetime import datetime, timedelta
from logging import getLogger
from secrets import token_urlsafe
from sqlite3 import IntegrityError
from unittest import TestCase
from uuid import uuid4

from sanic.exceptions import InvalidUsage
from sanic.response import json
from jwt import decode as jwt_decode

from webapi.tools import generate_token
from webapi.config import webapi
from webapi.server import app
from webapi.middlewares import authenticate, require_fields
from webapi.storage import drivers
from webapi.storage.models import ClientType

logger = getLogger(__name__)

ERROR_MESSAGE_1 = token_urlsafe(16)
ERROR_MESSAGE_2 = token_urlsafe(16)
NOW = datetime.utcnow()

PLAYER_JWT = generate_token(webapi.JWT_SECRET)
ADMIN_JWT = generate_token(webapi.JWT_SECRET, typ=ClientType.ADMIN.value)
EXPIRED_JWT = generate_token(webapi.JWT_SECRET,
                             iat=datetime.utcnow() - timedelta(hours=24))
WRONG_KEY_JWT = generate_token("wrong-super-secret-password")
REVOKED_JWT = generate_token(webapi.JWT_SECRET)

@app.route("/tests/http_error")
def raise_http_error(_req):
    """Raise a http error"""
    raise InvalidUsage(ERROR_MESSAGE_1)


@app.route("/tests/sql_error")
def raise_sql_error(_req):
    """Raise a sql error"""
    raise IntegrityError(ERROR_MESSAGE_2)


@app.route("/tests/auth")
@authenticate({ClientType.PLAYER, ClientType.ADMIN})
@coroutine
def require_auth(_req, jwt):
    """Return an empty json, require authentication"""
    return json({})


@app.route("/tests/admin_auth")
@authenticate({ClientType.ADMIN})
@coroutine
def require_auth_admin(_req, jwt):
    """Return an empty json, require admin authentication"""
    return json({})

@app.route("/tests/fields", methods=["POST"])
@require_fields({"field1", "field2"})
@coroutine
def route_require_fields(_req, field1, field2):
    """Return the fields"""
    return json({"field1": field1, "field2": field2})


class TestExceptions(TestCase):
    """Test case for middlewares.(safe_http|safe_sql)"""
    def test_safe_http(self):
        """Test safe_http against SanicException"""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            _, res = app.test_client.get("/tests/http_error")
        self.assertEqual(res.status, 400)
        self.assertEqual(res.headers["content-type"], "application/json")
        self.assertIn("error", res.json)
        self.assertEqual(res.json["error"], ERROR_MESSAGE_1)

    def test_safe_sql(self):
        """Test safe_sql against IntegrityConstraintViolationError"""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            _, res = app.test_client.get("/tests/sql_error")
        self.assertEqual(res.status, 400)
        self.assertEqual(res.headers["content-type"], "application/json")
        self.assertIn("error", res.json)
        self.assertEqual(res.json["error"], ERROR_MESSAGE_2)

class TestAuthenticate(TestCase):
    """Test case for middlewares.authenticate"""
    def test_valid_token(self):
        """Valid token has access"""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            _, res = app.test_client.get("/tests/auth", headers={
                "Authorization": "Bearer: %s" % PLAYER_JWT
            })
        self.assertEqual(res.status, 200)

    def test_no_authorization_header(self):
        """Fail if authorization header is missing"""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            _, res = app.test_client.get("/tests/auth")
        self.assertEqual(res.json["error"], "Authorization header required")
        self.assertEqual(res.status, 401)

    def test_no_bearer(self):
        """Fail if authorization header is not Bearer"""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            _, res = app.test_client.get("/tests/auth", headers={
                "Authorization": PLAYER_JWT
            })
        self.assertEqual(res.json["error"], "Bearer authorization type required")
        self.assertEqual(res.status, 401)

    def test_expired_token(self):
        """Fail if token is expirated (JWT:EXP)"""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            _, res = app.test_client.get("/tests/auth", headers={
                "Authorization": "Bearer: %s" % EXPIRED_JWT
            })
        self.assertEqual(res.json["error"], "Invalid token")
        self.assertEqual(res.status, 403)

    def test_wrong_key(self):
        """Fail if the token is signed with a wrong key"""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            _, res = app.test_client.get("/tests/auth", headers={
                "Authorization": "Bearer: %s" % WRONG_KEY_JWT
            })
        self.assertEqual(res.json["error"], "Invalid token")
        self.assertEqual(res.status, 403)

    def test_restricted_access_deny(self):
        """Fail if access is restricted"""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            _, res = app.test_client.get("/tests/admin_auth", headers={
                "Authorization": "Bearer: %s" % PLAYER_JWT
            })
        self.assertEqual(res.json["error"], "Restricted access")
        self.assertEqual(res.status, 403)

    def test_restricted_access_grant(self):
        """Pass if access is not restricted"""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            _, res = app.test_client.get("/tests/admin_auth", headers={
                "Authorization": "Bearer: %s" % ADMIN_JWT
            })
        self.assertEqual(res.status, 200)

    def test_revoked_token(self):
        """Fail if the token is revoked"""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            _, res_logout = app.test_client.get("/v1/auth/logout", headers={
                "Authorization": "Bearer: %s" % REVOKED_JWT
            })
            _, res_auth = app.test_client.get("/tests/auth", headers={
                "Authorization": "Bearer: %s" % REVOKED_JWT
            })
        self.assertEqual(res_logout.status, 200)
        self.assertEqual(res_auth.status, 403)
        self.assertEqual(res_auth.json["error"], "Revoked token")

class TestRequireFields(TestCase):
    """Test middlewares.require_fields"""
    def test_missing_paylod(self):
        """No payload"""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            _, res = app.test_client.post("/tests/fields")
        self.assertEqual(res.json["error"], "JSON required")
        self.assertEqual(res.status, 400)

    def test_missing_all_fields(self):
        """Empty object"""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            _, res = app.test_client.post("/tests/fields", json={})

        if res.json["error"] != "Fields {field1, field2} are missing"\
           and res.json["error"] != "Fields {field2, field1} are missing":
            self.assertEqual(res.json["error"], "Fields {field1, field2} are missing")

        self.assertEqual(res.status, 400)

    def test_missing_some_fields(self):
        """Missing fields"""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            _, res = app.test_client.post("/tests/fields", json={"field1":""})
        self.assertEqual(res.json["error"], r"Fields {field2} are missing")
        self.assertEqual(res.status, 400)

    def test_all_fields_ok(self):
        """All fields presents"""
        data = {"field1": "", "field2": ""}
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            _, res = app.test_client.post("/tests/fields", json=data)
        self.assertEqual(res.json, data)
        self.assertEqual(res.status, 200)
