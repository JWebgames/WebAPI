CREATE TABLE tbgames (
    gameid smallserial NOT NULL PRIMARY KEY,
    name character varying (24) NOT NULL UNIQUE,
    ownerid uuid NOT NULL,

    CONSTRAINT fk_ownerid FOREIGN KEY (tbusers)
        REFERENCES userid
        ON UPDATE CASCADE
        ON DELETE RESTRICT
);

CREATE FUNCTION create_game(character varying (24), uuid) RETURNS smallserial AS $$
    INSERT INTO tb_games (name, ownerid)
    VALUES ($1)
    RETURNING gameid
$$ LANGUAGE SQL;

CREATE FUNCTION get_game_by_id(smallserial) RETURNS tbgames AS $$
    SELECT *
    FROM tbgames
    WHERE gameid = $1
$$ LANGUAGE SQL;

CREATE FUNCTION get_game_by_name(character varying (24)) RETURNS tbgames AS $$
    SELECT *
    FROM tbgames
    WHERE name = $1
$$ LANGUAGE SQL;

CREATE FUNCTION get_games_by_owner(uuid) RETURN tbgames as $$
    SELECT *
    FROM tbgames
    WHERE ownerid = $1
$$ LANGUAGE SQL;

CREATE FUNCTION set_game_owner(uuid, uuid) RETURN VOID as $$
    UPDATE tbgames
    SET ownerid = $2
    WHERE gameid = $1
$$
