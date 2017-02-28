CREATE TABLE orgunit_groups(
    id SERIAL PRIMARY KEY NOT NULL,
    name TEXT NOT NULL DEFAULT '',
    dhis2id TEXT NOT NULL DEFAULT '',
    cdate TIMESTAMP DEFAULT NOW()
);

CREATE TABLE districts(
    id SERIAL PRIMARY KEY NOT NULL,
    name TEXT NOT NULL DEFAULT '',
    dhis2id TEXT NOT NULL DEFAULT '',
    cdate TIMESTAMP DEFAULT NOW(),
    ldate TIMESTAMP DEFAULT NOW()
);

CREATE TABLE facilities(
    id SERIAL PRIMARY KEY NOT NULL,
    name TEXT NOT NULL DEFAULT '',
    dhis2id TEXT NOT NULL DEFAULT '',
    uuid TEXT DEFAULT '',
    district TEXT NOT NULL DEFAULT '',
    is_033b BOOLEAN DEFAULT 'f',
    level TEXT NOT NULL DEFAULT '',
    subcounty TEXT NOT NULL DEFAULT '',
    cdate TIMESTAMP DEFAULT NOW(),
    ldate TIMESTAMP DEFAULT NOW()
);

CREATE TABLE sessions (
    session_id CHAR(128) UNIQUE NOT NULL,
    atime TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    data TEXT
);

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE users (
    id bigserial NOT NULL PRIMARY KEY,
    cdate timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
    firstname TEXT NOT NULL,
    lastname TEXT NOT NULL,
    username TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL, -- blowfish hash of password
    email TEXT,
    -- user_role  BIGINT NOT NULL REFERENCES user_roles ON DELETE RESTRICT ON UPDATE CASCADE,
    transaction_limit TEXT DEFAULT '0/'||to_char(NOW(),'yyyymmdd'),
    is_active BOOLEAN NOT NULL DEFAULT 't',
    is_system_user BOOLEAN NOT NULL DEFAULT 'f'

);

-- Some Data
copy districts (id, name, dhis2id) from 'districts.csv' delimiter ',' csv header;

INSERT INTO users(firstname,lastname,username,password,email,is_system_user)
VALUES
        ('Samuel','Sekiwere','admin',crypt('admin',gen_salt('bf')),'sekiskylink@gmail.com','t');
