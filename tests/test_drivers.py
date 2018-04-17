from asyncio import get_event_loop, gather
from uuid import uuid4, UUID
from unittest import TestCase

from webapi.config import webapi
from webapi.server import connect_to_postgres, disconnect_from_postgres, \
                          connect_to_redis, disconnect_from_redis
from webapi.storage import drivers
from webapi.tools import lruc
from webapi.exceptions import PlayerInGroupAlready, \
                              PlayerNotInGroup, \
                              GroupDoesntExist, \
                              GroupInQueueAlready, \
                              GroupIsFull


loop = get_event_loop()


class TestRDB(TestCase):
    """Test case for storage.drivers.RelationalDB"""
    def setUp(self):
        if webapi.PRODUCTION:
            lruc(gather(connect_to_postgres(None, loop),
                        connect_to_redis(None, loop)))
        else:
            drivers.RDB = drivers.SQLite()
            drivers.KVS = drivers.InMemory()

        lruc(drivers.RDB.create_user(
            uuid4(), "toto", "toto@example.com", b"suchpasssword"))
        self.user = lruc(drivers.RDB.get_user_by_login("toto"))
        lruc(drivers.RDB.create_game("bomberman", self.user.userid, 4))
        self.game = lruc(drivers.RDB.get_game_by_name("bomberman"))

    def tearDown(self):
        if webapi.PRODUCTION:
            lruc(gather(disconnect_from_postgres(None, loop),
                        disconnect_from_redis(None, loop)))
        else:
            drivers.RDB.conn.close()

        self.user = None
        self.game = None

    def test_create_retrieve_user(self):
        """Create a user and retrieve him, they should be the same"""
        pass

    def test_create_game(self):
        """Create a game a retrieve it, they should be the same"""
        pass


class TestKVS(TestCase):
    """Test case for storage.drivers.KeyValueStore"""
    def setUp(self):
        if webapi.PRODUCTION:
            lruc(gather(connect_to_postgres(None, loop),
                        connect_to_redis(None, loop)))
        else:
            drivers.RDB = drivers.SQLite()
            drivers.KVS = drivers.InMemory()

        lruc(drivers.RDB.create_user(
            uuid4(), "toto", "toto@example.com", b"suchpasssword"))
        self.user = lruc(drivers.RDB.get_user_by_login("toto"))
        lruc(drivers.RDB.create_game("bomberman", self.user.userid, 4))
        self.game = lruc(drivers.RDB.get_game_by_name("bomberman"))

    def tearDown(self):
        if webapi.PRODUCTION:
            lruc(gather(disconnect_from_postgres(None, loop),
                        disconnect_from_redis(None, loop)))
        else:
            drivers.RDB.conn.close()

        self.user = None
        self.game = None

    def test_start_game(self):
        """Make a match out of several groups of players"""
        player_1 = uuid4()
        player_2 = uuid4()
        player_3 = uuid4()
        player_4 = uuid4()
        player_5 = uuid4()
        player_6 = uuid4()

        group_1 = lruc(drivers.KVS.create_group(player_1, self.game.gameid))
        lruc(drivers.KVS.join_group(group_1, player_2))
        lruc(drivers.KVS.join_group(group_1, player_3))

        group_2 = lruc(drivers.KVS.create_group(player_4, self.game.gameid))
        lruc(drivers.KVS.join_group(group_2, player_5))

        group_3 = lruc(drivers.KVS.create_group(player_6, self.game.gameid))

        # 3 players join, need 4 to start
        queue_filled = lruc(drivers.KVS.join_queue(group_1))
        self.assertTrue(queue_filled is None)

        # 2 more players join, need 4 (3 & 2 don't fit 4)
        queue_filled = lruc(drivers.KVS.join_queue(group_2))
        self.assertTrue(queue_filled is None)

        # 1 more player join (3 & 1 fit)
        queue_filled = lruc(drivers.KVS.join_queue(group_3))
        self.assertTrue(isinstance(queue_filled, UUID))

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

    def test_join_unknow_group(self):
        """Joining an unknown (or dismissed) group must fail"""
        groupid = lruc(drivers.KVS.create_group(self.user.userid,
                                                self.game.gameid))
        lruc(drivers.KVS.leave_group(groupid, self.user.userid))
        coro = drivers.KVS.join_group(groupid, self.user.userid)
        self.assertRaises(GroupDoesntExist, lruc, coro)
    
    def test_leave_group_not_beeing_in(self):
        """Leaving a group the user is not in must fail"""
        player_2 = uuid4()
        groupid = lruc(drivers.KVS.create_group(self.user.userid,
                                                self.game.gameid))
        lruc(drivers.KVS.join_group(groupid, player_2))
        lruc(drivers.KVS.leave_group(groupid, self.user.userid))
        coro = drivers.KVS.leave_group(groupid, self.user.userid)
        self.assertRaises(PlayerNotInGroup, lruc, coro)

    def test_join_queued_group(self):
        """Joining a group in queue should fail"""
        player_2 = uuid4()
        groupid = lruc(drivers.KVS.create_group(self.user.userid,
                                                self.game.gameid))
        lruc(drivers.KVS.join_queue(groupid))
        coro = drivers.KVS.join_group(groupid, player_2)
        self.assertRaises(GroupInQueueAlready, lruc, coro)

    def test_join_filled_group(self):
        groupid = lruc(drivers.KVS.create_group(self.user.userid,
                                                self.game.gameid))
        for _ in range(3):
            lruc(drivers.KVS.join_group(groupid, uuid4()))
        coro = drivers.KVS.join_group(groupid, uuid4())
        self.assertRaises(GroupIsFull, lruc, coro)    
