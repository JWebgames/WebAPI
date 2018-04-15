import asyncio
from uuid import uuid4, UUID
from unittest import TestCase

from webapi.config import webapi
from webapi.server import connect_to_postgres, disconnect_from_postgres, \
                          connect_to_redis, disconnect_from_redis
from webapi.storage import drivers, models
from webapi.tools import lruc

loop = asyncio.get_event_loop()
toto = models.User(userid=uuid4(), name="toto", email="toto@example.com",
                   password=b"very_strong_password", isverified=False,
                   isadmin=False)

bomberman = models.Game(gameid=0, ownerid=toto, name="Bomberman", capacity=4)

class TestRDB(TestCase):
    """Test case for tools.cast"""
    def setUp(self):
        if webapi.PRODUCTION:
            future = asyncio.gather(connect_to_postgres(None, loop),
                                    connect_to_redis(None, loop))
            loop.run_until_complete(future)

    def tearDown(self):
        if webapi.PRODUCTION:
            future = asyncio.gather(disconnect_from_postgres(None, loop),
                                    disconnect_from_redis(None, loop))
            loop.run_until_complete(future)


    def test_create_retrieve_user(self):
        loop.run_until_complete(
            drivers.RDB.create_user(
                toto.userid, toto.name, toto.email, toto.password))
        
        twoto = loop.run_until_complete(
            drivers.RDB.get_user_by_id(
                toto.user_id))
        
        self.assertEqual(toto, twoto)

    def test_create_game(self):
        pass

class TestKVS(TestCase):
    def setUp(self):
        if webapi.PRODUCTION:
            future = asyncio.gather(connect_to_postgres(None, loop),
                                    connect_to_redis(None, loop))
            loop.run_until_complete(future)

    def tearDown(self):
        if webapi.PRODUCTION:
            future = asyncio.gather(disconnect_from_postgres(None, loop),
                                    disconnect_from_redis(None, loop))
            loop.run_until_complete(future)

    def test_start_game(self):
        player_1 = uuid4()
        player_2 = uuid4()
        player_3 = uuid4()
        player_4 = uuid4()
        player_5 = uuid4()
        player_6 = uuid4()

        
        group_1 = lruc(loop, drivers.KVS.create_group(player_1, bomberman))
        lruc(loop, drivers.KVS.join_group(group_1, player_2))
        lruc(loop, drivers.KVS.join_group(group_1, player_3))

        group_2 = lruc(loop, drivers.KVS.create_group(player_4, bomberman))
        lruc(loop, drivers.KVS.join_group(group_1, player_5))

        group_3 = lruc(loop, drivers.KVS.create_group(player_5, bomberman))

        # 3 players join, need 4 to start
        queue_filled = lruc(loop, drivers.KVS.join_queue(group_1))
        self.assertTrue(queue_filled is None)

        # 2 more players join, need 4 (3 & 2 don't fit 4)
        queue_filled = loop.run_until_complete(drivers.KVS.join_queue(group_2))
        self.assertTrue(queue_filled is None)

        # 1 more player join (3 & 1 fit)
        queue_filled = loop.run_until_complete(drivers.KVS.join_queue(group_3))
        self.assertTrue(isinstance(queue_filled, UUID))
