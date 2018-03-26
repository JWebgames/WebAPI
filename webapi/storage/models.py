"""Data models"""

from typing import NamedTuple, Optionnal, List
from uuid import UUID

class User(NamedTuple):
    userid: UUID
    name: str
    email: str
    password: bytes
    isverified: bool
    isadmin: bool

class Game(NamedTuple):
    gameid: int
    name: str
    ownerid: UUID

class Party(NamedTuple):
    partyid: UUID
    gameid: int
    playerids: Optionnal[List[UUID]] = None

class LinkPartyUser(NamedTuple):
    partyid: UUID
    userid: UUID
