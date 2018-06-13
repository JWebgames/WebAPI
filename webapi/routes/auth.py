"""Auth route, register/connect/disconnect"""

from datetime import datetime, timedelta
from logging import getLogger
from uuid import uuid4
from secrets import token_bytes
from pytimeparse import parse as timeparse
from sanic import Blueprint
from sanic.exceptions import Forbidden, NotFound
from sanic.response import json, text
import scrypt
import jwt as jwtlib
from .. import config
from ..middlewares import authenticate, require_fields
from ..server import RDB, KVS, HTTP
from ..storage.models import ClientType, MsgQueueType
from ..exceptions import NotFoundError
from ..tools import generate_token

bp = Blueprint("auth")
logger = getLogger(__name__)
JWT_EXPIRATION_TIME = timedelta(seconds=timeparse(config.webapi.JWT_EXPIRATION_TIME))

@bp.route("/register", methods=["POST"])
@require_fields({"username", "email", "password"})
async def register(_req, username, email, password):
    """Create a new account"""
    userid = uuid4()
    hashed_password = scrypt.encrypt(token_bytes(64), password, maxtime=0.1)
    await RDB.create_user(userid, username, email, hashed_password)
    logger.info("Account created: %s", userid)
    return json({"userid": str(userid)})

@bp.route("/", methods=["POST"])
@require_fields({"login", "password"})
async def login_(req, login, password):
    """Authenticate a user, on success create a new JSON Web Token"""
    try:
        user = await RDB.get_user_by_login(login)
    except NotFoundError as exc:
        logger.log(45, "User not found (IP: %s)", req.ip)
        raise NotFound("User not found") from exc

    try:
        scrypt.decrypt(user.password, password, encoding=None)
    except scrypt.error:
        logger.log(45, "Wrong password for user %s (IP: %s)", user.name, req.ip)
        raise Forbidden("Wrong password")

    jwt = jwtlib.encode({
        "iss": ClientType.WEBAPI.value,
        "sub": "webgames",
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + JWT_EXPIRATION_TIME,
        "jti": str(uuid4()),
        "typ": ClientType.ADMIN.value if user.isadmin else ClientType.PLAYER.value,
        "uid": str(user.userid),
        "nic": user.name
    }, config.webapi.JWT_SECRET, algorithm='HS256')

    logger.info("User connected: %s", user.userid)
    return json({"token": jwt})


@bp.route("/", methods=["DELETE"])
@authenticate({ClientType.PLAYER, ClientType.ADMIN})
async def logout(_req, jwt):
    """Disconnect a user by invalidating his JWT"""
    await KVS.revoke_token(jwt)

    # Kick user from user stream
    url = "{}/kick/{}/from/{}".format(
        config.webapi.MSQQUEUES_URL, jwt["uid"], MsgQueueType.USER.value)
    headers = {"Authorization": "Bearer: %s" % \
               generate_token(config.webapi.JWT_SECRET,
                              typ=ClientType.ADMIN.value)}
    async with HTTP.delete(url, headers=headers) as res:
        if res.status != 204:
            logger.error("Error calling url %s: %s %s",
                         url, res.status, res.reason)

    # Kick user out of his group
    url = "{}/kick/{}".format(config.webapi.GROUP_URL, jwt["uid"])
    headers = {"Authorization": "Bearer: %s" % \
               generate_token(config.webapi.JWT_SECRET,
                              typ=ClientType.ADMIN.value)}
    async with HTTP.delete(url, headers=headers) as res:
        if res.status not in [204, 404]:
            logger.error("Error calling url %s: %s %s",
                         url, res.status, res.reason)
    logger.info("User disconnected: %s", jwt["jti"])
    return text("", status=204)
