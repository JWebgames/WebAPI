"""Interfaces and implementation of databases drivers"""

from asyncio import ensure_future
from collections import OrderedDict, Iterable
from logging import getLogger
from operator import methodcaller
from os import listdir
from os.path import join as pathjoin
from pathlib import Path
from time import time
from asyncpg import Record
from sqlite3 import connect as sqlite3_connect
from aioredis import Redis as RedisHighInterface
from .models import User, Game, Group, LightGame
from ..tools import root, fake_async
from webapi.exceptions import PlayerInGroupAlready, \
                              PlayerNotInGroup, \
                              GroupDoesntExist, \
                              GroupInQueueAlready, \
                              GroupIsFull, \
                              GroupPlayingAlready
from uuid import UUID, uuid4
from time import time
from typing import NewType

logger = getLogger(__name__)
AutoIncr = NewType("AutoIncr", int)

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
            ("create_game", 3, AutoIncr),
            ("get_all_games", 0, LightGame),
            ("get_game_by_id", 1, Game),
            ("get_game_by_name", 1, Game),
            ("get_games_by_owner", 1, Game),
            ("set_game_owner", 2, None)
        ]

        async def wrap(name, argscnt, class_=None):
            """Create the prepated statement"""
            if argscnt:
                sqlargs = ", $".join(map(str, range(1, argscnt + 1)))
                query = await self.conn.prepare("SELECT %s($%s)" % (name, sqlargs))
            else:
                query = await self.conn.prepare("SELECT %s" % name)

            async def wrapped(*args):
                """Do the database call"""
                rows = (await query.fetchrow(*args))[name]
                if class_ is None or rows is None:
                    return rows
                if isinstance(rows, Record):
                    return class_(**dict(rows.items()))
                if isinstance(rows, Iterable):
                    return map(lambda row: class_(**dict(row.items())), rows)
            return wrapped

        for name, args_count, class_ in functions:
            setattr(self, name, await wrap(name, args_count, class_))


class SQLite(RelationalDataBase):
    """Implementation database-free"""
    def __init__(self):
        self.conn = sqlite3_connect(":memory:")
        sqldir = Path(root()).joinpath("storage", "sql_queries", "sqlite")

        def fuck(namedtuple, idk):
            plop = []
            for idx, dq in enumerate(namedtuple._field_types.values()):
                plop.append(dq(idk[idx]))
            return plop

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
                if class_ is AutoIncr:
                    query = "SELECT last_insert_rowid()"
                    return self.conn.cursor().execute(query).fetchone()[0]
                if len(rows) == 0:
                    return None
                elif len(rows) == 1 and class_ not in [LightGame]:
                    return class_(*fuck(class_, rows[0]))
                return map(lambda row: class_(*fuck(class_, row)), rows)
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
            ("create_game", AutoIncr),
            ("get_all_games", LightGame),
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

    async def create_group(self, userid, gameid):
        raise NotImplementedError()

    async def join_group(self, groupid, userid):
        raise NotImplementedError()

    async def leave_group(self, userid):
        raise NotImplementedError()

    async def join_queue(self, groupid):
        raise NotImplementedError()

    async def leave_queue(self, groupid):
        raise NotImplementedError()
    
    async def msgqueue_push(self, userid, msg, msgid, timestamp):
        raise NotImplementedError()
    
    async def create_party(self, gameid, slotid):
        raise NotImplementedError()


