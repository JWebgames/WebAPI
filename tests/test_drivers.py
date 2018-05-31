import asyncio
import json
from uuid import uuid4, UUID
from logging import getLogger
from unittest import TestCase
from asynctest import CoroutineMock
from random import randint

from webapi.config import webapi
from webapi.server import connect_to_postgres, disconnect_from_postgres, \
                          connect_to_redis, disconnect_from_redis
from webapi.storage import drivers
from webapi.tools import lruc
from webapi.exceptions import PlayerInGroupAlready, \
                              PlayerNotInGroup, \
                              GroupDoesntExist, \
                              WrongGroupState, \
                              GroupIsFull, \
                              GroupNotReady
from webapi.storage.models import State, MsgQueueType


loop = asyncio.get_event_loop()
logger = getLogger(__name__)


class TestRDB(TestCase):
    """Test case for storage.drivers.RelationalDB"""
    def setUp(self):
        try:
            if webapi.PRODUCTION:
                lruc(asyncio.gather(connect_to_postgres(None, loop),
                            connect_to_redis(None, loop)))
            else:
                drivers.RDB = drivers.SQLite()
                drivers.KVS = drivers.InMemory()

            userid = uuid4()
            lruc(drivers.RDB.create_user(
                userid, "toto", "toto@example.com", b"suchpasssword"))
            self.user = lruc(drivers.RDB.get_user_by_login("toto"))
            gameid = lruc(drivers.RDB.create_game("bomberman", self.user.userid, 4))
            self.game = lruc(drivers.RDB.get_game_by_id(gameid))
        except:
            logger.exception("Error in setUp RDB")

    def tearDown(self):
        try:
            if webapi.PRODUCTION:
                lruc(drivers.RDB.conn.fetch("TRUNCATE tbusers CASCADE"))
                lruc(drivers.RDB.conn.fetch("TRUNCATE tbgames CASCADE"))
                lruc(drivers.KVS.redis.flushdb())
                lruc(asyncio.gather(disconnect_from_postgres(None, loop),
                            disconnect_from_redis(None, loop)))
            else:
                drivers.RDB.conn.close()

            self.user = None
            self.game = None
        except:
            logger.exception("Error in teamDown RDB")

    def test_create_retrieve_user(self):
        """Create a user and retrieve him, they should be the same"""
        pass

    def test_create_game(self):
        """Create a game a retrieve it, they should be the same"""
        pass


