
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

CREATE TABLE IF NOT EXISTS warehouses (
    id       INT AUTO_INCREMENT PRIMARY KEY,
    name     VARCHAR(100) NOT NULL UNIQUE,
    location VARCHAR(150)
);

CREATE TABLE IF NOT EXISTS products (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    sku           VARCHAR(30)  NOT NULL UNIQUE,
    name          VARCHAR(150) NOT NULL,
    category      VARCHAR(60),
    price         DECIMAL(10,2) NOT NULL,
    cost          DECIMAL(10,2) NOT NULL DEFAULT 0,
    reorder_level INT NOT NULL DEFAULT 10,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS stock (
    product_id   INT NOT NULL,
    warehouse_id INT NOT NULL,
    qty          INT NOT NULL DEFAULT 0,
    PRIMARY KEY (product_id, warehouse_id)
);

CREATE TABLE IF NOT EXISTS customers (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    name       VARCHAR(120) NOT NULL,
    email      VARCHAR(150),
    phone      VARCHAR(30),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS orders (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    customer_id  INT NOT NULL,
    warehouse_id INT NOT NULL,
    status       VARCHAR(20) NOT NULL DEFAULT 'pending',
    total        DECIMAL(12,2) NOT NULL DEFAULT 0,
    created_by   INT NULL,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS order_items (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    order_id   INT NOT NULL,
    product_id INT NOT NULL,
    qty        INT NOT NULL,
    unit_price DECIMAL(10,2) NOT NULL
);

CREATE TABLE IF NOT EXISTS payments (
    id       INT AUTO_INCREMENT PRIMARY KEY,
    order_id INT NOT NULL,
    amount   DECIMAL(12,2) NOT NULL,
    method   VARCHAR(20) NOT NULL DEFAULT 'upi',
    note     VARCHAR(200),
    paid_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