class Redis(KeyValueStore):
    """Implementation for Redis"""

    user_groupid_key = "users:{!s}:groupid"
    user_ready_key = "users:{!s}:ready"
    group_gameid_key = "groups:{!s}:gameid"
    group_slotid_key = "groups:{!s}:slotid"
    group_partyid_key = "groups:{!s}:partyid"
    group_members_key = "groups:{!s}:members"
    game_queue_key = "queues:{!s}"
    slot_key = "slots:{!s}"
    party_slotid_key = "parties:{!s}:slotid"

    def __init__(self, redis_pool):
        self.redis = RedisHighInterface(redis_pool)

    async def revoke_token(self, token) -> None:
        await self.redis.zremrangebyscore("trl", 0, int(time()))
        await self.redis.zadd("trl", token["exp"], token["jti"])

    async def is_token_revoked(self, token_id) -> bool:
        return await self.redis.zscore("trl", token_id) != None

    async def create_group(self, userid, gameid):
        user_groupid_key = Redis.user_groupid_key.format(userid)
        groupid = await self.redis.get(user_groupid_key)
        if groupid is not None:
            raise PlayerInGroupAlready()
        
        groupid = uuid4()
        await self.redis.set(user_groupid_key, str(groupid))
        await self.redis.set(
            Redis.group_gameid_key.format(groupid), gameid)
        await self.redis.sadd(
            Redis.group_members_key.format(groupid), str(userid))

        return groupid
    
    async def join_group(self, groupid, userid):
        if (await self.redis.get(Redis.user_groupid_key.format(userid))) is not None:
            raise PlayerInGroupAlready()
        if (await self.redis.get(Redis.group_partyid_key.format(groupid))) is not None:
            raise GroupPlayingAlready()
        if (await self.redis.get(Redis.group_slotid_key.format(groupid))) is not None:
            raise GroupInQueueAlready()
        
        gameid = await self.redis.get(Redis.group_gameid_key.format(groupid))
        if gameid is None:
            raise GroupDoesntExist()
        game = await RDB.get_game_by_id(int(gameid))
        
        group_members_key = Redis.group_members_key.format(groupid)
        group_size = await self.redis.scard(group_members_key)
        if group_size + 1 > game.capacity:
            raise GroupIsFull()

        await self.redis.sadd(group_members_key, str(userid))
    
    async def leave_group(self, userid):
        user_groupid_key = Redis.user_groupid_key.format(userid)
        groupid = await self.redis.get(user_groupid_key)
        if groupid is None:
            raise PlayerNotInGroup()
        if (await self.redis.get(Redis.group_partyid_key.format(groupid))) is not None:
            raise GroupPlayingAlready()

        if (await self.redis.get(Redis.group_slotid_key.format(userid))) is not None:
            await self.leave_queue(groupid)

        await self.redis.delete(user_groupid_key)
        await self.redis.srem(Redis.group_members_key.format(groupid), str(userid))
    
    async def get_group(self, userid):
        user_groupid_key = Redis.user_groupid_key.format(userid)
        groupid = await self.redis.get(user_groupid_key)
        if groupid is None:
            raise PlayerNotInGroup()
    
        gameid = await self.redis.get(Redis.group_gameid_key.format(groupid))
        slotid = await self.redis.get(Redis.group_slotid_key.format(userid))
        partyid = await self.redis.get(Redis.group_partyid_key.format(groupid))
        members = await self.redis.smembers(Redis.group_members_key.format(groupid))

        return Group(list(map(UUID, members)),
                     gameid and UUID(gameid),
                     slotid and UUID(slotid),
                     partyid and UUID(partyid))

    async def is_ready(self, userid):
        return (await self.redis.get(Redis.user_ready_key.format(userid))) == b"1"

    async def clear_ready(self, userid):
        user_groupid_key = Redis.user_groupid_key.format(userid)
        groupid = await self.redis.get(user_groupid_key)
        if groupid is None:
            raise PlayerNotInGroup()
        groupid = groupid.decode()
        
        await self.redis.delete(Redis.user_ready_key.format(userid))


    async def set_ready(self, userid, callback_when_all_ready):
        user_groupid_key = Redis.user_groupid_key.format(userid)
        groupid = await self.redis.get(user_groupid_key)
        if groupid is None:
            raise PlayerNotInGroup()
        groupid = groupid.decode()
        
        await self.redis.set(Redis.user_ready_key.format(userid), 1)
    
    async def is_group_ready(self, groupid)
        group_members_key = Redis.group_members_key.format(groupid)
        members = list(map(methodcaller("decode"),
                           await self.redis.smembers(group_members_key)))

        coros = [self.is_ready(memberid) for memberid in members]
        if all(await asyncio.gather(coros)):
            coros = [self.redis.delete(Redis.user_ready_key.format(memberid))
                     for memberid in members]
            await asyncio.gather(coros)
            asyncio.ensure_future(callback_when_all_ready)


    async def join_queue(self, groupid):
        gameid = int(await self.redis.get(Redis.group_gameid_key.format(groupid)))
        if (await self.redis.get(Redis.group_partyid_key.format(groupid))) is not None:
            raise GroupPlayingAlready()
        if (await self.redis.get(Redis.group_slotid_key.format(groupid))) is not None:
            raise GroupInQueueAlready()

        game = await RDB.get_game_by_id(gameid)
        group_members_key = Redis.group_members_key.format(groupid)
        group_members = await self.redis.smembers(group_members_key)

        game_queue_key = Redis.game_queue_key.format(gameid)
        slotids = await self.redis.lrange(
            game_queue_key, 0, await self.redis.llen(game_queue_key))
        for slotid in map(methodcaller("decode"), slotids):
            slot_key = Redis.slot_key.format(slotid)
            slot_size = await self.redis.scard(slot_key)
            if slot_size + len(group_members) <= game.capacity:
                await self.redis.sunionstore(
                    slot_key, slot_key, group_members_key)
                await self.redis.set(
                    Redis.group_slotid_key.format(groupid), slotid)
                
                if slot_size + len(group_members) == game.capacity:
                    await self.redis.lrem(game_queue_key, 1, slot_key)
                    partyid = uuid4()
                    await self.redis.set(
                        Redis.party_slotid_key.format(partyid), slotid)
                    return start_gate(partyid)  # Coroutine /!\
                return

        slotid = uuid4()
        logger.debug("Creating new slot: %s", slotid)
        await self.redis.set(
            Redis.group_slotid_key.format(groupid), str(slotid))
        await self.redis.sunionstore(
            Redis.slot_key.format(slotid), group_members_key)
        if len(group_members) < game.capacity:
            await self.redis.rpush(
                Redis.game_queue_key.format(gameid), str(slotid))
        else:
            partyid = uuid4()
            await self.redis.set(
                Redis.group_partyid_key.format(groupid), str(partyid))
            await self.redis.set(
                Redis.party_slotid_key.format(partyid), str(slotid))
            return start_gate(partyid)  # Coroutine /!\

    async def leave_queue(self, groupid):
        raise NotImplementedError()

