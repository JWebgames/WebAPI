"""Interfaces and implementation of databases drivers"""

from collections import OrderedDict
from logging import getLogger
from operator import methodcaller
from os import listdir
from os.path import join as pathjoin
from pathlib import Path
from time import time
from asyncpg import Record
from sqlite3 import connect as sqlite3_connect
from .models import User, Game, Group
from ..tools import root, fake_async
from ..exceptions import *
from uuid import UUID, uuid4
from time import time

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

    async def create_game(self, name, ownerid, capacity):
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
                    logger.debug("%s", status)

    async def prepare(self):
        """Cache all SQL available functions"""

        functions = [
            ("create_user", 4, None),
            ("get_user_by_id", 1, User),
            ("get_user_by_login", 1, User),
            ("set_user_admin", 2, None),
            ("set_user_verified", 2, None),
            ("create_game", 3, int),
            ("get_game_by_id", 1, Game),
            ("get_game_by_name", 1, Game),
            ("get_games_by_owner", 1, Game),
            ("set_game_owner", 2, None)
        ]

        async def wrap(name, argscnt, class_=None):
            """Create the prepated statement"""
            sqlargs = ", $".join(map(str, range(1, argscnt + 1)))
            query = await self.conn.prepare("SELECT %s($%s)" % (name, sqlargs))

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
            @fake_async
            def wrapped(*args):
                args = list(args)
                for i in range(len(args)):
                    if isinstance(args[i], UUID):
                        args[i] = str(args[i])
                rows = self.conn.cursor().execute(sql, args).fetchall()
                if class_ is None:
                    return rows[0] if len(rows) == 1 else rows
                if len(rows) == 0:
                    return None
                elif len(rows) == 1:
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
            ("get_user_by_id", User),
            ("get_user_by_login", User),
            ("set_user_admin", None),
            ("set_user_verified", None),
            ("create_game", None),
            ("get_game_by_id", Game),
            ("get_game_by_name", Game),
            ("get_games_by_owner", Game),
            ("set_game_owner", None)
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

    async def create_group(self, userid):
        raise NotImplementedError()

    async def join_group(self, groupid, userid):
        raise NotImplementedError()

    async def leave_group(self, groupid, userid):
        raise NotImplementedError()

    async def join_queue(self, groupid, game):
        raise NotImplementedError()

    async def leave_queue(self, groupid):
        raise NotImplementedError()
    
    async def msgqueue_push(self, userid, msg, msgid, timestamp):
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
        self.token_revocation_list = []  # List[token_id: UUID]
        self.groups = {}  # Dict[group_id: UUID, NamedTuple[members: List[user_id: UUID], game_id: UUID, queue_id: UUID]]
        self.queues = {}  # Dict[str, OrderedDict[UUID, list]]

    @fake_async
    def revoke_token(self, token):
        self.token_revocation_list.append(token["tid"])

    @fake_async
    def is_token_revoked(self, token_id) -> bool:
        return token_id in self.token_revocation_list

    @fake_async
    def create_group(self, userid, gameid):
        for group in self.groups.values():
            if userid in group.members:
                raise PlayerInGroupAlready()

        groupid = uuid4()
        self.groups[groupid] = Group([userid], gameid, None, None)
        return groupid

    async def join_group(self, groupid, userid):
        group = self.groups.get(groupid)
        if group is None: raise GroupDoesntExist()
        if group.queueid is not None: raise GroupInQueueAlready()
        for group in self.groups.values():
            if userid in group.members:
                raise PlayerInGroupAlready()

        game = await RDB.get_game_by_id(group.gameid)
        if len(group.members) + 1 > game.capacity:
            raise GroupIsFull()

        self.groups[groupid].members.append(userid)

    @fake_async
    def leave_group(self, groupid, userid):
        group = self.groups.get(groupid)
        if groupid is None: raise GroupDoesntExist()
        if userid not in group.members: raise PlayerNotInGroup()

        if group.queueid is not None:
            self.leave_queue(self, groupid, group.queueid)
        group.members.remove(userid)
        if not group.members:
            del self.groups[groupid]

    async def join_queue(self, groupid):
        group = self.groups.get(groupid)
        if group is None:
            raise GroupDoesntExist()

        game = await RDB.get_game_by_id(group.gameid)

        game_queue = self.queues.get(game.gameid)
        if game_queue is None:
            game_queue = self.queues[game.gameid] = OrderedDict()

        for queueid, queue in game_queue.items():
            size = len(queue) + len(group.members)
            if size < game.capacity:
                queue.extend(group.members)
                group.queueid = queueid
                return
            elif size == game.capacity:
                queue.extend(group.members)
                group.queueid = queueid
                return queueid

        queueid = uuid4()
        self.queues[game.gameid][queueid] = group.members.copy()
        group.queueid = queueid
        if len(self.queues[game.gameid][queueid]) == game.capacity:
            return queueid

    @fake_async
    def leave_queue(self, groupid, queueid):
        group = self.groups.get(groupid)
        if group is None:
            raise GroupDoesntExist()

        queue = self.queues.get(queueid)
        if queue is None:
            raise QueueDoesntExist()

        for member in group.members:
            queue.remove(member)

    @fake_async
    def msgqueue_push(self, userid, msg, msgid=None, timestamp=None):
        if msgid is None:
            msgid = uuid4()
        if timestamp is None:
            timestamp = time()
