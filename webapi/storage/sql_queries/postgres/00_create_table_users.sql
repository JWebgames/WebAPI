CREATE TABLE tbusers (
    userid uuid PRIMARY KEY,
    name varchar(24) UNIQUE,
    email varchar(254) UNIQUE,
    password bytea NOT NULL,
    isadmin boolean NOT NULL DEFAULT FALSE,
    isverified boolean NOT NULL DEFAULT FALSE,

    CONSTRAINT chk_name CHECK (name ~* '^\w{3,}$'),
    CONSTRAINT chk_name_not_email CHECK (name !~* '^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$'),
    CONSTRAINT chk_email CHECK (email ~* '^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$')
);

CREATE FUNCTION create_user(userid uuid, name varchar(24), email varchar(254), password bytea) RETURNS VOID AS $$
    INSERT INTO tbusers (userid, name, email, password)
    VALUES (userid, name, email, password)
$$ LANGUAGE SQL;

CREATE FUNCTION get_user_by_id(arg_userid uuid) RETURNS tbusers AS $$
    SELECT *
    FROM tbusers
    WHERE userid = arg_userid
$$ LANGUAGE SQL;

CREATE FUNCTION get_user_by_login(login varchar(254)) RETURNS tbusers AS $$
    SELECT *
    FROM tbusers
    WHERE name = login OR email = login
$$ LANGUAGE SQL;

CREATE FUNCTION set_user_verified(arg_userid uuid, value boolean) RETURNS VOID AS $$
    UPDATE tbusers
    SET isverified = value
    WHERE userid = arg_userid
$$ LANGUAGE SQL;

CREATE FUNCTION set_user_admin(arg_userid uuid, value boolean) RETURNS VOID AS $$
    UPDATE tbusers
    SET isadmin = value
    WHERE userid = arg_xuserid
$$ LANGUAGE SQL;
