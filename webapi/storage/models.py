"""Data models"""

from collections import Iterable
from enum import Enum
from json import dumps as json_dumps
from typing import NamedTuple, List, Optional
from uuid import UUID

class JSONable:
    """Mixin that add asdict and asjson methods"""
    def asdict(self):
        """Return the inner __dict__ converted to json-friendly python dict"""
        dict_ = self.__dict__.copy()
        for key, value in dict_.items():
            if not isinstance(value, (bytes, str)) and isinstance(value, Iterable):
                for idx, sub_value in enumerate(value.copy()):
                    if isinstance(sub_value, UUID):
                        dict_[key][idx] = str(sub_value)
            elif isinstance(value, UUID):
                dict_[key] = str(value)
            elif isinstance(value, Enum):
                dict_[key] = value.name
        return dict_

    def asjson(self):
        """Return the inner __dict__ converted to json dict"""
        return json_dumps(self.asdict())


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
    """Enum of message group"""
    USER = "user"
    GROUP = "group"
    PARTY = "party"


class User(JSONable):
    """User model"""
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
        return tmpl.format(**self.asdict())


class Game(JSONable):
    """Game model"""
    gameid: int
    name: str
    ownerid: UUID
    capacity: int
    image: str
    port: int

    def __init__(self, gameid, name, ownerid, capacity, image, ports):
        self.gameid = int(gameid)
        self.name = name
        self.ownerid = ownerid if isinstance(ownerid, UUID) else UUID(ownerid)
        self.capacity = int(capacity)
        self.image = image
        if isinstance(ports, Iterable):
            self.ports = list(map(int, ports))
        else:
            self.ports = [int(ports)]


class Group(JSONable):
    """Group model"""
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


class UserKVS(JSONable):
    """User model"""
    groupid: Optional[UUID]
    partyid: Optional[UUID]
    ready: bool

    def __init__(self, groupid, partyid, ready):
        self.groupid = groupid
        self.partyid = partyid
        self.ready = ready


class Slot(JSONable):
    """Slot model"""
    players: List[UUID]
    groups: List[UUID]

    def __init__(self, players, groups):
        self.players = players
        self.groups = groups


class Party(JSONable):
    """Slot model"""
    gameid: UUID
    slotid: UUID
    host: str
    ports: List[int]

    def __init__(self, gameid, slotid, host, ports):
        self.gameid = gameid
        self.slotid = slotid
        self.host = host
        self.ports = ports


class Message(NamedTuple):
    """Message model"""
    msgid: UUID
    timestamp: float
    message: str
