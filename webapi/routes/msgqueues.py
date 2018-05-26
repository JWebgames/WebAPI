import asyncio
from contextlib import suppress
from logging import getLogger
from operator import methodcaller
from collections import defaultdict
from sanic import Blueprint
from sanic.response import stream
from sanic.exceptions import InvalidUsage
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
    logger.debug("Start heart-beating on %s", res.transport)
    with suppress(asyncio.CancelledError):
        while True:
            await asyncio.sleep(30)
            if res.transport.is_closing():
                stop_event.set()
                break
            res.write('{"type":"heartbeat"}')
            res.write(chr(30))  # ascii unit separator
    logger.debug("Stop heart-beating on %s", res.transport)


async def sub_proxy(res, stop_event, queue, id_):
    logger.info("New subscribtion to queue %s:%s", queue.value, id_)
    reciever = drivers.MSG.recv_messages(queue, id_)
    async for sentinel in reciever: break  # sentinel = next(reciever)
    try:
        async for msg in reciever:
            if res.transport.is_closing():
                logger.debug("Transport %s closed", res.transport)
                stop_event.set()
                await reciever.asend(sentinel)
                continue
            logger.debug("Send message %s from queue %s:%s to %s",
                        msg, queue.value, id_, res)
            res.write(msg)
            res.write(chr(30))  # ascii unit separator
    except asyncio.CancelledError:
        pass
    finally:
        reciever.send(sentinel)
    logger.info("Subscribtion to queue %s:%s over", queue.value, id_)


async def stream_until_event_is_set(res, stream_func):
    stop_event = asyncio.Event()
    sf_task = asyncio.ensure_future(stream_func(res, stop_event))
    hb_task = asyncio.ensure_future(heartbeat(res, stop_event))

    stop_events.append(stop_event)
    tasks.extend([sf_task, hb_task])

    with suppress(asyncio.CancelledError):
        await stop_event.wait()
    sf_task.cancel()
    hb_task.cancel()

    stop_events.remove(stop_event)
    tasks.remove(sf_task)
    tasks.remove(hb_task)


@bp.route("/user", methods=["GET"])
@authenticate({ClientType.PLAYER, ClientType.ADMIN})
async def get_user_msg(req, jwt):
    greetings(MsgQueueType.USER, jwt["uid"])
    return stream(async_partial(stream_until_event_is_set,
        stream_func=async_partial(sub_proxy,
            queue=MsgQueueType.USER, id_=jwt["uid"])))
    

@bp.route("/group", methods=["GET"])
@authenticate({ClientType.PLAYER, ClientType.ADMIN})
async def get_group_msg(req, jwt):
    user = await drivers.KVS.get_user(jwt["uid"])
    if user.groupid is None:
        raise PlayerNotInGroup()

    greetings(MsgQueueType.GROUP, user.groupid)
    return stream(async_partial(stream_until_event_is_set,
        stream_func=async_partial(sub_proxy,
            queue=MsgQueueType.GROUP, id_=user.groupid)))

@bp.route("/party", methods=["GET"])
@authenticate({ClientType.PLAYER, ClientType.ADMIN})
async def get_party_msg(req, jwt):
    user = await drivers.KVS.get_user(jwt["uid"])
    if user.partyid is None:
        raise PlayerNotInParty()

    greetings(MsgQueueType.PARTY, user.groupid)
    return stream(async_partial(stream_until_event_is_set,
        stream_func=async_partial(sub_proxy,
            queue=MsgQueueType.PARTY, id_=user.partyid)))

def greetings(queue, id_):
    payload = {"type": "server:notice",
               "notice": "subed to {}:{!s}".format(queue.value, id_)}
    coro = drivers.KVS.send_message(queue, id_, payload)
    asyncio.get_event_loop().call_later(0.2, asyncio.ensure_future, coro)

async def close_all_connections(_app, _loop):
    logger.info("Closing all streaming connections...")
    for task in tasks.copy():
        task.cancel()
    for event in stop_events.copy():
        event.set()