class TestMatchMaker(TestCase):
    """Test case for function related to the Match Maker"""
    def setUp(self):
        try:
            if webapi.PRODUCTION:
                lruc(asyncio.gather(connect_to_postgres(None, loop),
                            connect_to_redis(None, loop)))
            else:
                drivers.RDB = drivers.SQLite()
                drivers.KVS = drivers.InMemory()

            userid = uuid4()
            lruc(drivers.RDB.create_user(
                userid, "toto", "toto@example.com", b"suchpasssword"))
            self.user = lruc(drivers.RDB.get_user_by_id(userid))
            gameid = lruc(drivers.RDB.create_game("bomberman", self.user.userid, 4))
            self.game = lruc(drivers.RDB.get_game_by_id(gameid))
        except:
            logger.exception("Error in setUp KVS")

    def tearDown(self):
        try:
            if webapi.PRODUCTION:
                lruc(drivers.RDB.conn.fetch("TRUNCATE tbusers CASCADE"))
                lruc(drivers.RDB.conn.fetch("TRUNCATE tbgames CASCADE"))
                lruc(drivers.KVS.redis.flushdb())
                lruc(asyncio.gather(disconnect_from_postgres(None, loop),
                            disconnect_from_redis(None, loop)))
            else:
                drivers.RDB.conn.close()

            self.user = None
            self.game = None
        except:
            logger.exception("Error in tearDown KVS")

    def test_start_game(self):
        """Make a match out of several groups of players"""

        drivers.KVS.start_game = CoroutineMock()

        player_1 = uuid4()
        player_2 = uuid4()
        player_3 = uuid4()
        player_4 = uuid4()
        player_5 = uuid4()
        player_6 = uuid4()

        group_1 = lruc(drivers.KVS.create_group(player_1, self.game.gameid))
        lruc(drivers.KVS.mark_as_ready(player_1))
        lruc(drivers.KVS.join_group(group_1, player_2))
        lruc(drivers.KVS.mark_as_ready(player_2))
        lruc(drivers.KVS.join_group(group_1, player_3))
        lruc(drivers.KVS.mark_as_ready(player_3))

        group_2 = lruc(drivers.KVS.create_group(player_4, self.game.gameid))
        lruc(drivers.KVS.mark_as_ready(player_4))
        lruc(drivers.KVS.join_group(group_2, player_5))
        lruc(drivers.KVS.mark_as_ready(player_5))

        group_3 = lruc(drivers.KVS.create_group(player_6, self.game.gameid))
        lruc(drivers.KVS.mark_as_ready(player_6))

        # 3 players join, need 4 to start
        queue_filled = lruc(drivers.KVS.join_queue(group_1))

        # 2 more players join, need 4 (3 & 2 don't fit 4)
        queue_filled = lruc(drivers.KVS.join_queue(group_2))

        # 1 more player join (3 & 1 fit)
        queue_filled = lruc(drivers.KVS.join_queue(group_3))

        group = lruc(drivers.KVS.get_group(group_3))
        drivers.KVS.start_game.assert_called_once_with(group.slotid)
        

    def test_create_group_while_alone(self):
        """Creating a group beeing alone must pass"""
        coro = drivers.KVS.create_group(self.user.userid, self.game.gameid)
        self.assertTrue(isinstance(lruc(coro), UUID))

    def test_create_group_while_in_group(self):
        """Creating a group beeing in a group must fail"""
        lruc(drivers.KVS.create_group(self.user.userid, self.game.gameid))
        coro = drivers.KVS.create_group(self.user.userid, self.game.gameid)
        self.assertRaises(PlayerInGroupAlready, lruc, coro)

    def test_join_group_while_in_group(self):
        """Joining a group beeing in a group must pass"""
        groupid = lruc(drivers.KVS.create_group(self.user.userid,
                                                self.game.gameid))
        coro = drivers.KVS.join_group(groupid, self.user.userid)
        self.assertRaises(PlayerInGroupAlready, lruc, coro)
    
    def test_leave_group_not_beeing_in(self):
        """Leaving a group the user is not in must fail"""
        player_2 = uuid4()
        groupid = lruc(drivers.KVS.create_group(self.user.userid,
                                                self.game.gameid))
        lruc(drivers.KVS.join_group(groupid, player_2))
        lruc(drivers.KVS.leave_group(self.user.userid))
        coro = drivers.KVS.leave_group(self.user.userid)
        self.assertRaises(PlayerNotInGroup, lruc, coro)

    def test_join_queued_group(self):
        """Joining a queued group should fail"""
        player_2 = uuid4()
        groupid = lruc(drivers.KVS.create_group(self.user.userid,
                                                self.game.gameid))
        lruc(drivers.KVS.mark_as_ready(self.user.userid))
        lruc(drivers.KVS.join_queue(groupid))
        coro = drivers.KVS.join_group(groupid, player_2)
        self.assertRaises(WrongGroupState, lruc, coro)

    def test_join_filled_group(self):
        """Joining a filled group should fail"""
        groupid = lruc(drivers.KVS.create_group(self.user.userid,
                                                self.game.gameid))
        for _ in range(3):
            lruc(drivers.KVS.join_group(groupid, uuid4()))
        coro = drivers.KVS.join_group(groupid, uuid4())
        self.assertRaises(GroupIsFull, lruc, coro)

    def test_join_leave_queue(self):
        """Join the queue and leave it a couple of time should pass"""
        groupid = lruc(drivers.KVS.create_group(self.user.userid,
                                                self.game.gameid))
        lruc(drivers.KVS.mark_as_ready(self.user.userid))
        group = lruc(drivers.KVS.get_group(groupid))
        self.assertEqual(group.state, State.GROUP_CHECK)

        # Join
        lruc(drivers.KVS.join_queue(groupid))
        group = lruc(drivers.KVS.get_group(groupid))
        self.assertEqual(group.state, State.IN_QUEUE)

        # Leave
        lruc(drivers.KVS.leave_queue(groupid))
        group = lruc(drivers.KVS.get_group(groupid))
        self.assertEqual(group.state, State.GROUP_CHECK)

        # Join
        lruc(drivers.KVS.join_queue(groupid))
        group = lruc(drivers.KVS.get_group(groupid))
        self.assertEqual(group.state, State.IN_QUEUE)

        # Leave
        lruc(drivers.KVS.leave_queue(groupid))
        group = lruc(drivers.KVS.get_group(groupid))
        self.assertEqual(group.state, State.GROUP_CHECK)

    def test_clear_ready_while_queued(self):
        """Mark a player as not ready while in queue should leave the queue"""
        groupid = lruc(drivers.KVS.create_group(self.user.userid,
                                                self.game.gameid))
        lruc(drivers.KVS.mark_as_ready(self.user.userid))
        lruc(drivers.KVS.join_queue(groupid))
        lruc(drivers.KVS.mark_as_not_ready(self.user.userid))
        group = lruc(drivers.KVS.get_group(groupid))
        self.assertEqual(group.state, State.GROUP_CHECK)
    
    def test_mark_unmark_ready(self):
        """Test mark_as_ready/mark_as_not_ready on a couple of game state"""
        coro = drivers.KVS.mark_as_ready(self.user.userid)
        self.assertRaises(PlayerNotInGroup, lruc, coro)

        groupid = lruc(drivers.KVS.create_group(self.user.userid,
                                                self.game.gameid))
        lruc(drivers.KVS.mark_as_ready(self.user.userid))
        lruc(drivers.KVS.join_queue(groupid))
        coro = drivers.KVS.mark_as_ready(self.user.userid)
        self.assertRaises(WrongGroupState, lruc, coro)
        lruc(drivers.KVS.mark_as_not_ready(self.user.userid))

    def test_join_queue_not_all_ready(self):
        """Joining the queue while all the players are not ready should fail"""
        player_2 = uuid4()
        groupid = lruc(drivers.KVS.create_group(self.user.userid,
                                                self.game.gameid))
        lruc(drivers.KVS.mark_as_ready(self.user.userid))
        lruc(drivers.KVS.join_group(groupid, player_2))
        coro = drivers.KVS.join_queue(groupid)
        self.assertRaises(GroupNotReady, lruc, coro)

