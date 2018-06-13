"""Helper module for admin use"""

import asyncio
from getpass import getpass
from secrets import token_bytes
from uuid import uuid4
from scrypt import encrypt as scrypt_encrypt
from .config import show as show_config
from .server import connect_to_postgres
from .storage import drivers
from .tools import ask_bool, lruc

def wizard():
    """Database configuration wizard"""
    loop = asyncio.get_event_loop()

    print("Current configuration: ")
    show_config(short_output=True)

    print()
    if ask_bool("Configure postgres ?"):
        loop.run_until_complete(connect_to_postgres(None, loop))

        if ask_bool("Initialize the database ?"):
            loop.run_until_complete(drivers.RDB.install())

        if ask_bool("Create a user ?"):
            userid = uuid4()
            print("Userid:", userid)
            name = input("Username: ")
            mail = input("Email: ")
            pwd = getpass("Password: ")
            hpwd = scrypt_encrypt(token_bytes(64), pwd, maxtime=0.1)
            print("Hashed password: {}...".format(hpwd[:25]))
            if ask_bool("Process with user creation ?"):
                coro = drivers.RDB.create_user(userid, name, mail, hpwd)
                loop.run_until_complete(coro)
                print("Done")
            else:
                print("Canceled")

        if ask_bool("Update a user ?"):
            login = input("Username/email of the user you want to change: ")
            coro = drivers.RDB.get_user_by_login(login)
            user = loop.run_until_complete(coro)
            print(user)
            action = "Remove" if user.isadmin else "Grant"
            if ask_bool("%s admin privileges ?" % action):
                coro = drivers.RDB.set_user_admin(user.userid, not user.isadmin)
                loop.run_until_complete(coro)
                print("Done")

        if ask_bool("Create a game ?"):
            name = input("Game name: ")
            user = lruc(drivers.RDB.get_user_by_login(input("Owner login: ")))
            cap = int(input("Capacity: "))
            img = input("Image: ")
            ports = [int(input("Port: "))]
            while True:
                port = input("Another Port (leave blank to exit): ")
                if not port:
                    break
                ports.append(int(port))
            if ask_bool("Process with game creation ?"):
                lruc(drivers.RDB.create_game(name, user.userid, cap, img, ports))
                print("Done")
