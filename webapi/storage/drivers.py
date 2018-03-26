"""Interfaces and implementation for key-value store access"""
"""Interfaces and implementation for relational database access"""

import types
from sqlite3 import connect as sqlite3_connect
from asyncio import sleep, gather, get_event_loop
from pathlib import Path
from os import listdir
from os.path import join as pathjoin
from ..tools import root
from collections import namedtuple
from itertools import starmap

RDB: "RelationalDataBase"
KVS: "KeyValueStore"

class RelationalDataBase():
    """Interface for relational database access"""
    async def create_user(self, userid, name, email, hashed_password, isadmin):
        """Create a user"""
        raise NotImplementedError()

    async def get_user_by_login(self, login):
        """Get a user given its login (username or email)"""
        raise NotImplementedError()

    async def get_user_by_id(self, id_):
        """Get a user given its id"""
        raise NotImplementedError()

    async def set_user_admin(self, userid):
        """Set a user as admin"""
        raise NotImplementedError()

    async def set_user_verified(self, userid):
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

        async def wrap(name, argscnt):
            """Cache the prepated statement"""
            args = ", $".join(range(1, argscnt + 1))
            query = await pgconn.prepare("SELECT %s($%s)" % (name, args))
            async def wrapped(*args):
                """Do the database call"""
                return await query.fetch(*args)
            return name, wrapped

        for name, wrapped in \
                get_event_loop(). \
                run_until_complete(
                    gather(
                        *starmap(wrap, [
                            ("create_user", 4),
                            ("get_user_by_id", 1),
                            ("get_user_by_login", 1),
                            ("set_user_admin", 1),
                            ("set_user_verified", 1),
                            ("create_game", 2),
                            ("get_game_by_id", 1),
                            ("get_game_by_name", 1),
                            ("get_games_by_owner", 1),
                            ("set_game_owner", 1),
                            ("create_party", 3),
                        ])
                    )
                ).result():
            setattr(self, name, wrapped)


class SQLite(RelationalDataBase):
    """Implementation database-free"""
    def __init__(self):
        dbfile = pathjoin(root(), "storage", "data.sqlite3")
        self.conn = sqlite3_connect(dbfile)
        self.queries = {}

        cur = self.conn.cursor()
        sqldir = pathjoin(root(), "storage", "sql_queries", "sqlite")
        for filename in listdir(sqldir):
            with Path(sqldir).joinpath(filename).open() as file:
                sql = file.read()
                if filename.startswith("create_table"):
                    cur.execute(sql)
                else:
                    query_name = filename[:filename.rindex(".")]
                    self.queries[query_name] = sql

    async def create_user(self, userid, name, email, hashed_password, isadmin):
        await sleep(0)
        self.conn.cursor().execute(self.queries["create_user"], {
            "userid": userid,
            "name": name,
            "email": email,
            "password": hashed_password,
            "isadmin": int(isadmin)
        })

    async def get_user_by_login(self, login):
        await sleep(0)
        return self.conn.cursor().execute(self.queries["get_user_by_login"], {
            "login": login
        }).fetchone()

    async def grant_admin(self, userid):
        await sleep(0)
        cur = self.conn.cursor()
        cur.execute(self.queries["update_user_set_admin"], {userid: userid})


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

    async def revoke_token(self, token_id) -> None:
        raise NotImplementedError()

    async def is_token_revoked(self, token_id) -> bool:
        raise NotImplementedError()


class InMemory(KeyValueStore):
    """Implementation database-free"""
    def __init__(self):
        self.token_revocation_list = []

    async def revoke_token(self, token_id):
        self.token_revocation_list.append(token_id)

    async def is_token_revoked(self, token_id) -> bool:
        return token_id in self.token_revocation_list
