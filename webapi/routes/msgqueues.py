from asyncio import ensure_future
from logging import getLogger
from operator import methodcaller
from sanic import Blueprint
from sanic.response import stream
from sanic.exceptions import InvalidUsage
from ..exceptions import PlayerNotInParty, PlayerNotInGroup
from ..middlewares import authenticate, require_fields
from ..storage import drivers
from ..storage.models import ClientType, MsgQueueType

bp = Blueprint("msgqueues")
logger = getLogger(__name__)

async def feeder(res, queue):
    chan = (await drivers.KVS.redis.subscribe(queue))[0]
    while await chan.wait_message():
        msg = await chan.get(encoding="utf-8")
        logger.debug("Send message \"%s\" from queue %s to %s", queue, msg, res)
        res.write(msg)
        res.write(chr(30))  # ascii unit separator

@bp.route("/user", methods=["GET"])
@authenticate({ClientType.PLAYER, ClientType.ADMIN})
async def get_user_msg(req, jwt):
    queue = drivers.Redis.msgqueue_key.format(MsgQueueType.USER.value, jwt["uid"])
    async def recv(res):
        await feeder(res, queue)
    
    ensure_future(drivers.KVS.send_message(MsgQueueType.USER.value, jwt["uid"], {"type": "server:notice", "notice": "hello"}))
    return stream(recv)
    

@bp.route("/group", methods=["GET"])
@authenticate({ClientType.PLAYER, ClientType.ADMIN})
async def get_group_msg(req, jwt):
    user = await drivers.KVS.get_user(jwt["uid"])
    if user.groupid is None:
        raise InvalidUsage() from PlayerNotInGroup

    queue = drivers.Redis.msgqueue_key.format(MsgQueueType.GROUP.value, user.groupid)
    async def recv(res):
        await feeder(res, queue)
    return stream(recv)

@bp.route("/party", methods=["GET"])
@authenticate({ClientType.PLAYER, ClientType.ADMIN})
async def get_party_msg(req, jwt):
    user = await drivers.KVS.get_user(jwt["uid"])
    if user.partyid is None:
        raise InvalidUsage() from PlayerNotInParty()

    queue = drivers.Redis.msgqueue_key.format(MsgQueueType.PARTY.value, user.groupid)
    async def recv(res):
        await feeder(res, queue)
    return stream(recv)
