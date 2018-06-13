"""Interfaces and implementation of databases drivers"""

from asyncio import ensure_future, gather, Queue
from collections import defaultdict
from json import dumps as json_dumps
from logging import getLogger, StreamHandler, Formatter
from operator import methodcaller
from os import listdir
from os.path import join as pathjoin
from pathlib import Path
from random import sample
from sqlite3 import connect as sqlite3_connect
from time import time
from uuid import UUID, uuid4

import zmq
import zmq.asyncio
from aioredis import Redis as AIORedis

from .models import User, Game, State, MsgQueueType, \
                    Group, UserKVS, Slot, Party
from .. import config
from ..server import RDB, KVS, CTR, MSG
from ..tools import root, fake_async
from ..exceptions import PlayerInGroupAlready, \
                         PlayerNotInGroup, \
                         GroupDoesntExist, \
                         GroupIsFull, \
                         GroupNotReady, \
                         WrongGroupState, \
                         GameDoesntExist, \
                         NotFoundError, \
                         PartyDoesntExist


logger = getLogger(__name__)

game_logger = getLogger("game")
game_logger.propagate = False
game_handler = StreamHandler()
game_handler.formatter = Formatter("<{name}> {message}", style="{")
game_logger.handlers = [game_handler]


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

    async def create_game(self, name, ownerid, capacity, image, ports):
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

    async def set_game_owner(self, gameid, ownerid):
        """Change the owner of a game"""
        raise NotImplementedError()


class Postgres(RelationalDataBase):
    """Implementation for postgres"""
    def __init__(self, pgpool):
        self.pool = pgpool

    async def install(self):
        """Create tables and functions"""
        sqldir = pathjoin(root(), "storage", "sql_queries", "postgres")
        async with self.pool.acquire() as conn:
            for file in sorted(listdir(sqldir)):
                with Path(sqldir).joinpath(file).open() as sqlfile:
                    for sql in filter(methodcaller("strip"), sqlfile.read().split(";")):
                        status = await conn.execute(sql)
                        logger.debug("%s", status)

    async def create_user(self, userid, name, email, hashed_password):
        async with self.pool.acquire() as conn:
            query = await conn.prepare("SELECT create_user($1, $2, $3, $4)")
            await query.fetch(userid, name, email, hashed_password)

    async def get_user_by_login(self, login):
        async with self.pool.acquire() as conn:
            query = await conn.prepare("SELECT * FROM get_user_by_login($1)")
            user = await query.fetchrow(login)
        if user["userid"] is None:
            raise NotFoundError()
        return User(**dict(user.items()))

    async def get_user_by_id(self, id_):
        async with self.pool.acquire() as conn:
            query = await conn.prepare("SELECT * FROM get_user_by_id($1)")
            user = await query.fetchrow(id_)
        if user["userid"] is None:
            raise NotFoundError()
        return User(**dict(user.items()))

    async def set_user_admin(self, userid, value):
        async with self.pool.acquire() as conn:
            query = await conn.prepare("SELECT set_user_admin($1, $2)")
            await query.fetch(userid, value)

    async def set_user_verified(self, userid, value):
        async with self.pool.acquire() as conn:
            query = await conn.prepare("SELECT set_user_verified($1, $2)")
            await query.fetch(userid, value)

    async def create_game(self, name, ownerid, capacity, image, ports):
        async with self.pool.acquire() as conn:
            query = await conn.prepare("SELECT create_game($1, $2, $3, $4, $5)")
            gameid = await query.fetchrow(name, ownerid, capacity, image, ports)
        return gameid[0]

    async def get_game_by_id(self, id_):
        async with self.pool.acquire() as conn:
            query = await conn.prepare("SELECT * FROM get_game_by_id($1)")
            game = await query.fetchrow(id_)
        if game["gameid"] is None:
            raise NotFoundError()
        return Game(**dict(game.items()))

    async def get_all_games(self):
        async with self.pool.acquire() as conn:
            query = await conn.prepare("SELECT * FROM get_all_games()")
            games = await query.fetch()

        return map(lambda game: Game(**dict(game.items())), games)

    async def get_game_by_name(self, name):
        async with self.pool.acquire() as conn:
            query = await conn.prepare("SELECT * FROM get_game_by_name($1)")
            game = await query.fetchrow(name)
        if game["gameid"] is None:
            raise NotFoundError()
        return Game(**dict(game.items()))

    async def get_games_by_owner(self, ownerid):
        async with self.pool.acquire() as conn:
            query = await conn.prepare("SELECT * FROM get_games_by_owner($1)")
            games = await query.fetch()

        return map(lambda game: Game(**dict(game.items())), games)

    async def set_game_owner(self, gameid, ownerid):
        async with self.pool.acquire() as conn:
            query = await conn.prepare("SELECT set_game_owner($1, $2)")
            await query.fetch(gameid, ownerid)

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
            query = self.conn.cursor().execute(sqlfile.read(), [str(id_)])
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

    async def create_game(self, name, ownerid, capacity, image, ports):
        with self.sqldir.joinpath("create_game.sql").open() as sqlfile:
            self.conn.cursor().execute(sqlfile.read(),
                [name, str(ownerid), capacity, image, ports[0]])

        query = "SELECT last_insert_rowid()"
        return self.conn.cursor().execute(query).fetchone()[0]

    async def get_game_by_id(self, id_):
        with self.sqldir.joinpath("get_game_by_id.sql").open() as sqlfile:
            query = self.conn.cursor().execute(sqlfile.read(), [str(id_)])
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

    async def get_games_by_owner(self, ownerid):
        with self.sqldir.joinpath("get_games_by_owner.sql").open() as sqlfile:
            query = self.conn.cursor().execute(sqlfile.read(), [ownerid])
            games = query.fetchall()
            return map(lambda game: Game(*game), games)

    async def set_game_owner(self, gameid, ownerid):
        with self.sqldir.joinpath("set_game_owner.sql").open() as sqlfile:
            self.conn.cursor().execute(sqlfile.read(), [gameid, ownerid])