class TestMessager(TestCase):
    """Test case for Messager"""
    def setUp(self):
        try:
            if webapi.PRODUCTION:
                lruc(asyncio.gather(connect_to_postgres(None, loop),
                                    connect_to_redis(None, loop)))
            else:
                drivers.RDB = drivers.SQLite()
                drivers.KVS = drivers.InMemory()
            drivers.MSG = drivers.Messager()

            userid = uuid4()
            lruc(drivers.RDB.create_user(
                userid, "toto", "toto@example.com", b"suchpasssword"))
            self.user = lruc(drivers.RDB.get_user_by_id(userid))
            gameid = lruc(drivers.RDB.create_game("bomberman", self.user.userid, 4))
            self.game = lruc(drivers.RDB.get_game_by_id(gameid))
        except:
            logger.exception("Error in setUp KVS")

    def tearDown(self):
        try:
            if webapi.PRODUCTION:
                lruc(drivers.RDB.conn.fetch("TRUNCATE tbusers CASCADE"))
                lruc(drivers.RDB.conn.fetch("TRUNCATE tbgames CASCADE"))
                lruc(drivers.KVS.redis.flushdb())
                lruc(asyncio.gather(disconnect_from_postgres(None, loop),
                            disconnect_from_redis(None, loop)))
            else:
                drivers.RDB.conn.close()
            
            drivers.MSG.close()

            self.user = None
            self.game = None
        except:
            logger.exception("Error in tearDown KVS")
    
    def test_send_recv_messages(self):
        async def feeder(message):
            await drivers.MSG.send_message(
                MsgQueueType.USER, self.user.userid, message)

        async def reciever():
            gen = drivers.MSG.recv_messages(MsgQueueType.USER, self.user.userid)
            async for sentinel in gen:
                logger.debug(sentinel)
                break
            async for msg in gen:
                logger.debug(msg)
                await gen.asend(sentinel)
            return msg

        payload = {"value": randint(0, 99)}
        asyncio.get_event_loop().call_later(0.1, asyncio.ensure_future, feeder(payload))
        self.assertEqual(json.loads(lruc(asyncio.wait_for(reciever(), 0.2))), payload)
      