"""Interfaces and implementation of databases drivers"""

from asyncio import ensure_future, gather, Queue
from collections import OrderedDict, Iterable, defaultdict
from datetime import datetime, timedelta
from json import dumps as json_dumps
from logging import getLogger
from operator import methodcaller
from os import listdir
from os.path import join as pathjoin
from pathlib import Path
from time import time
from aioredis import Redis as AIORedis
from asyncpg import Record
from sqlite3 import connect as sqlite3_connect
from .models import User, Game, State, MsgQueueType, \
                    Group, UserKVS, Slot, Message
from ..tools import root, fake_async
from webapi.exceptions import PlayerInGroupAlready, \
                              PlayerNotInGroup, \
                              GroupDoesntExist, \
                              GroupIsFull, \
                              GroupNotReady, \
                              WrongGroupState, \
                              GameDoesntExist, \
                              NotFoundError
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
    
    async def get_all_games(self):
        """Get all games"""
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
    
    async def create_user(self, userid, name, email, hashed_password):
        query = await self.conn.prepare("SELECT create_user($1, $2, $3, $4)")
        await query.fetch(userid, name, email, hashed_password)

    async def get_user_by_login(self, login):
        query = await self.conn.prepare("SELECT * FROM get_user_by_login($1)")
        user = await query.fetchrow(login)
        if user["userid"] is None:
            raise NotFoundError()
        return User(**dict(user.items()))

    async def get_user_by_id(self, id_):
        query = await self.conn.prepare("SELECT * FROM get_user_by_id($1)")
        user = await query.fetchrow(id_)
        if user["userid"] is None:
            raise NotFoundError()
        return User(**dict(user.items()))

    async def set_user_admin(self, userid, value):
        query = await self.conn.prepare("SELECT set_user_admin($1, $2)")
        await query.fetch(userid, value)

    async def set_user_verified(self, userid, value):
        query = await self.conn.prepare("SELECT set_user_verified($1, $2)")
        await query.fetch(userid, value)

    async def create_game(self, name, ownerid, capacity):
        query = await self.conn.prepare("SELECT create_game($1, $2, $3)")
        gameid = await query.fetchrow(name, ownerid, capacity)[0]
        return gameid

    async def get_game_by_id(self, id_):
        query = await self.conn.prepare("SELECT * FROM get_game_by_id($1)")
        game = await query.fetchrow(id_)
        if game["gameid"] is None:
            raise NotFoundError()
        return Game(**dict(game.items()))
    
    async def get_all_games(self):
        query = await self.conn.prepare("SELECT * FROM get_all_games()")
        games = await query.fetch()

        return map(lambda game: Game(**dict(game.items())), games)

    async def get_game_by_name(self, name):
        query = await self.conn.prepare("SELECT * FROM get_game_by_name($1)")
        game = await query.fetchrow(name)
        if game["gameid"] is None:
            raise NotFoundError()
        return Game(**dict(game.items()))