class KeyValueStore():
    """Interface for key-value store access"""
    async def revoke_token(self, token) -> None:
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

    async def start_game(self, gameid, slotid):
        """Prepare the database to start a game"""
        raise NotImplementedError()

    async def get_party(self, partyid):
        """Get party info"""
        raise NotImplementedError()

    async def end_game(self, partyid):
        """Clean the dabatase at the end of a game"""
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
    party_gameid_key = "parties:{!s}:gameid"
    party_slotid_key = "parties:{!s}:slotid"
    party_host_key = "parties:{!s}:host"
    party_ports_key = "parties:{!s}:ports"
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
        await self.redis.delete(Redis.user_ready_key.format(userid))
        await self.redis.srem(
            Redis.group_members_key.format(groupid), str(userid))

        ensure_future(self.group_cleanup(groupid))

    async def group_cleanup(self, groupid):
        """Remove keys from redis"""
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
        return (await self.redis.get(Redis.user_ready_key.format(userid))) == b"1"

    async def is_group_ready(self, groupid):
        """Check the readiness of each member of a group"""
        return all(await gather(*[
            self.is_user_ready(userid.decode()) for userid in
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
        if not await self.is_group_ready(groupid):
            raise GroupNotReady()
        await self.redis.set(group_state_key, State.IN_QUEUE.value)

        game = await RDB.get_game_by_id(gameid)
        group_members_key = Redis.group_members_key.format(groupid)
        group_members = await self.redis.smembers(group_members_key)

        game_queue_key = Redis.game_queue_key.format(gameid)
        slotids = await self.redis.lrange(
            game_queue_key, 0, await self.redis.llen(game_queue_key))
        for slotid in [UUID(slotid.decode()) for slotid in slotids]:
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
                    ensure_future(self.start_game(gameid, slotid))
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
                ensure_future(self.start_game(gameid, slotid))

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

    async def start_game(self, gameid, slotid):
        partyid = str(uuid4())
        payload = {"type": "game:starting", "partyid": str(partyid)}

        groups = await self.redis.smembers(Redis.slot_groups_key.format(slotid))
        for groupid in map(methodcaller("decode"), groups):
            await MSG.send_message(MsgQueueType.GROUP, groupid, payload)
            await self.redis.set(
                Redis.group_state_key.format(groupid), State.PLAYING.value)
            await self.redis.set(
                Redis.group_partyid_key.format(groupid), partyid)

        users = await self.redis.smembers(Redis.slot_players_key.format(slotid))
        for userid in map(methodcaller("decode"), users):
            await self.redis.set(
                Redis.user_partyid_key.format(userid), partyid)

        await self.redis.lrem(Redis.game_queue_key.format(gameid), 1, str(slotid))

        game = await RDB.get_game_by_id(gameid)
        party = Party(gameid, slotid, config.webapi.GAME_HOST,
                      sorted(sample(range(config.webapi.GAME_PORT_RANGE_START,
                                          config.webapi.GAME_PORT_RANGE_STOP),
                                    len(game.ports))))
        await self.redis.set(
            Redis.party_gameid_key.format(partyid), str(party.gameid))
        await self.redis.set(
            Redis.party_slotid_key.format(partyid), str(party.slotid))
        await self.redis.set(
            Redis.party_host_key.format(partyid), party.host)
        await self.redis.sadd(
            Redis.party_ports_key.format(partyid), *party.ports)

        ensure_future(CTR.launch_game(gameid, game, partyid, party))

    async def get_party(self, partyid):
        gameid = await self.redis.get(Redis.party_gameid_key.format(partyid))
        if gameid is None:
            raise PartyDoesntExist()
        slotid = await self.redis.get(Redis.party_slotid_key.format(partyid))
        host = await self.redis.get(Redis.party_host_key.format(partyid))
        ports = await self.redis.get(Redis.party_ports_key.format(partyid))

        return Party(gameid=UUID(gameid.decode()),
                     slotid=UUID(slotid.decode()),
                     host=host.decode(),
                     ports=list(map(int, ports)))

    async def end_game(self, partyid):
        slotid = await self.redis.get(Redis.party_slotid_key.format(partyid))
        slotid = UUID(slotid.decode())

        groups = await self.redis.smembers(Redis.slot_groups_key.format(slotid))
        for groupid in map(methodcaller("decode"), groups):
            await self.redis.set(
                Redis.group_state_key.format(groupid), State.GROUP_CHECK.value)
            await self.redis.delete(Redis.group_partyid_key.format(groupid))

        users = await self.redis.smembers(Redis.slot_players_key.format(slotid))
        for userid in map(methodcaller("decode"), users):
            await self.redis.delete(Redis.user_partyid_key.format(userid))

        await self.redis.delete(Redis.party_gameid_key.format(partyid))
        await self.redis.delete(Redis.party_slotid_key.format(partyid))
        await self.redis.delete(Redis.party_host_key.format(partyid))
        await self.redis.delete(Redis.party_ports_key.format(partyid))
        await self.redis.delete(Redis.slot_players_key.format(slotid))
        await self.redis.delete(Redis.slot_groups_key.format(slotid))


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
    def is_token_revoked(self, token_id) -> bool:
        return token_id in self.token_revocation_list

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
            raise WrongGroupState(group.state, valids)

        if group.state == State.IN_QUEUE:
            self.leave_queue(self, None, group)
        del self.users[userid]
        group.members.remove(userid)
        if not group.members:
            del self.groups[user.groupid]

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
                    ensure_future(self.start_game(game.gameid, slotid))
                break
        else:
            slotid = uuid4()
            group.slotid = slotid
            slot = self.slots[slotid] = Slot(group.members.copy(), [groupid])
            self.queues[game.gameid].append(slotid)
            if len(slot.players) == game.capacity:
                ensure_future(self.start_game(game.gameid, slotid))

    @fake_async
    def leave_queue(self, groupid):
        group = self.groups.get(groupid)
        if group is None:
            raise GroupDoesntExist()
        if group.state != State.IN_QUEUE:
            raise WrongGroupState(group.state, State.IN_QUEUE)

        slot = self.slots[group.slotid]
        slot.groups.remove(groupid)
        for member in group.members:
            slot.players.remove(member)
        if not slot.groups:
            del self.slots[group.slotid]
            self.queues[group.gameid].remove(group.slotid)
        group.slotid = None
        group.state = State.GROUP_CHECK

    async def start_game(self, gameid, slotid):
        partyid = uuid4()
        payload = {"type": "game:starting", "partyid": str(partyid)}
        slot = self.slots[slotid]
        for groupid in slot.groups:
            await MSG.send_message(MsgQueueType.GROUP, groupid, payload)
            group = self.groups[groupid]
            group.state = State.PLAYING
            group.partyid = partyid
        for userid in slot.players:
            self.users[userid].partyid = partyid

        self.queues[group.gameid].remove(group.slotid)

        game = await RDB.get_game_by_id(gameid)
        party = Party(gameid, slotid, config.webapi.GAME_HOST,
                      sorted(sample(range(config.webapi.GAME_PORT_RANGE_START,
                                          config.webapi.GAME_PORT_RANGE_STOP),
                                    len(game.ports))))
        self.parties[partyid] = party

        ensure_future(CTR.launch_game(gameid, game, partyid, party))

    @fake_async
    def get_party(self, partyid):
        return self.parties[partyid]

    @fake_async
    def end_game(self, partyid):
        slotid = self.parties[partyid].slotid
        slot = self.slots[slotid]
        for groupid in slot.groups:
            group = self.groups[groupid]
            group.state = State.GROUP_CHECK
            group.partyid = None
        for userid in slot.players:
            self.users[userid].partyid = None

        del self.slots[slotid]
        del self.parties[partyid]


class Messager:
    """Send and recieve message over ZeroMQ"""

    def __init__(self):
        self.context = zmq.asyncio.Context()
        self.pusher = self.context.socket(zmq.PUSH)
        self.pusher.connect(config.messager.PULL_ADDRESS)
        logger.debug("Connected to messager puller running on %s",
                     config.messager.PULL_ADDRESS)

    async def send_message(self, queue, id_, payload):
        """PUSH a message to be PUB by the Messager"""
        await self.pusher.send_string(
            "{}:{!s} {}".format(queue.value, id_, json_dumps(payload)))

    async def recv_messages(self, queue, id_):
        """SUB to messages PUB by th Message"""
        sub_pattern = "{}:{!s}".format(queue.value, id_)
        suber = self.context.socket(zmq.SUB)
        suber.connect(config.messager.PUB_ADDRESS)
        logger.debug("Connected to messager publisher running on %s",
                     config.messager.PUB_ADDRESS)
        suber.setsockopt_string(zmq.SUBSCRIBE, sub_pattern)
        logger.debug("Recieving message for pattern %s",
                     sub_pattern)

        sentinel = object()
        yield sentinel
        while True:
            if ((yield (await suber.recv_string())[len(sub_pattern) + 1:])
                is sentinel):
                break
        yield
        logger.debug("Stop recieving message for pattern %s "
                     "and closing connection", sub_pattern)
        suber.close()

    def close(self):
        """Cleanup"""
        self.pusher.close()

class Docker:
    """Docker driver"""
    def __init__(self, docker):
        self.docker = docker

    async def launch_game(self, gameid, game, partyid, party):
        """Launch a game in a container on the host machine"""
        container_config = {
            #"Cmd": ["-text", "hello"],
            #"Image": "hashicorp/http-echo",
            "Image": game.image,
            "AttachStdin": False,
            "AttachStdout": True,
            "AttachStderr": True,
            "Tty": False,
            "OpenStdin": False,
            "HostConfig": {
                "PortBindings": {
                    "{}/tcp".format(internal_port): [
                        {
                            "HostIp": "0.0.0.0",
                            "HostPort": str(external_port)
                        }
                    ]
                    for external_port, internal_port
                    in zip(party.ports, game.ports)
                }
            }
        }

        logger.info(
            "Starting a match of %s (ID: %d) using match ID %s...",
            game.name, gameid, partyid)
        container = await self.docker.containers.run(config=container_config)
        logger.info("Game started.")

        payload = {"type": "game:started", "host": party.host, "ports": party.ports}
        await MSG.send_message(MsgQueueType.PARTY, partyid, payload)

        party_logger = getLogger("game.{!s}.{!s}".format(gameid, partyid))
        async for line in await container.log(stdout=True, stderr=True, follow=True):
            party_logger.debug(line.strip())
        await container.wait()
        logger.info("Game over")

        await KVS.end_game(partyid)

        payload = {"type": "game:over"}
        await MSG.send_message(MsgQueueType.PARTY, partyid, payload)
