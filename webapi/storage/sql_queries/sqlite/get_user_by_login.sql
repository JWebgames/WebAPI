SELECT userid, name, email, password, isadmin, isverified
FROM tbuser
WHERE name=:login OR email=:login
