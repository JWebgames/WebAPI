from contextlib import suppress
from logging import getLogger
from uuid import UUID
from sanic import Blueprint
from sanic.response import json, text
from sanic.exceptions import NotFound, InvalidUsage
from .. import config
from .. import server
from ..tools import generate_token
from ..middlewares import authenticate, require_fields
from ..storage import drivers 
from ..storage.models import ClientType, MsgQueueType
from ..exceptions import PlayerNotInGroup, GroupNotReady, WrongGroupState
from json import loads as json_loads

bp = Blueprint("groups")
logger = getLogger(__name__)


@bp.route("/", methods=["GET"])
@authenticate({ClientType.PLAYER, ClientType.ADMIN})
async def group_state(req, jwt):
    try:
        user = await drivers.KVS.get_user(jwt["uid"])
    except PlayerNotInGroup as exc:
        raise NotFound("Player not in group") from exc
    group = await drivers.KVS.get_group(user.groupid)
    jsonbody = user.asdict()
    jsonbody.update(group.asdict())
    jsonbody["members"] = [
        {"name": (await drivers.RDB.get_user_by_id(userid)).name,
         "ready": await drivers.KVS.is_user_ready(userid),
         "id": userid} for userid in jsonbody["members"]]
    del jsonbody["ready"]
    return json(jsonbody)


@bp.route("/create/<gameid:int>", methods=["POST"])
@authenticate({ClientType.PLAYER, ClientType.ADMIN})
async def create(req, gameid, jwt):
    groupid = await drivers.KVS.create_group(jwt["uid"], gameid)
    return json({"groupid": str(groupid)})


@bp.route("/invite/byid/<userid>", methods=["POST"])
@authenticate({ClientType.PLAYER, ClientType.ADMIN})
async def invite_id(req, userid, jwt):
    return await invite(userid, jwt)


@bp.route("/invite/byname/<user>", methods=["POST"])
@authenticate({ClientType.PLAYER, ClientType.ADMIN})
async def invite_name(req, user, jwt):
    user = await drivers.RDB.get_user_by_login(user)
    return await invite(user.userid, jwt)

async def invite(userid, jwt):
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
    await drivers.MSG.send_message(MsgQueueType.USER, userid, payload)
    return text("", status=204)


@bp.route("/join/<groupid>", methods=["POST"])
@authenticate({ClientType.PLAYER, ClientType.ADMIN})
async def join(req, groupid, jwt):
    await drivers.KVS.join_group(UUID(groupid), jwt["uid"])

    user = await drivers.KVS.get_user(jwt["uid"])
    payload = {"type": "group:user joined",
               "user": {
                   "userid": jwt["uid"],
                   "username": jwt.get("nic")
               }}
    await drivers.MSG.send_message(MsgQueueType.GROUP, user.groupid, payload)
    return text("", status=204)


@bp.route("/leave", methods=["DELETE"])
@authenticate({ClientType.PLAYER, ClientType.ADMIN})
async def leave(req, jwt):
    return await do_leave(jwt["uid"], jwt["nic"])

@bp.route("/kick/<userid>", methods=["DELETE"])
@authenticate({ClientType.ADMIN})
async def kick(req, userid, jwt):
    with suppress(WrongGroupState):
        return await do_leave(userid, None)
    logger.warning("Cannot kick a player playing")
    return text("", status=204)

async def do_leave(userid, username):
    user = await drivers.KVS.get_user(userid)
    await drivers.KVS.leave_group(userid)

    # Kick user from group stream
    url = "{}/kick/{}/from/{}".format(
        config.webapi.MSQQUEUES_URL, userid, MsgQueueType.GROUP.value)
    headers = {"Authorization": "Bearer: %s" % \
               generate_token(config.webapi.JWT_SECRET,
                              typ=ClientType.ADMIN.value)}
    async with server.http_client.delete(url, headers=headers) as res:
        if res.status != 204:
            logger.error("Error calling url %s: %s %s",
                        url, res.status, res.reason)

    payload = {"type": "group:user left",
               "user": {
                   "userid": userid,
                   "username": username
               }}
    await drivers.MSG.send_message(MsgQueueType.GROUP, user.groupid, payload)
    return text("", status=204)

@bp.route("/ready", methods=["POST"])
@authenticate({ClientType.PLAYER, ClientType.ADMIN})
async def ready(req, jwt):
    await drivers.KVS.mark_as_ready(jwt["uid"])

    user = await drivers.KVS.get_user(jwt["uid"])
    payload = {"type": "group:user is ready",
               "user": {
                   "userid": jwt["uid"],
                   "username": jwt.get("nic")
               }}
    await drivers.MSG.send_message(MsgQueueType.GROUP, user.groupid, payload)
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
    await drivers.MSG.send_message(MsgQueueType.GROUP, user.groupid, payload)
    return text("", status=204)


@bp.route("/start", methods=["POST"])
@authenticate({ClientType.PLAYER, ClientType.ADMIN})
async def start(req, jwt):
    user = await drivers.KVS.get_user(jwt["uid"])
    try:
        await drivers.KVS.join_queue(user.groupid)
    except GroupNotReady as exc:
        raise InvalidUsage("The group is not ready yet") from exc

    payload = {"type":"group:queue joined"}
    await drivers.MSG.send_message(MsgQueueType.GROUP, user.groupid, payload)
    return text("", status=204)
