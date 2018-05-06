"""Data models"""

from typing import NamedTuple, List, Optional
from uuid import UUID


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


class Group():
    members: List[UUID]
    gameid: Optional[UUID]
    slotid: Optional[UUID]
    partyid: Optional[UUID]

    def __init__(self, members, gameid, slotid, partyid):
        self.members = members
        self.gameid = gameid
        self.slotid = slotid
        self.partyid = partyid

    def asdict():
        return {
            "members": list(map(str, self.members)),
            "gameid": str(self.gameid),
            "slotid": str(self.slotid),
            "partyid": str(self.partyid)
        }

class UserKVS:
    groupid: Optional[UUID]
    is_ready: bool

    def __ini__(self, groupid, ready):
        self.groupid = groupid
        self.ready = ready
    
    def asdict():
        return {
            "groupid": str(self.groupid),
            "ready": self.ready
        }