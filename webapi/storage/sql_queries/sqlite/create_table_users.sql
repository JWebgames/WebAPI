CREATE TABLE IF NOT EXISTS tbusers (
    userid TEXT NOT NULL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL UNIQUE,
    password BLOB NOT NULL,
    isadmin INTEGER NOT NULL DEFAULT 0,
    isverified INTEGER NOT NULL DEFAULT 0,

    CONSTRAINT chk_isadmin CHECK (isadmin in (0, 1)),
    CONSTRAINT chk_isverified CHECK (isverified in (0, 1))
)
