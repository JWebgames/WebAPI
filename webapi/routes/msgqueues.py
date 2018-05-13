from logging import getLogger
from sanic import Blueprint
from sanic.response import json
from ..exceptions import PlayerNotInParty
from ..middlewares import authenticate, require_fields
from ..storage import drivers
from ..storage.models import ClientType, MsgQueueType

bp = Blueprint("msgqueues")
logger = getLogger(__name__)

@bp.route("/user", methods=["GET"])
@authenticate({ClientType.PLAYER, ClientType.ADMIN})
async def get_user_msg(req, jwt):
    msgs = await drivers.KVS.recv_messages(MsgQueueType.USER, jwt["uid"])
    return json(list(map(methodcaller("_asdict"), msgs)))

@bp.route("/group", methods=["GET"])
@authenticate({ClientType.PLAYER, ClientType.ADMIN})
async def get_user_msg(req, jwt):
    user = await drivers.KVS.get_user(jwt["uid"])
    msgs = await drivers.KVS.recv_messages(MsgQueueType.GROUP, user.groupid)
    return json(list(map(methodcaller("_asdict"), msgs)))

@bp.route("/user", methods=["GET"])
@authenticate({ClientType.PLAYER, ClientType.ADMIN})
async def get_user_msg(req, jwt):
    user = await drivers.KVS.get_user(jwt["uid"])
    if user.partyid is None:
        raise PlayerNotInParty()

    msgs = await drivers.KVS.recv_messages(MsgQueueType.USER, user.partyid)
    return json(list(map(methodcaller("_asdict"), msgs)))
