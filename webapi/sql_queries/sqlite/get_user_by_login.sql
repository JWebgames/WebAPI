SELECT userid, name, email, password, isadmin
FROM tbusers
WHERE name=:login OR email=:login
