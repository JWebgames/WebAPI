from logging import getLogger
from sanic import Blueprint
from sanic.response import json
from ..middlewares import authenticate, require_fields
from ..storage import drivers 
from ..storage.models import ClientType

bp = Blueprint("groups")
logger = getLogger(__name__)

@bp.route("/create/<gameid>", methods=["POST"])
@authenticate({ClientType.PLAYER, ClientType.ADMIN})
async def create(req, gameid, jwt):
    groupid = await drivers.KVS.create_group(jwt["uid"], gameid)
    return json({"groupid": str(groupid)})

@bp.route("/invite/<userid>", methods=["GET"])
@authenticate({ClientType.PLAYER, ClientType.ADMIN})
async def invite(req, userid, jwt):
    pass

@bp.route("/leave", methods=["GET"])
@authenticate({ClientType.PLAYER, ClientType.ADMIN})
async def leave(req, jwt):
    await drivers.KVS.leave_group(jwt["uid"])

@bp.route("/<groupid>", methods=["GET"])
@authenticate({ClientType.PLAYER, ClientType.ADMIN})
async def group_state(req, groupid, jwt):
    group = await drivers.KVS.get_group(jwt["uid"])
    return json(group.asdict())

@bp.route("/ready", methods=["GET"])
@authenticate({ClientType.PLAYER, ClientType.ADMIN})
async def ready(req, jwt):
    await drivers.KVS.is_ready(jwt["uid"])
    return json({})