class SQLite(RelationalDataBase):
    """Implementation database-free"""
    def __init__(self):
        self.conn = sqlite3_connect(":memory:")
        self.sqldir = Path(root()).joinpath("storage", "sql_queries", "sqlite")

        create_tables = [
            "create_table_users",
            "create_table_games"]
        for table in create_tables:
            with self.sqldir.joinpath("%s.sql" % table).open() as sqlfile:
                self.conn.cursor().execute(sqlfile.read())

    async def create_user(self, userid, name, email, hashed_password):
        with self.sqldir.joinpath("create_user.sql").open() as sqlfile:
            self.conn.cursor().execute(sqlfile.read(),
                [str(userid), name, email, hashed_password])

    async def get_user_by_login(self, login):
        with self.sqldir.joinpath("get_user_by_login.sql").open() as sqlfile:
            query = self.conn.cursor().execute(sqlfile.read(), [login])
            user = query.fetchone()
            if user is None:
                raise NotFoundError()
            return User(*user)

    async def get_user_by_id(self, id_):
        with self.sqldir.joinpath("get_user_by_id.sql").open() as sqlfile:
            query = self.conn.cursor().execute(sqlfile.read(), [id_])
            user = query.fetchone()
            if user is None:
                raise NotFoundError()
            return User(*user)

    async def set_user_admin(self, userid, value):
        with self.sqldir.joinpath("set_user_admin.sql").open() as sqlfile:
            self.conn.cursor().execute(sqlfile.read(), [str(userid), value])

    async def set_user_verified(self, userid, value):
        with self.sqldir.joinpath("set_user_verified.sql").open() as sqlfile:
            self.conn.cursor().execute(sqlfile.read(), [str(userid), value])

    async def create_game(self, name, ownerid, capacity):
        with self.sqldir.joinpath("create_game.sql").open() as sqlfile:
            self.conn.cursor().execute(sqlfile.read(),
                [name, str(ownerid), capacity])
    
        query = "SELECT last_insert_rowid()"
        return self.conn.cursor().execute(query).fetchone()[0] 

    async def get_game_by_id(self, id_):
        with self.sqldir.joinpath("get_game_by_id.sql").open() as sqlfile:
            query = self.conn.cursor().execute(sqlfile.read(), [id_])
            game = query.fetchone()
            if game is None:
                raise NotFoundError()
            return Game(*game)

    async def get_game_by_name(self, name):
        with self.sqldir.joinpath("get_game_by_name.sql").open() as sqlfile:
            query = self.conn.cursor().execute(sqlfile.read(), [name])
            game = query.fetchone()
            if game is None:
                raise NotFoundError()
            return Game(*game)
    
    async def get_all_games(self):
        with self.sqldir.joinpath("get_all_games.sql").open() as sqlfile:
            query = self.conn.cursor().execute(sqlfile.read())
            games = query.fetchall()
            return map(lambda game: Game(*game), games)


class KeyValueStore():
    """Interface for key-value store access"""
    async def revoke_token(self, token_id) -> None:
        """Set a token a revoked"""
        raise NotImplementedError()

    async def is_token_revoked(self, token_id) -> bool:
        """Validate a non-expirated token"""
        raise NotImplementedError()
    
    async def get_user(self, userid):
        """Get a user given it's id"""
        raise NotImplementedError()

    async def create_group(self, userid, gameid):
        """Create a new group for a game"""
        raise NotImplementedError()

    async def join_group(self, groupid, userid):
        """Join an existing group"""
        raise NotImplementedError()
    
    async def get_group(self, groupid):
        """Get a group given its id"""
        raise NotImplementedError()
    
    async def mark_as_ready(self, userid):
        """Mark user as ready"""
        raise NotImplementedError()
    
    async def mark_as_not_ready(self, userid):
        """Mark user as not ready"""
        raise NotImplementedError()
    
    async def is_user_ready(self, userid):
        """Check the readyness of a user"""
        raise NotImplementedError()

    async def leave_group(self, userid):
        """Leave the current group"""
        raise NotImplementedError()

    async def join_queue(self, groupid):
        """Place the group in the queue, try to create a match"""
        raise NotImplementedError()

    async def leave_queue(self, groupid):
        """Remove the group from the queue"""
        raise NotImplementedError()
    
    async def create_party(self, groupid):
        raise NotImplementedError()
    
    async def send_message(self, queue_group, queue_target, id_, payload):
        raise NotImplementedError()

    async def recv_messages(self, queue, id_):
        raise NotImplementedError()


