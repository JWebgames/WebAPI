CREATE TABLE tbgames (
    gameid smallserial NOT NULL PRIMARY KEY,
    name varchar(24) NOT NULL UNIQUE,
    ownerid uuid NOT NULL,

    CONSTRAINT fk_ownerid FOREIGN KEY (ownerid)
        REFERENCES tbusers
        ON UPDATE CASCADE
        ON DELETE RESTRICT
);

CREATE FUNCTION create_game(name varchar(24), ownerid uuid) RETURNS smallint AS $$
    INSERT INTO tbgames (name, ownerid)
    VALUES (name, ownerid)
    RETURNING gameid
$$ LANGUAGE SQL;

CREATE FUNCTION get_game_by_id(gameid smallint) RETURNS tbgames AS $$
    SELECT *
    FROM tbgames
    WHERE gameid = gameid
$$ LANGUAGE SQL;

CREATE FUNCTION get_game_by_name(name varchar(24)) RETURNS tbgames AS $$
    SELECT *
    FROM tbgames
    WHERE name = name
$$ LANGUAGE SQL;

CREATE FUNCTION get_games_by_owner(ownerid uuid) RETURNS tbgames as $$
    SELECT *
    FROM tbgames
    WHERE ownerid = ownerid
$$ LANGUAGE SQL;

CREATE FUNCTION set_game_owner(gameid smallint, ownerid uuid) RETURNS VOID as $$
    UPDATE tbgames
    SET ownerid = ownerid
    WHERE gameid = gameid
$$ LANGUAGE SQL;