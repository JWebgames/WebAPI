"""Groups route, create/invite/join groups"""

from logging import getLogger
from uuid import UUID
from sanic import Blueprint
from sanic.response import json, text
from sanic.exceptions import NotFound, InvalidUsage
from .. import config
from ..server import HTTP, RDB, KVS, MSG
from ..tools import generate_token
from ..middlewares import authenticate
from ..storage.models import ClientType, MsgQueueType
from ..exceptions import PlayerNotInGroup, GroupNotReady, WrongGroupState

bp = Blueprint("groups")
logger = getLogger(__name__)


@bp.route("/", methods=["GET"])
@authenticate({ClientType.PLAYER, ClientType.ADMIN})
async def group_state(_req, jwt):
    """Get the current group state of the player"""
    try:
        user = await KVS.get_user(jwt["uid"])
    except PlayerNotInGroup as exc:
        raise NotFound("Player not in group") from exc
    group = await KVS.get_group(user.groupid)
    jsonbody = user.asdict()
    jsonbody.update(group.asdict())
    jsonbody["members"] = [
        {"name": (await RDB.get_user_by_id(userid)).name,
         "ready": await KVS.is_user_ready(userid),
         "id": userid} for userid in jsonbody["members"]]
    del jsonbody["ready"]
    return json(jsonbody)


@bp.route("/create/<gameid:int>", methods=["POST"])
@authenticate({ClientType.PLAYER, ClientType.ADMIN})
async def create(_req, gameid, jwt):
    """Create a new group for the given game"""
    groupid = await KVS.create_group(jwt["uid"], gameid)
    return json({"groupid": str(groupid)})


@bp.route("/invite/byid/<userid>", methods=["POST"])
@authenticate({ClientType.PLAYER, ClientType.ADMIN})
async def invite_id(_req, userid, jwt):
    """Invite a player to the group given his id"""
    return await invite(userid, jwt)


@bp.route("/invite/byname/<user>", methods=["POST"])
@authenticate({ClientType.PLAYER, ClientType.ADMIN})
async def invite_name(_req, user, jwt):
    """Invite a player to the group given his name"""
    user = await RDB.get_user_by_login(user)
    return await invite(user.userid, jwt)

async def invite(userid, jwt):
    """Invite a player to the group given his id"""
    user = await KVS.get_user(jwt["uid"])
    group = await KVS.get_group(user.groupid)
    game = await RDB.get_game_by_id(group.gameid)

    payload = {"type": "group:invitation recieved",
               "from": {
                   "userid": jwt["uid"],
                   "username": jwt.get("nic")},
               "to": {
                   "groupid": str(user.groupid),
                   "gameid": str(game.gameid),
                   "gamename": game.name
               }}
    await MSG.send_message(MsgQueueType.USER, userid, payload)
    return text("", status=204)


@bp.route("/join/<groupid>", methods=["POST"])
@authenticate({ClientType.PLAYER, ClientType.ADMIN})
async def join(_req, groupid, jwt):
    """Join a group given its id"""
    await KVS.join_group(UUID(groupid), jwt["uid"])

    user = await KVS.get_user(jwt["uid"])
    payload = {"type": "group:user joined",
               "user": {
                   "userid": jwt["uid"],
                   "username": jwt.get("nic")
               }}
    await MSG.send_message(MsgQueueType.GROUP, user.groupid, payload)
    return text("", status=204)


@bp.route("/leave", methods=["DELETE"])
@authenticate({ClientType.PLAYER, ClientType.ADMIN})
async def leave(_req, jwt):
    """Leave the current group"""
    await do_leave(jwt["uid"], jwt["nic"])
    return text("", status=204)

@bp.route("/kick/<userid>", methods=["DELETE"])
@authenticate({ClientType.ADMIN})
async def kick(_req, userid, jwt):
    """Kick a player out of his group"""
    try:
        await do_leave(userid, None)
    except PlayerNotInGroup:
        logger.warning("Cannot kick a player who is not in a group")
    except WrongGroupState:
        logger.warning("Cannot kick a player playing")
    return text("", status=204)

async def do_leave(userid, username):
    """Remove a user from his group, close its group stream"""
    user = await KVS.get_user(userid)
    await KVS.leave_group(userid)

    # Kick user from group stream
    url = "{}/kick/{}/from/{}".format(
        config.webapi.MSGQUEUES_URL, userid, MsgQueueType.GROUP.value)
    headers = {"Authorization": "Bearer: %s" % \
               generate_token(config.webapi.JWT_SECRET,
                              typ=ClientType.ADMIN.value)}
    async with HTTP.delete(url, headers=headers) as res:
        if res.status != 204:
            logger.error("Error calling url %s: %s %s",
                         url, res.status, res.reason)

    payload = {"type": "group:user left",
               "user": {
                   "userid": userid,
                   "username": username
               }}
    await MSG.send_message(MsgQueueType.GROUP, user.groupid, payload)

@bp.route("/ready", methods=["POST"])
@authenticate({ClientType.PLAYER, ClientType.ADMIN})
async def ready(_req, jwt):
    """Mark the player as ready"""
    await KVS.mark_as_ready(jwt["uid"])

    user = await KVS.get_user(jwt["uid"])
    payload = {"type": "group:user is ready",
               "user": {
                   "userid": jwt["uid"],
                   "username": jwt.get("nic")
               }}
    await MSG.send_message(MsgQueueType.GROUP, user.groupid, payload)
    return text("", status=204)


@bp.route("/ready", methods=["DELETE"])
@authenticate({ClientType.PLAYER, ClientType.ADMIN})
async def notready(_req, jwt):
    """Mark the player as not ready"""
    await KVS.mark_as_not_ready(jwt["uid"])

    user = await KVS.get_user(jwt["uid"])
    payload = {"type": "group:user is not ready",
               "user": {
                   "userid": jwt["uid"],
                   "username": jwt.get("nic")
               }}
    await MSG.send_message(MsgQueueType.GROUP, user.groupid, payload)
    return text("", status=204)


@bp.route("/start", methods=["POST"])
@authenticate({ClientType.PLAYER, ClientType.ADMIN})
async def start(_req, jwt):
    """Place the group into the match maker"""
    user = await KVS.get_user(jwt["uid"])
    try:
        await KVS.join_queue(user.groupid)
    except GroupNotReady as exc:
        raise InvalidUsage("The group is not ready yet") from exc

    payload = {"type":"group:queue joined"}
    await MSG.send_message(MsgQueueType.GROUP, user.groupid, payload)
    return text("", status=204)
