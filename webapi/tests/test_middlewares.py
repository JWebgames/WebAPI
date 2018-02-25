"""Test runner for config module"""

import warnings
from asyncio import coroutine
from datetime import datetime, timedelta
from logging import getLogger
from secrets import token_urlsafe
from sqlite3 import IntegrityError
from unittest import TestCase
from uuid import uuid4

import jwt as jwtlib
from sanic.exceptions import InvalidUsage
from sanic.response import json

from ..config import webapi
from ..server import app
from ..middlewares import ClientType, authenticate

logger = getLogger(__name__)

ERROR_MESSAGE_1 = token_urlsafe(16)
ERROR_MESSAGE_2 = token_urlsafe(16)
NOW = datetime.utcnow()

player_id = uuid4()
player_jwt_payload = {
    "iss": ClientType.WEBAPI.value,
    "sub": "webgames",
    "iat": NOW,
    "exp": NOW + timedelta(minutes=5),
    "tid": str(uuid4()),
    "typ": ClientType.PLAYER.value,
    "uid": str(player_id)
}
player_jwt = jwtlib.encode(player_jwt_payload, webapi.JWT_SECRET).decode()

admin_id = uuid4()
admin_jwt_payload = {
    "iss": ClientType.WEBAPI.value,
    "sub": "webgames",
    "iat": NOW,
    "exp": NOW + timedelta(minutes=5),
    "tid": str(uuid4()),
    "typ": ClientType.ADMIN.value,
    "uid": str(admin_id)
}
admin_jwt = jwtlib.encode(admin_jwt_payload, webapi.JWT_SECRET).decode()

revoked_jwt = jwtlib.encode({
    "iss": ClientType.WEBAPI.value,
    "sub": "webgames",
    "iat": NOW,
    "exp": NOW + timedelta(minutes=5),
    "tid": str(uuid4()),
    "typ": ClientType.PLAYER.value,
    "uid": str(uuid4())
}, webapi.JWT_SECRET).decode()

expired_jwt = jwtlib.encode({
    "iss": ClientType.WEBAPI.value,
    "sub": "webgames",
    "iat": NOW - timedelta(hours=24),
    "exp": NOW - timedelta(hours=12),
    "tid": str(uuid4()),
    "typ": ClientType.PLAYER.value,
    "uid": str(uuid4())
}, webapi.JWT_SECRET).decode()

wrong_key_jwt = jwtlib.encode({
    "iss": ClientType.WEBAPI.value,
    "sub": "webgames",
    "iat": NOW,
    "exp": NOW + timedelta(minutes=5),
    "tid": str(uuid4()),
    "typ": ClientType.PLAYER.value,
    "uid": str(uuid4())
}, "wrong-super-secret-password").decode()


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
    """Return the JWT"""
    return json(jwt)


@app.route("/tests/admin_auth")
@authenticate({ClientType.ADMIN})
@coroutine
def require_auth_admin(_req, jwt):
    """Return the JWT"""
    return json(jwt)


class TestExceptions(TestCase):
    """Test case for middlewares.(safe_http|safe_sql)"""
    def test_safe_http(self):
        """Test against SanicException"""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            _, res = app.test_client.get("/tests/http_error")
        self.assertEqual(res.status, 400)
        self.assertEqual(res.headers["content-type"], "application/json")
        self.assertIn("error", res.json)
        self.assertEqual(res.json["error"], ERROR_MESSAGE_1)

    def test_safe_sql(self):
        """Test against IntegrityConstraintViolationError"""
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
                "Authorization": "Bearer: %s" % player_jwt
            })
        self.assertEqual(res.json, player_jwt_payload)
        self.assertEqual(res.status, 200)

    def test_no_authorization_header(self):
        """Authorization header is missing"""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            _, res = app.test_client.get("/tests/auth")
        self.assertEqual(res.json["error"], "Authorization header required")
        self.assertEqual(res.status, 401)

    def test_no_bearer(self):
        """Authorization header is not Bearer"""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            _, res = app.test_client.get("/tests/auth", headers={
                "Authorization": player_jwt
            })
        self.assertEqual(res.json["error"], "Bearer authorization type required")
        self.assertEqual(res.status, 401)

    def test_expired_token(self):
        """Token is expirated (JWT:EXP)"""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            _, res = app.test_client.get("/tests/auth", headers={
                "Authorization": "Bearer: %s" % expired_jwt
            })
        self.assertEqual(res.json["error"], "Invalid token")
        self.assertEqual(res.status, 403)

    def test_wrong_key(self):
        """Token is signed with a wrong key"""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            _, res = app.test_client.get("/tests/auth", headers={
                "Authorization": "Bearer: %s" % wrong_key_jwt
            })
        self.assertEqual(res.json["error"], "Invalid token")
        self.assertEqual(res.status, 403)

    def test_restricted_access_deny(self):
        """Access is restricted to Admin. Player try to access"""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            _, res = app.test_client.get("/tests/admin_auth", headers={
                "Authorization": "Bearer: %s" % player_jwt
            })
        self.assertEqual(res.json["error"], "Restricted access")
        self.assertEqual(res.status, 403)

    def test_restricted_access_grant(self):
        """Access is restricted to Admin. Admin try to access"""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            _, res = app.test_client.get("/tests/admin_auth", headers={
                "Authorization": "Bearer: %s" % admin_jwt
            })
        logger.debug(res.json)
        self.assertEqual(res.status, 200)

    def test_revoked_token(self):
        """Player try to connect after a logout"""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            _, res = app.test_client.get("/v1/auth/logout", headers={
                "Authorization": "Bearer: %s" % revoked_jwt
            })
        logger.debug(res.json)
        self.assertEqual(res.status, 200)

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            _, res = app.test_client.get("/tests/auth", headers={
                "Authorization": "Bearer: %s" % revoked_jwt
            })
        self.assertEqual(res.json["error"], "Revoked token")
        self.assertEqual(res.status, 403)
