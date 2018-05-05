from datetime import datetime, timedelta
from logging import getLogger
from uuid import uuid4
from secrets import token_bytes
import jwt as jwtlib
import scrypt
from pytimeparse import parse as timeparse
from sanic import Blueprint
from sanic.exceptions import Forbidden, NotFound
from sanic.response import json
from .. import config
from ..middlewares import authenticate, require_fields, ClientType
from ..storage import drivers 

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

@bp.route("/login", methods=["POST"])
@require_fields({"login", "password"})
async def login(req, login, password):
    user = await drivers.RDB.get_user_by_login(login)
    if user is None:
        logger.log(45, "User not found (IP: %s)", req.ip)
        raise NotFound("User not found")

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


@bp.route("/logout", methods=["GET"])
@authenticate({ClientType.PLAYER, ClientType.ADMIN})
async def logout(req, jwt):
    await drivers.KVS.revoke_token(jwt)
    logger.info("User disconnected: %s", jwt["jti"])
    return json({})
