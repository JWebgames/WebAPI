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


class Game(NamedTuple):
    gameid: int
    name: str
    capacity: int
    ownerid: UUID


class Group(NamedTuple):
    members: List[UUID]
    gameid: Optional[UUID]
    queueid: Optional[UUID]
    partyid: Optional[UUID]

