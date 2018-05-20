"""Data models"""

from typing import NamedTuple, List, Optional, Tuple
from uuid import UUID
from enum import Enum
from collections import Iterable

class jsonable:
    def asdict(self):
        if hasattr(self, "_asdict"):
            dict_ = self._asdict()
        else:
            dict_ = self.__dict__.copy()
        for key, value in dict_.items():
            if type(value) is not str and isinstance(value, Iterable):
                for idx, sub_value in enumerate(value.copy()):
                    if isinstance(sub_value, UUID):
                        dict_[key][idx] = str(sub_value)
            elif isinstance(value, UUID):
                dict_[key] = str(value)
            elif isinstance(value, Enum):
                dict_[key] = value.name
        return dict_


class ClientType(Enum):
    """Enum of JWT user type"""
    ADMIN = "admin"
    PLAYER = "player"
    GAME = "game"
    WEBAPI = "webapi"
    MANAGER = "manager"


class State(Enum):
    """Enum of player states"""
    GROUP_CHECK = b"group-check"
    IN_QUEUE = b"in-queue"
    PARTY_CHECK = b"party-check"
    PLAYING = b"playing"


class MsgQueueType(Enum):
    USER = "user"
    GROUP = "group"
    PARTY = "party"


class User(jsonable):
    userid: UUID
    name: str
    email: str
    password: bytes
    isverified: bool
    isadmin: bool

    def __init__(self, userid, name, email, password, isverified, isadmin):
        self.userid = userid if isinstance(userid, UUID) else UUID(userid)
        self.name = name
        self.email = email
        self.password = password
        self.isverified = bool(isverified)
        self.isadmin = bool(isadmin)

    def __str__(self):
        tmpl = "User(userid={userid}, name={name}, " \
               "email={email}, password=<not shown>, " \
               "isverified={isverified}, isadmin={isadmin})"
        return tmpl.format(**self._asdict())


class Game(jsonable):
    gameid: int
    name: str
    ownerid: UUID
    capacity: int

    def __init__(self, gameid, name, ownerid, capacity):
        self.gameid = int(gameid)
        self.name = name
        self.ownerid = ownerid if isinstance(ownerid, UUID) else UUID(ownerid)
        self.capacity = int(capacity)


class Group(jsonable):
    state: State
    members: List[UUID]
    gameid: UUID
    slotid: Optional[UUID]
    partyid: Optional[UUID]

    def __init__(self, state, members, gameid, slotid, partyid):
        self.state = state
        self.members = members
        self.gameid = gameid
        self.slotid = slotid
        self.partyid = partyid


class UserKVS(jsonable):
    groupid: Optional[UUID]
    partyid: Optional[UUID]
    ready: bool

    def __init__(self, groupid, partyid, ready):
        self.groupid = groupid
        self.partyid = partyid
        self.ready = ready


class Slot(jsonable):
    players: List[UUID]
    groups: List[UUID]

    def __init__(self, players, groups):
        self.players = players
        self.groups = groups


class Party(jsonable):
    slotid: UUID

    def __init__(self, slotid):
        self.slotid = slotid


class Message(NamedTuple):
    msgid: UUID
    timestamp: float
    message: str
