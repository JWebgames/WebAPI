"""Data models"""

from typing import NamedTuple, List, Optional
from uuid import UUID
from enum import Enum

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
    USER = b"user"
    GROUP = b"group"
    PARTY = b"party"


class User(NamedTuple):
    userid: UUID
    name: str
    email: str
    password: bytes
    isverified: bool
    isadmin: bool

    def __str__(self):
        tmpl = "User(userid={userid}, name={name}, " \
               "email={email}, password=<not shown>, " \
               "isverified={isverified}, isadmin={isadmin})"
        return tmpl.format(**self._asdict())


class LightGame(NamedTuple):
    gameid: int
    name: str


class Game(NamedTuple):
    gameid: int
    name: str
    ownerid: UUID
    capacity: int


class Group:
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

    def asdict():
        return {
            "state": self.state.value,
            "members": list(map(str, self.members)),
            "gameid": str(self.gameid),
            "slotid": self.slotid and str(self.slotid),
            "partyid": self.partyid and str(self.partyid)
        }


class UserKVS:
    groupid: Optional[UUID]
    partyid: Optional[UUID]
    ready: bool

    def __init__(self, groupid, partyid, ready):
        self.groupid = groupid
        self.partyid = partyid
        self.ready = ready
    
    def asdict():
        return {
            "groupid": self.groupid and str(self.groupid),
            "partyid": self.partyid and str(self.partyid),
            "ready": self.ready
        }

class Slot:
    players: List[UUID]
    groups: List[UUID]

    def __init__(self, players, groups):
        self.players = players
        self.groups = groups
    
    def asdict():
        return {
            "members": list(map(str, self.members)),
            "groups": list(map(str, self.groups))
        }

class Party:
    slotid: UUID

    def __init__(self, slotid):
        self.slotid = slotid
    
    def asdict():
        return {
            "slotid": str(self.slotid)
        }

class Message(NamedTuple):
    msgid: UUID
    timestamp: float
    message: str

    def asdict(self):
        d = super()._asdict():
        d["msgid"] = str(d["msgid"])
        return d