class InMemory(KeyValueStore):
    """Implementation database-free"""
    def __init__(self):
        self.token_revocation_list = []  # List[tokenid: UUID]
        self.groups = {}  # Dict[groupid: UUID, Group]
        self.queues = {}  # Dict[gameid, OrderedDict[UUID, List[userid]]]
        self.slots = {}  # Dict[slotid, List[userid]]
        self.parties = {}  # Dict[partyid, List[userid]]
        self.user_map = {}

    @fake_async
    def revoke_token(self, token):
        self.token_revocation_list.append(token["jti"])

    @fake_async
    def is_token_revoked(self, tokenid) -> bool:
        return tokenid in self.token_revocation_list

    @fake_async
    def create_group(self, userid, gameid):
        for group in self.groups.values():
            if userid in group.members:
                raise PlayerInGroupAlready()

        groupid = uuid4()
        self.user_map[userid] = groupid
        self.groups[groupid] = Group([userid], gameid, None, None)
        return groupid

    async def join_group(self, groupid, userid):
        group = self.groups.get(groupid)
        if group is None:
            raise GroupDoesntExist()
        if group.partyid is not None:
            raise GroupPlayingAlready()
        if group.slotid is not None:
            raise GroupInQueueAlready()
        for group in self.groups.values():
            if userid in group.members:
                raise PlayerInGroupAlready()

        game = await RDB.get_game_by_id(group.gameid)
        if len(group.members) + 1 > game.capacity:
            raise GroupIsFull()

        self.user_map[userid] = groupid
        self.groups[groupid].members.append(userid)

    @fake_async
    def leave_group(self, userid):
        groupid = self.user_map.get(userid)
        if groupid is None:
            raise PlayerNotInGroup()
        
        group = self.groups[groupid]
        if group.slotid is not None:
            self.leave_queue(self, groupid, group.slotid)
        del self.user_map[userid]
        group.members.remove(userid)
        if not group.members:
            del self.groups[groupid]
    
    @fake_async
    def get_group(self, userid):
        groupid = self.user_map.get(userid)
        if groupid is None:
            raise PlayerNotInGroup()
        return self.groups[groupid]

    async def join_queue(self, groupid):
        group = self.groups.get(groupid)
        if group is None:
            raise GroupDoesntExist()

        game = await RDB.get_game_by_id(group.gameid)

        game_queue = self.queues.get(game.gameid)
        if game_queue is None:
            game_queue = self.queues[game.gameid] = OrderedDict()

        for slotid, slot in game_queue.items():
            size = len(slot) + len(group.members)
            if size < game.capacity:
                slot.extend(group.members)
                group.slotid = slotid
                return
            elif size == game.capacity:
                slot.extend(group.members)
                group.slotid = slotid
                partyid = uuid4()
                self.parties[partyid] = slot
                ensure_future(start_gate, partyid)

        slotid = uuid4()
        group.slotid = slotid
        self.slots[slotid] = group.members.copy()
        self.queues[game.gameid][slotid] = self.slots[slotid]
        if len(self.slots[slotid]) == game.capacity:
            partyid = uuid4()
            ensure_future(start_game, partyid)

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
