CREATE TABLE tbgames (
    gameid smallserial NOT NULL PRIMARY KEY,
    name varchar(24) NOT NULL UNIQUE,
    ownerid uuid NOT NULL,
    capacity smallint NOT NULL,

    CONSTRAINT fk_ownerid FOREIGN KEY (ownerid)
        REFERENCES tbusers
        ON UPDATE CASCADE
        ON DELETE RESTRICT
);

CREATE FUNCTION create_game(name varchar(24), ownerid uuid, capacity smallint) RETURNS smallint AS $$
    INSERT INTO tbgames (name, ownerid, capacity)
    VALUES (name, ownerid, capacity)
    RETURNING gameid
$$ LANGUAGE SQL;

CREATE FUNCTION get_all_games() RETURNS tbgames AS $$
    SELECT gameid, name
    FROM tbgames
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
