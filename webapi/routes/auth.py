import atexit
from asyncio import ensure_future
from contextlib import suppress
from datetime import datetime, timedelta
from logging import getLogger
from uuid import uuid4
from secrets import token_bytes
import jwt as jwtlib
import scrypt
from pytimeparse import parse as timeparse
from sanic import Blueprint
from sanic.exceptions import Forbidden, NotFound
from sanic.response import json, text
from .. import config
from .. import server
from ..middlewares import authenticate, require_fields
from ..storage import drivers
from ..storage.models import ClientType
from ..exceptions import NotFoundError, WrongGroupState, PlayerNotInGroup, WebAPIError
from ..tools import generate_token

bp = Blueprint("auth")
logger = getLogger(__name__)
JWT_EXPIRATION_TIME = timedelta(seconds=timeparse(config.webapi.JWT_EXPIRATION_TIME))

@bp.route("/register", methods=["POST"])
@require_fields({"username", "email", "password"})
async def register(req, username, email, password):
    userid = uuid4()
    hashed_password = scrypt.encrypt(token_bytes(64), password, maxtime=0.1)
    await drivers.RDB.create_user(userid, username, email, hashed_password)
    logger.info("Account created: %s", userid)
    return json({"userid": str(userid)})

@bp.route("/", methods=["POST"])
@require_fields({"login", "password"})
async def login(req, login, password):
    try:
        user = await drivers.RDB.get_user_by_login(login)
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
async def logout(req, jwt):
    await drivers.KVS.revoke_token(jwt)
    url = "{}/kick/{}".format(config.webapi.GROUP_URL, jwt["uid"])
    headers = {"Authorization": "Bearer: %s" % \
               generate_token(config.webapi.JWT_SECRET,
                              typ=ClientType.ADMIN.value)}
    async with server.http_client.delete(url, headers=headers) as res:
        if res.status not in [204, 404]:
            logger.error("Error calling url %s: %s %s",
                        url, res.status, res.reason)
    logger.info("User disconnected: %s", jwt["jti"])
    return text("", status=204)
