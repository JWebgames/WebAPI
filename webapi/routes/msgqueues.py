"Subscription bridge"

import asyncio
from contextlib import suppress
from logging import getLogger
from collections import defaultdict
from sanic import Blueprint
from sanic.response import stream, text
from ..exceptions import PlayerNotInParty, PlayerNotInGroup
from ..middlewares import authenticate
from ..server import MSG, KVS
from ..storage.models import ClientType, MsgQueueType
from ..tools import async_partial

bp = Blueprint("msgqueues")
logger = getLogger(__name__)
tasks = []
stop_events = {
    MsgQueueType.USER.value: defaultdict(list),
    MsgQueueType.GROUP.value: defaultdict(list),
    MsgQueueType.PARTY.value: defaultdict(list),
}

async def heartbeat(res, stop_event):
    """Each 30 seconds, write on the transport"""
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


async def sub_bridge(res, stop_event, queue, id_):
    """Send message from the messager on the http streaming"""
    logger.info("New subscribtion to queue %s:%s", queue.value, id_)
    reciever = MSG.recv_messages(queue, id_)
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
    except Exception as exc:
        logger.error("Catch %s, cleanup and reraising...", exc)
        await reciever.asend(sentinel)
        async for _ in reciever: pass
        raise
    logger.info("Subscribtion to queue %s:%s over", queue.value, id_)


async def stream_until_event_is_set(res, userid, queue, queueid):
    """
    Stream manager, start the bridge and heartbeat, wait for a stop
    event or the cancallation of the task to do cleanup and close
    the underlying transport
    """
    stop_event = asyncio.Event()
    sf_task = asyncio.ensure_future(sub_bridge(res, stop_event, queue, queueid))
    hb_task = asyncio.ensure_future(heartbeat(res, stop_event))

    stop_events[queue.value][userid].append(stop_event)
    tasks.extend([sf_task, hb_task])

    with suppress(asyncio.CancelledError):
        await stop_event.wait()
    sf_task.cancel()
    hb_task.cancel()

    stop_events[queue.value][userid].remove(stop_event)
    if not stop_events[queue.value][userid]:
        del stop_events[queue.value][userid]
    tasks.remove(sf_task)
    tasks.remove(hb_task)


@bp.route("/user", methods=["GET"])
@authenticate({ClientType.PLAYER, ClientType.ADMIN})
async def get_user_msg(_req, jwt):
    """Create a HTTP Stream bridge for an user"""
    greetings(MsgQueueType.USER, jwt["uid"])
    return stream(async_partial(stream_until_event_is_set,
                                userid=jwt["uid"],
                                queue=MsgQueueType.USER,
                                queueid=jwt["uid"]))

@bp.route("/group", methods=["GET"])
@authenticate({ClientType.PLAYER, ClientType.ADMIN})
async def get_group_msg(_req, jwt):
    """Create a HTTP Stream bridge for a group"""
    user = await KVS.get_user(jwt["uid"])
    if user.groupid is None:
        raise PlayerNotInGroup()

    greetings(MsgQueueType.GROUP, user.groupid)
    return stream(async_partial(stream_until_event_is_set,
                                userid=jwt["uid"],
                                queue=MsgQueueType.GROUP,
                                queueid=str(user.groupid)))

@bp.route("/party", methods=["GET"])
@authenticate({ClientType.PLAYER, ClientType.ADMIN})
async def get_party_msg(_req, jwt):
    """Create a HTTP Stream bridge for a party"""
    user = await KVS.get_user(jwt["uid"])
    if user.partyid is None:
        raise PlayerNotInParty()

    greetings(MsgQueueType.PARTY, user.groupid)
    return stream(async_partial(stream_until_event_is_set,
                                userid=jwt["uid"],
                                queue=MsgQueueType.PARTY,
                                queueid=str(user.partyid)))

@bp.route("/kick/<userid>/from/<queue>", methods=["DELETE"])
@authenticate({ClientType.ADMIN})
async def kick_user(_req, queue, userid, jwt):
    """Close stream"""
    logger.info("Kicking user %s from queue %s", userid, queue)
    for event in stop_events[queue][userid].copy():
        event.set()
    return text("", status=204)

def greetings(queue, id_):
    """Send a dummy message"""
    payload = {"type": "server:notice",
               "notice": "subed to {}:{!s}".format(queue.value, id_)}
    coro = MSG.send_message(queue, id_, payload)
    asyncio.get_event_loop().call_later(0.2, asyncio.ensure_future, coro)

async def close_all_connections(_app, _loop):
    """Cleanup"""
    logger.info("Closing all streaming connections...")
    for task in tasks.copy():
        task.cancel()
    for queue in stop_events:
        for id_ in stop_events[queue].copy():
            for event in stop_events[queue][id_].copy():
                event.set()
