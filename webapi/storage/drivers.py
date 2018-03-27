"""Interfaces and implementation of databases drivers"""

from asyncio import gather, get_event_loop, run_coroutine_threadsafe, sleep
from collections import namedtuple
from itertools import starmap
from logging import getLogger
from operator import methodcaller
from os import listdir
from os.path import join as pathjoin
from pathlib import Path
from time import time
from asyncpg import Record
from sqlite3 import connect as sqlite3_connect
from .models import User, Game
from ..tools import root

logger = getLogger(__name__)

RDB: "RelationalDataBase"
KVS: "KeyValueStore"

class RelationalDataBase():
    """Interface for relational database access"""
    async def create_user(self, userid, name, email, hashed_password):
        """Create a user"""
        raise NotImplementedError()

    async def get_user_by_login(self, login):
        """Get a user given its login (username or email)"""
        raise NotImplementedError()

    async def get_user_by_id(self, id_):
        """Get a user given its id"""
        raise NotImplementedError()

    async def set_user_admin(self, userid, value):
        """Set a user as admin"""
        raise NotImplementedError()

    async def set_user_verified(self, userid, value):
        """Set a user as admin"""
        raise NotImplementedError()

    async def create_game(self, name, ownerid):
        """Create a game"""
        raise NotImplementedError()

    async def get_game_by_id(self, id_):
        """Get a game given its id"""
        raise NotImplementedError()

    async def get_game_by_name(self, name):
        """Get a game given its name"""
        raise NotImplementedError()

    async def get_games_by_owner(self, ownerid):
        """Get games given their owner"""
        raise NotImplementedError()

    async def set_game_owner(self, ownerid):
        """Change the owner of a game"""
        raise NotImplementedError()

    async def create_party(self, partyid, gamename, userids):
        """Create a party"""
        raise NotImplementedError()


class Postgres(RelationalDataBase):
    """Implementation for postgres"""
    def __init__(self, pgconn):
        self.conn = pgconn

    async def install(self):
        """Create tables and functions"""
        sqldir = pathjoin(root(), "storage", "sql_queries", "postgres")
        for file in sorted(listdir(sqldir)):
            with Path(sqldir).joinpath(file).open() as sqlfile:
                for sql in filter(methodcaller("strip"), sqlfile.read().split(";")):
                    status = await self.conn.execute(sql)
                    logger.debug    ("%s", status)

    async def prepare(self):
        """Cache all SQL available functions"""

        functions = [
            ("create_user", 4, None),
            ("get_user_by_id", 1, User),
            ("get_user_by_login", 1, User),
            ("set_user_admin", 2, None),
            ("set_user_verified", 2, None),
            ("create_game", 2, int),
            ("get_game_by_id", 1, Game),
            ("get_game_by_name", 1, Game),
            ("get_games_by_owner", 1, Game),
            ("set_game_owner", 2, None)
        ]

        async def wrap(name, argscnt, class_=None):
            """Create the prepated statement"""
            args = ", $".join(map(str, range(1, argscnt + 1)))
            query = await self.conn.prepare("SELECT %s($%s)" % (name, args))
            async def wrapped(*args):
                """Do the database call"""
                rows = (await query.fetchrow(*args))[name]
                if class_ is None:
                    return rows
                if isinstance(rows, Record):
                    return class_(**dict(rows.items()))
                return map(lambda row: class_(**dict(row.items())), rows)
            return wrapped

        for name, args_count, class_ in functions:
            setattr(self, name, await wrap(name, args_count, class_))

class SQLite(RelationalDataBase):
    """Implementation database-free"""
    def __init__(self):
        self.conn = sqlite3_connect(":memory:")
        sqldir = Path(root()).joinpath("storage", "sql_queries", "sqlite")

        def wrap(sql, class_=None):
            async def wrapped(self, *args):
                await sleep(0)
                rows = self.conn.cursor().execute(sql, args).fetchall()
                if class_ is None:
                    return rows[0] if len(rows) == 1 else rows
                if len(rows) == 1:
                    return class_(*rows[0])
                return map(lambda row: class_(*row), rows)
            return wrapped

        create_tables = [
            "create_table_users",
            "create_table_games"]
        for table in create_tables:
            with sqldir.joinpath("%s.sql" % table).open() as sqlfile:
                self.conn.cursor().execute(sqlfile.read())

        functions = [
            ("create_user", None),
            ("get_user_by_login", User),
            ("set_user_admin", None),
            ("set_user_verified", None)
        ]

        for function, class_ in functions:
            with sqldir.joinpath("%s.sql" % function).open() as sqlfile:
                setattr(self, function, wrap(sqlfile.read(), class_))


class KeyValueStore():
    """Interface for key-value store access"""
    async def revoke_token(self, token_id) -> None:
        """Set a token a revoked"""
        raise NotImplementedError()

    async def is_token_revoked(self, token_id) -> bool:
        """Validate a non-expirated token"""
        raise NotImplementedError()


class Redis(KeyValueStore):
    """Implementation for Redis"""
    def __init__(self, redis_conn):
        self.conn = redis_conn

    async def revoke_token(self, token) -> None:
        await self.conn.zremrangebyscore("trl", 0, int(time()))
        await self.conn.zadd("trl", token["exp"], token["tid"])

    async def is_token_revoked(self, token_id) -> bool:
        return await self.conn.zscore("trl", token_id) != None


class InMemory(KeyValueStore):
    """Implementation database-free"""
    def __init__(self):
        self.token_revocation_list = []

    async def revoke_token(self, token):
        await sleep(0)
        self.token_revocation_list.append(token["tid"])

    async def is_token_revoked(self, token_id) -> bool:
        await sleep(0)
        return token_id in self.token_revocation_list
