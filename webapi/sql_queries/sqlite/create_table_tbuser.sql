CREATE TABLE IF NOT EXISTS tbuser (
    userid BLOB NOT NULL,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    password BLOB NOT NULL,
    salt BLOB NOT NULL,
    isadmin INTEGER DEFAULT 0,

    CONSTRAINT pk PRIMARY KEY (userid),
    CONSTRAINT uk_name UNIQUE (name),
    CONSTRAINT uk_email UNIQUE (email),
    CONSTRAINT chk_isadmin CHECK (isadmin in (0, 1))
)
