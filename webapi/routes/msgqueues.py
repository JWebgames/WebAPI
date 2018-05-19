import asyncio
from contextlib import suppress
from logging import getLogger
from operator import methodcaller
from collections import defaultdict
from sanic import Blueprint
from sanic.response import stream
from sanic.exceptions import InvalidUsage
from ..server import app
from ..exceptions import PlayerNotInParty, PlayerNotInGroup
from ..middlewares import authenticate, require_fields
from ..storage import drivers
from ..storage.models import ClientType, MsgQueueType
from ..tools import async_partial

bp = Blueprint("msgqueues")
logger = getLogger(__name__)
tasks = []
stop_events = []

async def heartbeat(res, stop_event):
    logger.info("Start beating on %s", res)
    with suppress(asyncio.CancelledError):
        while True:
            await asyncio.sleep(30)
            if res.transport.is_closing():
                logger.debug("Transport %s closed", res.transport)
                stop_event.set()
                break
            res.write('{"type":"heartbeat"}')
            res.write(chr(30))  # ascii unit separator
    logger.info("Stop beating on %s", res)


async def sub_proxy(res, stop_event, queue, id_):
    logger.info("%s subscribed to queue %s:%s", res, queue, id_)
    with suppress(asyncio.CancelledError):
        for msg in drivers.KVS.recv_messages(queue, id_):
            if res.transport.is_closing():
                logger.debug("Transport %s closed", res.transport)
                stop_event.set()
                break
            logger.debug("Send message %s from queue %s:%s to %s",
                         msg, queue, id_, res)
            res.write(msg)
            res.write(chr(30))  # ascii unit separator
    logger.info("%s's subscribtion to queue %s ended", res, queue)


async def stream_until_event_is_set(res, func):
    stop_event = asyncio.Event()
    func_task = asyncio.ensure_future(func(res, stop_event))
    hb_task = asyncio.ensure_future(heartbeat(res, stop_event))

    stop_events.append(stop_event)
    tasks.extend([func_task, hb_task])

    with suppress(asyncio.CancelledError):
        await stop_event.wait()
    func_task.cancel()
    hb_task.cancel()

    stop_events.remove(stop_event)
    tasks.remove(func_task)
    tasks.remove(hb_task)


@bp.route("/user", methods=["GET"])
@authenticate({ClientType.PLAYER, ClientType.ADMIN})
async def get_user_msg(req, jwt):
    greetings(MsgQueueType.USER.value, user["jwt"])
    return stream(async_partial(stream_until_event_is_set,
        func=async_partial(sub_proxy(queue=MsgQueueType.PLAYER.value,
                                     id_=jwt["uid"]))))
    

@bp.route("/group", methods=["GET"])
@authenticate({ClientType.PLAYER, ClientType.ADMIN})
async def get_group_msg(req, jwt):
    user = await drivers.KVS.get_user(jwt["uid"])
    if user.groupid is None:
        raise PlayerNotInGroup()

    greetings(MsgQueueType.PARTY.value, user.partyid)
    return stream(async_partial(stream_until_event_is_set,
        func=async_partial(sub_proxy(queue=MsgQueueType.GROUP.value,
                                     id_=user.groupid))))

@bp.route("/party", methods=["GET"])
@authenticate({ClientType.PLAYER, ClientType.ADMIN})
async def get_party_msg(req, jwt):
    user = await drivers.KVS.get_user(jwt["uid"])
    if user.partyid is None:
        raise PlayerNotInParty()

    greetings(MsgQueueType.GROUP.value, user.groupid)
    subfunc = 
    return stream(async_partial(stream_until_event_is_set,
        func=async_partial(sub_proxy(queue=MsgQueueType.PARTY.value,
                                     id_=user.partyid))))

def greetings(queue, id_):
    payload = {"type":"server:notice","notice":"hello %d" % queue.value}
    coro = drivers.KVS.send_message(queue, id_, payload)
    asyncio.get_event_loop().call_later(0.2, asyncio.ensure_future, coro)

async def close_all_connections(_app, _loop):
    logger.info("Closing all streaming connections...")
    for task in tasks.copy():
        task.cancel()
    for event in stop_events.copy():
        event.set()
