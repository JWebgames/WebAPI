if __name__ == "__main__":
    # Prevent server.py from beeing imported twice
    from server import start
    from sys import exit
    start()
    exit(0)

def start():
    import __main__
    if "exit" in dir(__main__):
        print("Hack")
    pass
