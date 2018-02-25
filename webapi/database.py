import sqlite3
from asyncio import coroutine
from typing import Optional, List
from os import listdir
from .tools import get_package_path


RDB : "RelationalDataBase"
KVS : "KeyValueStore"

class RelationalDataBase():
    async def create_user(self, userid, name, email, hashed_password, isadmin):
        raise NotImplementedError()

    async def get_user_by_login(self, login):
        raise NotImplementedError()


class Postgres(RelationalDataBase):
    def __init__(self, pgconn):
        self.conn = pgconn


class SQLite(RelationalDataBase):
    def __init__(self):
        dbfile = str(get_package_path().joinpath("data.sqlite3"))
        self.conn = sqlite3.connect(dbfile)
        self.queries = {}

        cur = self.conn.cursor()
        root = get_package_path().joinpath("sql_queries", "sqlite")
        for filename in listdir(str(root)):
            with root.joinpath(filename).open() as file:
                sql = file.read()
                if filename.startswith("create_table"):
                    cur.execute(sql)
                else:
                    query_name = filename[:filename.rindex(".")]
                    self.queries[query_name] = sql

    @coroutine
    def create_user(self, userid, name, email, hashed_password, isadmin):
        self.conn.cursor().execute(self.queries["create_user"], {
            "userid": userid,
            "name": name,
            "email": email,
            "password": hashed_password,
            "isadmin": int(isadmin)
        })

    @coroutine
    def get_user_by_login(self, login):
        return self.conn.cursor().execute(self.queries["get_user_by_login"], {
            "login": login
        }).fetchone()

    @coroutine
    def grant_admin(self, userid):
        cur = self.conn.cursor()
        cur.execute(self.queries["update_user_set_admin"], {userid: userid})



# =================


class KeyValueStore():
    def revoke_token(self, future, token) -> None:
        raise NotImplementedError()

    def is_token_revoked(self, future, token) -> bool:
        raise NotImplementedError()


class Redis(KeyValueStore):
    def __init__(self, redis_conn):
        self.conn = redis_conn


class InMemory(KeyValueStore):
    def __init__(self):
        self.token_revocation_list = []

    @coroutine
    def revoke_token(self, token_id):
        self.token_revocation_list.append(token_id)

    @coroutine
    def is_token_revoked(self, token_id) -> bool:
        return token_id in self.token_revocation_list


        