class Redis(KeyValueStore):
    """Implementation for Redis"""

    user_groupid_key = "users:{!s}:groupid"
    user_ready_key = "users:{!s}:ready"
    user_partyid_key = "users:{!s}:partyid"
    group_state_key = "groups:{!s}:state"
    group_members_key = "groups:{!s}:members"
    group_gameid_key = "groups:{!s}:gameid"
    group_slotid_key = "groups:{!s}:slotid"
    group_partyid_key = "groups:{!s}:partyid"
    game_queue_key = "queues:{!s}"
    slot_players_key = "slots:{!s}:players"
    slot_groups_key = "slots:{!s}:groups"
    msgqueue_key = "msgqueues:{!s}:{!s}"

    def __init__(self, redis_pool):
        self.redis = AIORedis(redis_pool)

    async def revoke_token(self, token) -> None:
        await self.redis.zremrangebyscore("trl", 0, int(time()))
        await self.redis.zadd("trl", token["exp"], token["jti"])

    async def is_token_revoked(self, token_id) -> bool:
        return await self.redis.zscore("trl", token_id) != None
    
    async def get_user(self, userid):
        groupid = await self.redis.get(Redis.user_groupid_key.format(userid))
        if groupid is None:
            raise PlayerNotInGroup()
        partyid = await self.redis.get(Redis.user_partyid_key.format(userid))
        ready = await self.redis.get(Redis.user_ready_key.format(userid))

        return UserKVS(UUID(groupid.decode()),
                       partyid and UUID(partyid.decode()),
                       ready == b"1")


    async def create_group(self, userid, gameid):
        user_groupid_key = Redis.user_groupid_key.format(userid)
        groupid = await self.redis.get(user_groupid_key)
        if groupid is not None:
            raise PlayerInGroupAlready()
        
        if (await RDB.get_game_by_id(gameid)) is None:
            raise GameDoesntExist()
        
        groupid = uuid4()
        await self.redis.set(user_groupid_key, str(groupid))
        await self.redis.set(Redis.user_ready_key.format(userid), b"0")
        await self.redis.set(
            Redis.group_state_key.format(groupid), State.GROUP_CHECK.value)
        await self.redis.set(
            Redis.group_gameid_key.format(groupid), str(gameid))
        await self.redis.sadd(
            Redis.group_members_key.format(groupid), str(userid))

        return groupid
    
    async def join_group(self, groupid, userid):
        user_groupid_key = Redis.user_groupid_key.format(userid)
        if (await self.redis.get(user_groupid_key)) is not None:
            raise PlayerInGroupAlready()

        await self.redis.set(Redis.user_ready_key.format(userid), b"0")

        gameid = await self.redis.get(Redis.group_gameid_key.format(groupid))
        if gameid is None:
            raise GroupDoesntExist()

        state = State(await self.redis.get(
            Redis.group_state_key.format(groupid)))
        if state != State.GROUP_CHECK:
            raise WrongGroupState(state, State.GROUP_CHECK)

        game = await RDB.get_game_by_id(int(gameid))        
        group_members_key = Redis.group_members_key.format(groupid)
        group_size = await self.redis.scard(group_members_key)
        if group_size + 1 > game.capacity:
            raise GroupIsFull()

        await self.redis.set(user_groupid_key, str(groupid))
        await self.redis.sadd(group_members_key, str(userid))
        await self.redis.set(Redis.user_ready_key.format(userid), b"0")
    
    async def leave_group(self, userid):
        user_groupid_key = Redis.user_groupid_key.format(userid)
        groupid = await self.redis.get(user_groupid_key)
        if groupid is None:
            raise PlayerNotInGroup()
        groupid = groupid.decode()

        state = State(await self.redis.get(
            Redis.group_state_key.format(groupid)))
        valids = [State.GROUP_CHECK, State.IN_QUEUE]
        if state not in valids:
            raise WrongGroupState(state, valids)
        if state == State.IN_QUEUE:
            await self.leave_queue(groupid)

        await self.redis.delete(user_groupid_key)
        await self.redis.srem(
            Redis.group_members_key.format(groupid), str(userid))

        ensure_future(self.group_cleanup(groupid))
    
    async def group_cleanup(self, groupid):
        if (await self.redis.scard(Redis.group_members_key.format(groupid))) == 0:
            await gather(
                self.redis.delete(Redis.group_gameid_key.format(groupid)),
                self.redis.delete(Redis.group_state_key.format(groupid)),
                self.redis.delete(Redis.group_slotid_key.format(groupid)),
                self.redis.delete(Redis.group_partyid_key.format(groupid))
            )
    
    async def get_group(self, groupid):
        state = await self.redis.get(Redis.group_state_key.format(groupid))
        if state is None:
            raise GroupDoesntExist()
        gameid = await self.redis.get(Redis.group_gameid_key.format(groupid))
        slotid = await self.redis.get(Redis.group_slotid_key.format(groupid))
        partyid = await self.redis.get(Redis.group_partyid_key.format(groupid))
        members = await self.redis.smembers(Redis.group_members_key.format(groupid))

        return Group(State(state),
                    [UUID(userid.decode()) for userid in members],
                    int(gameid),
                    slotid and UUID(slotid.decode()),
                    partyid and UUID(partyid.decode()))

    async def mark_as_ready(self, userid):
        user_groupid_key = Redis.user_groupid_key.format(userid)
        groupid = await self.redis.get(user_groupid_key)
        if groupid is None:
            raise PlayerNotInGroup()
        groupid = groupid.decode()

        state = State(await self.redis.get(
            Redis.group_state_key.format(groupid)))
        valids = [State.GROUP_CHECK, State.PARTY_CHECK]
        if state not in valids:
            raise WrongGroupState(state, valids)
        
        await self.redis.set(Redis.user_ready_key.format(userid), b"1")

    async def mark_as_not_ready(self, userid):
        user_groupid_key = Redis.user_groupid_key.format(userid)
        groupid = await self.redis.get(user_groupid_key)
        if groupid is None:
            raise PlayerNotInGroup()
        groupid = groupid.decode()

        state = State(await self.redis.get(
            Redis.group_state_key.format(groupid)))
        valids = [State.GROUP_CHECK, State.IN_QUEUE, State.PARTY_CHECK]
        if state not in valids:
            raise WrongGroupState(state, valids)
        if state == State.IN_QUEUE:
            await self.leave_queue(groupid)
        
        await self.redis.set(Redis.user_ready_key.format(userid), b"0")
    
    async def is_user_ready(self, userid):
        ready = self.redis.get(Redis.user_ready_key.format(userid))
        if ready is None:
            raise PlayerNotInGroup()
        return ready == b"1"

    async def is_ready(self, userid):
        return (await self.redis.get(Redis.user_ready_key.format(userid))) == b"1"
    
    async def is_group_ready(self, groupid):
        return all(await gather(*[
            self.is_ready(userid.decode()) for userid in 
            await self.redis.smembers(Redis.group_members_key.format(groupid))]))


    async def join_queue(self, groupid):
        gameid = await self.redis.get(Redis.group_gameid_key.format(groupid))
        if gameid is None:
            raise GroupDoesntExist()
        gameid = int(gameid)

        group_state_key = Redis.group_state_key.format(groupid)
        state = State(await self.redis.get(group_state_key))
        if state != State.GROUP_CHECK:
            raise WrongGroupState(state, State.GROUP_CHECK)
        await self.redis.set(group_state_key, State.IN_QUEUE.value)

        if not (await self.is_group_ready(groupid)):
            raise GroupNotReady()

        game = await RDB.get_game_by_id(gameid)
        group_members_key = Redis.group_members_key.format(groupid)
        group_members = await self.redis.smembers(group_members_key)

        game_queue_key = Redis.game_queue_key.format(gameid)
        slotids = await self.redis.lrange(
            game_queue_key, 0, await self.redis.llen(game_queue_key))
        for slotid in map(methodcaller("decode"), slotids):
            slot_players_key = Redis.slot_players_key.format(slotid)
            slot_size = await self.redis.scard(slot_players_key)
            if slot_size + len(group_members) <= game.capacity:
                await self.redis.set(
                    Redis.group_slotid_key.format(groupid), str(slotid))
                await self.redis.sunionstore(
                    slot_players_key, slot_players_key, group_members_key)
                await self.redis.sadd(
                    Redis.slot_groups_key.format(slotid), str(groupid))
                
                if slot_size + len(group_members) == game.capacity:
                    ensure_future(self.start_game(UUID(slotid)))
                break
        else:
            slotid = uuid4()
            await self.redis.set(
                Redis.group_slotid_key.format(groupid), str(slotid))
            await self.redis.sunionstore(
                Redis.slot_players_key.format(slotid), group_members_key)
            await self.redis.sadd(Redis.slot_groups_key.format(slotid), str(groupid))
            await self.redis.rpush(
                Redis.game_queue_key.format(gameid), str(slotid))
            if len(group_members) == game.capacity:
                ensure_future(self.start_game(UUID(slotid)))

    async def leave_queue(self, groupid):
        gameid = await self.redis.get(Redis.group_gameid_key.format(groupid))
        if gameid is None:
            raise GroupDoesntExist()
        gameid = int(gameid)
        
        group_state_key = Redis.group_state_key.format(groupid)
        state = State(await self.redis.get(group_state_key))
        if state != State.IN_QUEUE:
            raise WrongGroupState(state, State.IN_QUEUE)

        group_slotid_key = Redis.group_slotid_key.format(groupid)
        slotid = (await self.redis.get(group_slotid_key)).decode()
        slot_players_key = Redis.slot_players_key.format(slotid)
        await self.redis.srem(Redis.slot_groups_key.format(slotid), str(groupid))
        await self.redis.sdiffstore(
            slot_players_key, slot_players_key, Redis.group_members_key.format(groupid))
        if (await self.redis.scard(slot_players_key)) == 0:
            self.redis.lrem(Redis.game_queue_key.format(gameid), 1, slotid)
        await self.redis.set(group_state_key, State.GROUP_CHECK.value)
    
    async def send_message(self, queue, id_, payload):
        await self.redis.publish(
            Redis.msgqueue_key.format(queue.value, id_),
            json_dumps(payload).encode("utf-8"))

    async def recv_messages(self, queue, id_):
        key = Redis.msgqueue_key.format(queue.value, id_)
        chan = (await self.redis.subscribe(key))[0]
        while await chan.wait_message():
            yield await chan.get(encoding="utf-8")


