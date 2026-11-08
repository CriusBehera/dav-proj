-- Run once:  mysql -u root -p < schema.sql
CREATE DATABASE IF NOT EXISTS dav_db;
USE dav_db;

CREATE TABLE IF NOT EXISTS users (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    username      VARCHAR(50)  NOT NULL UNIQUE,
    login_email   VARCHAR(255) NULL UNIQUE,   -- for email and Google sign-in (kept private)
    provider      VARCHAR(20) NOT NULL DEFAULT 'password',  -- 'password' or 'google'
    password_hash VARCHAR(255) NULL,          -- empty for Google-only accounts
    totp_secret   VARCHAR(64) NULL,           -- authenticator app key (two-step sign-in)
    backup_codes  TEXT NULL,                  -- hashed one-time backup codes
    failed_attempts INT NOT NULL DEFAULT 0,   -- wrong passwords in a row
    locked_until  DATETIME NULL,              -- set after too many wrong passwords
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS notes (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    title      VARCHAR(150) NOT NULL,
    body       TEXT,
    user_id    INT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);
