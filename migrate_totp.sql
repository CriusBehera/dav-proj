-- Authenticator-app two-step sign-in (run once on an existing database).
--   Local:  mysql -u root dav_db < migrate_totp.sql
--   TiDB:   python3 load_db.py --host HOST --user USER --file migrate_totp.sql
USE dav_db;
ALTER TABLE users ADD COLUMN totp_secret VARCHAR(64) NULL;
ALTER TABLE users ADD COLUMN backup_codes TEXT NULL;
