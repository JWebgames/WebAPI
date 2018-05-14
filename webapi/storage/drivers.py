"""Interfaces and implementation of databases drivers"""

from asyncio import ensure_future, gather
from collections import OrderedDict, Iterable, defaultdict
from datetime import datetime, timedelta
from logging import getLogger
from operator import methodcaller
from os import listdir
from os.path import join as pathjoin
from pathlib import Path
from time import time
from asyncpg import Record
from sqlite3 import connect as sqlite3_connect
from .models import User, Game, LightGame, \
                    Group, UserKVS, Slot, Message, \
                    State, MsgQueueType
from ..tools import root, fake_async
from webapi.exceptions import PlayerInGroupAlready, \
                              PlayerNotInGroup, \
                              GroupDoesntExist, \
                              GroupIsFull, \
                              GroupNotReady, \
                              WrongGroupState, \
                              GameDoesntExist
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
                query = await self.conn.prepare("SELECT %s()" % name)

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
    
    async def get_group_of_user(self, userid):
        """Get the group of the user"""
        raise NotImplementedError()
    
    async def mark_as_ready(self, userid):
        """Mark self as ready"""
        raise NotImplementedError()
    
    async def mark_as_not_ready(self, userid):
        """Mark self as not ready (group-check/party-check)"""
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
    
    async def send_message(self, queue, id_, payload):
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
        self.redis = redis_pool

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
        if (await self.scard(group_members_key)) == 0:
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
        queue = Redis.msgqueue_key.format(queue, id_)
        await self.redis.publish(queue, json.dumps(payload).encode("utf-8"))



class InMemory(KeyValueStore):
    """Implementation database-free"""
    def __init__(self):
        self.token_revocation_list = []  # List[tokenid]]
        self.users = {}  # Dict[userid, UserKVS]
        self.groups = {}  # Dict[groupid, Group]
        self.queues = {}  # Dict[gameid, List[slotid]]
        self.slots = {}  # Dict[slotid, Slot]
        self.parties = {}  # Dict[partyid, Party]
        self.msgqueue = {
            MsgQueueType.USER: defaultdict(list),
            MsgQueueType.GROUP: defaultdict(list),
            MsgQueueType.PARTY: defaultdict(list),
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
            raise PlayerInGroupAlready
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
    def get_group_of_user(self, userid):
        user = self.users.get(userid)
        if user is None:
            raise PlayerNotInGroup()
        return self.groups[user.groupid]

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
    def leave_group(self, userid):
        user = self.users.get(userid)
        if user is None or user.groupid is None:
            raise PlayerNotInGroup()
        
        group = self.groups[user.groupid]
        if group.state == State.IN_QUEUE:
            self.leave_queue(self, None, group)
        del self.users[userid]
        group.members.remove(userid)
        if not group.members:
            del self.groups[groupid]
    
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

    @fake_async
    def send_message(self, queue, id_, message, msgid=None, timestamp=None):
        if msgid is None:
            msgid = uuid4()
        if timestamp is None:
            timestamp = time()

        self.msgqueues[queue][id_].append(
            Message(msgid=msgid, timestamp=timestamp, message=message))
    
    @fake_async
    def recv_messages(self, queue, id_, since=None):
        if since is None:
            since=datetime.utcnow() - timedelta(seconds=5)
        
        return list(filter(lambda msg: msg.timestamp >= since, 
                           self.msgqueue[queue].get(id_, [])))
