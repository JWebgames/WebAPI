from logging import getLogger
from sanic import Blueprint
from sanic.response import json, text
from ..middlewares import authenticate, require_fields
from ..storage import drivers 
from ..storage.models import ClientType, MsgQueueType
from json import loads as json_loads

bp = Blueprint("groups")
logger = getLogger(__name__)


@bp.route("/", methods=["GET"])
@authenticate({ClientType.PLAYER, ClientType.ADMIN})
async def group_state(req, groupid, jwt):
    group = await drivers.KVS.get_group_of_user(jwt["uid"])
    return json(group.asdict())


@bp.route("/create/<gameid>", methods=["POST"])
@authenticate({ClientType.PLAYER, ClientType.ADMIN})
async def create(req, gameid, jwt):
    groupid = await drivers.KVS.create_group(jwt["uid"], gameid)
    return json({"groupid": str(groupid)})


@bp.route("/invite/<userid>", methods=["GET"])
@authenticate({ClientType.PLAYER, ClientType.ADMIN})
async def invite(req, userid, jwt):
    user = await drivers.KVS.get_user(jwt["uid"])
    group = await drivers.KVS.get_group(user.groupid)
    game = await drivers.RDB.get_game_by_id(group.gameid)

    payload = {"type": "group:invitation recieved",
               "from": {
                   "userid": jwt["uid"],
                   "username": jwt.get("nic")},
               "to": {
                   "groupid": str(user.groupid),
                   "gameid": str(game.gameid),
                   "gamename": game.name
               }}
    await drivers.KVS.send_message(MsgQueueType.USER, userid, payload)
    return text("", status=204)


@bp.route("/join/<groupid>", methods=["GET"])
@authenticate({ClientType.PLAYER, ClientType.ADMIN})
async def join(req, groupid, jwt):
    await drivers.KVS.join_group(groupid, jwt["uid"])

    user = await drivers.KVS.get_user(jwt["uid"])
    payload = {"type": "group:user joined",
               "user": {
                   "userid": jwt["uid"],
                   "username": jwt.get("nic")
               }}
    await drivers.KVS.send_message(MsgQueueType.GROUP, user.groupid, payload)
    return text("", status=204)


@bp.route("/leave", methods=["GET"])
@authenticate({ClientType.PLAYER, ClientType.ADMIN})
async def leave(req, jwt):
    user = await drivers.KVS.get_user(jwt["uid"])
    await drivers.KVS.leave_group(jwt["uid"])

    payload = {"type": "group:user left",
               "user": {
                   "userid": jwt["uid"],
                   "username": jwt.get("nic")
               }}
    await drivers.KVS.send_message(MsgQueueType.GROUP, user.groupid, payload)
    return text("", status=204)


@bp.route("/ready", methods=["GET"])
@authenticate({ClientType.PLAYER, ClientType.ADMIN})
async def ready(req, jwt):
    await drivers.KVS.mark_as_ready(jwt["uid"])

    user = await drivers.KVS.get_user(jwt["uid"])
    payload = {"type": "group:user is ready",
               "user": {
                   "userid": jwt["uid"],
                   "username": jwt.get("nic")
               }}
    await drivers.KVS.send_message(MsgQueueType.GROUP, user.groupid, payload)
    return text("", status=204)


@bp.route("/ready", methods=["DELETE"])
@authenticate({ClientType.PLAYER, ClientType.ADMIN})
async def notready(req, jwt):
    await drivers.KVS.mark_as_not_ready(jwt["uid"])

    user = await drivers.KVS.get_user(jwt["uid"])
    payload = {"type": "group:user is not ready",
               "user": {
                   "userid": jwt["uid"],
                   "username": jwt.get("nic")
               }}
    await drivers.KVS.send_message(MsgQueueType.GROUP, user.groupid, payload)
    return text("", status=204)


@bp.route("/start", methods=["GET"])
@authenticate({ClientType.PLAYER, ClientType.ADMIN})
async def start(req, jwt):
    user = await drivers.KVS.get_user(jwt["uid"])
    await drivers.KVS.join_queue(user.groupid)

    payload = {"type":"group:queue joined"}
    await drivers.KVS.send_message(MsgQueueType.GROUP, user.groupid, payload)
    return text("", status=204)