class InMemory(KeyValueStore):
    """Implementation database-free"""
    def __init__(self):
        self.token_revocation_list = []  # List[tokenid]]
        self.users = {}  # Dict[userid, UserKVS]
        self.groups = {}  # Dict[groupid, Group]
        self.queues = {}  # Dict[gameid, List[slotid]]
        self.slots = {}  # Dict[slotid, Slot]
        self.parties = {}  # Dict[partyid, Party]
        self.msgqueues = {
            MsgQueueType.USER: defaultdict(Queue),
            MsgQueueType.GROUP: defaultdict(Queue),
            MsgQueueType.PARTY: defaultdict(Queue),
        }

    @fake_async
    def revoke_token(self, token):
        self.token_revocation_list.append(token["jti"])

    @fake_async
    def is_token_revoked(self, tokenid) -> bool:
        return tokenid in self.token_revocation_list

    @fake_async
    def create_group(self, userid, gameid):
        user = self.users.get(userid)
        if user is not None and user.groupid is not None:
            raise PlayerInGroupAlready()

        groupid = uuid4()
        self.users[userid] = UserKVS(groupid, None, False)
        self.groups[groupid] = Group(
            State.GROUP_CHECK, [userid], gameid, None, None)
        return groupid
    
    @fake_async
    def get_user(self, userid):
        user = self.users.get(userid)
        if user is None:
            raise PlayerNotInGroup()
        return user

    async def join_group(self, groupid, userid):
        user = self.users.get(userid)
        if user is not None and user.groupid is not None:
            raise PlayerInGroupAlready()

        group = self.groups.get(groupid)
        if group is None:
            raise GroupDoesntExist()
        if group.state != State.GROUP_CHECK:
            raise WrongGroupState(group.state, State.GROUP_CHECK)

        game = await RDB.get_game_by_id(group.gameid)
        if len(group.members) + 1 > game.capacity:
            raise GroupIsFull()

        self.users[userid] = UserKVS(groupid, None, False)
        self.groups[groupid].members.append(userid)
    
    @fake_async
    def get_group(self, groupid):
        group = self.groups.get(groupid)
        if group is None:
            raise GroupDoesntExist()
        return group

    @fake_async
    def mark_as_ready(self, userid):
        user = self.users.get(userid)
        if user is None or user.groupid is None:
            raise PlayerNotInGroup()
        
        state = self.groups[user.groupid].state
        valids = [State.GROUP_CHECK, State.PARTY_CHECK]
        if state not in valids:
            raise WrongGroupState(state, valids)
        
        user.ready = True
    
    async def mark_as_not_ready(self, userid):
        user = self.users.get(userid)
        if user is None or user.groupid is None:
            raise PlayerNotInGroup()

        state = self.groups[user.groupid].state
        valids = [State.GROUP_CHECK, State.IN_QUEUE, State.PARTY_CHECK]
        if state not in valids:
            raise WrongGroupState(state, valids)

        user.ready = False
        if self.groups[user.groupid].state == State.IN_QUEUE:
            await self.leave_queue(user.groupid)
    
    @fake_async
    def is_user_ready(self, userid):
        return self.users[userid].ready

    @fake_async
    def leave_group(self, userid):
        user = self.users.get(userid)
        if user is None or user.groupid is None:
            raise PlayerNotInGroup()
        group = self.groups[user.groupid]

        valids = [State.GROUP_CHECK, State.IN_QUEUE]
        if group.state not in valids:
            raise WrongGroupState(state, valids)
        
        if group.state == State.IN_QUEUE:
            self.leave_queue(self, None, group)
        del self.users[userid]
        group.members.remove(userid)
        if not group.members:
            del self.groups[user.groupid]
    
    @fake_async
    def get_user(self, userid):
        user = self.users.get(userid)
        if user is None:
            raise PlayerNotInGroup()
        return user


    @fake_async
    def get_group(self, groupid):
        group = self.groups.get(groupid)
        if group is None:
            raise GroupDoesntExist()
        return self.groups[groupid]


    async def join_queue(self, groupid):
        group = self.groups.get(groupid)
        if group is None:
            raise GroupDoesntExist()
        if group.state != State.GROUP_CHECK:
            raise WrongGroupState(group.state, State.GROUP_CHECK)
        group.state = State.IN_QUEUE
        
        for userid in group.members:
            if not self.users[userid].ready:
                raise GroupNotReady()

        game = await RDB.get_game_by_id(group.gameid)

        game_queue = self.queues.get(game.gameid)
        if game_queue is None:
            game_queue = self.queues[game.gameid] = []

        for slotid in game_queue:
            slot = self.slots[slotid]
            size = len(slot.players) + len(group.members)
            if size <= game.capacity:
                slot.players.extend(group.members)
                slot.groups.append(groupid)
                group.slotid = slotid
                if size == game.capacity:
                    ensure_future(self.start_game(slotid))
                break
        else:
            slotid = uuid4()
            group.slotid = slotid
            slot = self.slots[slotid] = Slot(group.members.copy(), [groupid])
            self.queues[game.gameid].append(slotid)
            if len(slot.players) == game.capacity:
                ensure_future(self.start_game(slotid))

    @fake_async
    def leave_queue(self, groupid, group=None):
        if group is None:
            group = self.groups.get(groupid)
            if group is None:
                raise GroupDoesntExist()
            if group.state != State.IN_QUEUE:
                raise GroupNotInQueue()

        slot = self.slots[group.slotid]
        slot.groups.remove(groupid)
        for member in group.members:
            slot.players.remove(member)
        if not slot.groups:
            del self.slots[group.slotid]
            self.queues[group.gameid].remove(group.slotid)
        group.slotid = None
        group.state = State.GROUP_CHECK

    async def send_message(self, queue, id_, payload):
        await self.msgqueues[queue][id_].put(json_dumps(payload).encode())

    async def recv_messages(self, queue, id_):
        while True:
            yield await self.msgqueues[queue][id_].get()
