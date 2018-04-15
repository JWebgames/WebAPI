import asyncio
from uuid import uuid4
from unittest import TestCase

from webapi.production import webapi
from webapi.server import connect_to_postgres, disconnect_from_postgres, \
                          connect_to_redis, disconnect_from_redis
from webapi.storage import drivers, models

loop = asyncio.get_event_loop()
toto = models.User(userid=uuid4(), name="toto", email="toto@example.com",
                   password=b"very_strong_password" isverified=False,
                   isadmin=False)

class TestRDB(TestCase):
    """Test case for tools.cast"""
    def setUp(self):
        if webapi.production:
            future = asyncio.gather(connect_to_postgres(None, loop),
                                    connect_to_redis(None, loop))
            loop.run_until_complete(future)

    def tearDown(self):
        if webapi.production:
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
        if webapi.production:
            future = asyncio.gather(connect_to_postgres(None, loop),
                                    connect_to_redis(None, loop))
            loop.run_until_complete(future)

    def tearDown(self):
        if webapi.production:
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

        bomberman = models.Game(gameid=0, ownerid=player_1, name="Bomberman", capacity=4)

        create_group()