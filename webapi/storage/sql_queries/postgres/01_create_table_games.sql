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

CREATE FUNCTION get_all_games() RETURNS SETOF tbgames AS $$
    SELECT *
    FROM tbgames
$$ LANGUAGE SQL;

CREATE FUNCTION get_game_by_id(arg_gameid smallint) RETURNS tbgames AS $$
    SELECT *
    FROM tbgames
    WHERE gameid = arg_gameid
$$ LANGUAGE SQL;

CREATE FUNCTION get_game_by_name(arg_name varchar(24)) RETURNS tbgames AS $$
    SELECT *
    FROM tbgames
    WHERE name = arg_name
$$ LANGUAGE SQL;

CREATE FUNCTION get_games_by_owner(arg_ownerid uuid) RETURNS SETOF tbgames as $$
    SELECT *
    FROM tbgames
    WHERE ownerid = arg_ownerid
$$ LANGUAGE SQL;

CREATE FUNCTION set_game_owner(arg_gameid smallint, ownerid uuid) RETURNS VOID as $$
    UPDATE tbgames
    SET ownerid = ownerid
    WHERE gameid = arg_gameid
$$ LANGUAGE SQL;
