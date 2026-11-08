-- Adds email + Google sign-in to an existing database (run once).
--   Local:  mysql -u root dav_db < migrate_auth.sql
--   TiDB:   python3 load_db.py --host HOST --user USER --file migrate_auth.sql
USE dav_db;
ALTER TABLE users ADD COLUMN login_email VARCHAR(255) NULL;
ALTER TABLE users ADD COLUMN provider VARCHAR(20) NOT NULL DEFAULT 'password';
ALTER TABLE users MODIFY password_hash VARCHAR(255) NULL;
CREATE UNIQUE INDEX users_login_email ON users (login_email);
