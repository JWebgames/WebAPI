from datetime import datetime, timedelta
from logging import getLogger
from secrets import token_bytes
import jwt as jwtlib
import scrypt
from pytimeparse import parse as timeparse
from sanic import Blueprint
from sanic.exceptions import Forbidden
from sanic.response import json, json
from ..config import webapi
from ..middlewares import authenticate, require_fields, ClientType
from .. import database

bp = Blueprint("auth")
logger = getLogger(__name__)
JWT_EXPIRATION_TIME = timedelta(timeparse(webapi.JWT_EXPIRATION_TIME))

@bp.route("/register", methods=["POST"])
@require_fields({"username", "email", "password"})
async def register(req, username, email, password):
    userid = uuid4()
    hashed_password = scrypt.encrypt(token_bytes(64), password)
    await database.RDB.create_user(userid,
                                   username,
                                   email,
                                   hashed_password,
                                   isadmin=False)

@bp.route("/login", methods=["POST"])
@require_fields({"login", "password"})
async def login(req, login, password):
    user = await database.RDB.get_user_by_login(login)
    if user is None:
        logger.log(45, "User not found (IP: %s)", req.ip)
        raise NotFound("User not found")

    try:
        scrypt.decrypt(password, user.password, maxtime=0.5)
    except scrypt.error:
        logger.log(45, "Wrong password for user %s (IP: %s)", user.name, req.ip)
        raise Forbidden("Wrong password")

    jwt = jwtlib.encode({
        "iss": ClientType.WEBAPI.value,
        "sub": "webgames",
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + JWT_EXPIRATION_TIME,
        "tid": str(uuid4()),
        "typ": ClientType.ADMIN.value if user["isadmin"] else ClientType.USER.value,
        "uid": str(user["userid"])
    }, webapi.JWT_SECRET)

    return json({"token": jwt})


@bp.route("/logout", methods=["GET"])
@authenticate({ClientType.PLAYER, ClientType.ADMIN})
async def logout(req, jwt):
    await database.KVS.revoke_token(jwt["tid"])
    return json({})
