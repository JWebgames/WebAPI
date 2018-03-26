CREATE TABLE IF NOT EXISTS tbusers (
    userid BLOB NOT NULL,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    password BLOB NOT NULL,
    isadmin INTEGER DEFAULT 0,
    isverified INTEGER DEFAULT 0,

    CONSTRAINT pk PRIMARY KEY (userid),
    CONSTRAINT uk_name UNIQUE (name),
    CONSTRAINT uk_email UNIQUE (email),
    CONSTRAINT chk_isadmin CHECK (isadmin in (0, 1)),
    CONSTRAINT chk_isverified CHECK (isverified in (0, 1))
)
