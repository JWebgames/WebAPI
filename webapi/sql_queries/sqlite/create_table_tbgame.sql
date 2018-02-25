CREATE TABLE IF NOT EXISTS tbgame (
    gameid BLOB NOT NULL,
    name TEXT NOT NULL,
    userid BLOB NOT NULL,

    CONSTRAINT pk PRIMARY KEY (gameid),
    CONSTRAINT uk_name UNIQUE (name),
    CONSTRAINT fk_userid FOREIGN KEY (userid)
        REFERENCES tbuser
        ON UPDATE CASCADE
        ON DELETE RESTRICT
)
