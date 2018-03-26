CREATE TABLE tbusers (
    userid uuid PRIMARY KEY,
    name character varying (24) UNIQUE,
    email character varying (254) UNIQUE,
    password bytea NOT NULL,
    isverified boolean NOT NULL DEFAULT FALSE,
    isadmin boolean NOT NULL DEFAULT FALSE,

    CONSTRAINT chk_nickname CHECK (nickname ~* '^\w{3,}$'),
    CONSTRAINT chk_nickname_not_email CHECK (nickname !~* '^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$'),
    CONSTRAINT chk_email CHECK (email ~* '^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$')
);

CREATE FUNCTION create_user(uuid, character varying (24), character varying (254), bytea) RETURNS VOID AS $$
    INSERT INTO tb_users (userid, nickname, email, password)
    VALUES ($1, $2, $3, $4)
$$ LANGUAGE SQL;

CREATE FUNCTION get_user_by_id(uuid) RETURNS tbusers AS $$
    SELECT *
    FROM tbusers
    WHERE userid = $1
$$ LANGUAGE SQL;

CREATE FUNCTION get_user_by_login(character varying (254)) RETURNS tbusers AS $$
    SELECT *
    FROM tbusers
    WHERE name = $1 OR email = $1
$$ LANGUAGE SQL;

CREATE FUNCTION set_user_verified(uuid) RETURNS VOID AS $$
    UPDATE tbusers
    SET isverified = True
    WHERE userid = $1
$$ LANGUAGE SQL;

CREATE FUNCTION set_user_admin(uuid) RETURNS VOID AS $$
    UPDATE tbusers
    SET isadmin = True
    WHERE userid = $1
$$ LANGUAGE SQL;
