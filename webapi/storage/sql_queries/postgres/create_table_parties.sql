CREATE TABLE tbparties (
    partyid uuid PRIMARY KEY,
    gameid smallserial NOT NULL,

    CONSTRAINT fk_gameid FOREIGN KEY (gameid)
        REFERENCES tbgames(gameid)
        ON UPDATE CASCADE
        ON DELETE CASCADE
);

CREATE TABLE link_parties_users (
    partyid uuid NOT NULL,
    userid uuid NOT NULL,

    CONSTRAINT pk PRIMARY KEY (partyid, userid),
    CONSTRAINT fk_partyid FOREIGN KEY (partyid)
        REFERENCES tbparties(partyid)
        ON UPDATE CASCADE
        ON DELETE CASCADE,
    CONSTRAINT fk_userid FOREIGN KEY (userid)
        REFERENCES tbusers
        ON UPDATE CASCADE
        ON DELETE RESTRICT
);

CREATE FUNCTION create_party(patyid uuid, gamename character varying (24), userids uuid ARRAY) RETURNS VOID AS $$
DECLARE
    uuserid uuid;
BEGIN
    INSERT INTO tb_parties (partyid, gameid) 
    VALUES (
        partyid,
        (SELECT gameid FROM get_game_by_name(gamename))
    );

    FOREACH userid IN ARRAY userids
    LOOP
        INSERT INTO link_parties_users (partyid, userid)
        VALUES (partyid, userid);
    END LOOP;
END;
$$ LANGUAGE plpgsql;
