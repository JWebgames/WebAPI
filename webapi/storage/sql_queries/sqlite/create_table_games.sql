CREATE TABLE IF NOT EXISTS tbgames (
    gameid INTEGER NOT NULL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    ownerid TEXT NOT NULL,
    capacity INTEGER NOT NULL,

    CONSTRAINT fk_ownerid FOREIGN KEY (ownerid)
        REFERENCES tbusers
        ON UPDATE CASCADE
        ON DELETE RESTRICT
)
