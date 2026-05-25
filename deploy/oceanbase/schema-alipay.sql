ALTER USER root IDENTIFIED BY '<ALIPAY_TENANT_PASSWORD>';

CREATE DATABASE IF NOT EXISTS alipay_demo;
USE alipay_demo;

CREATE TABLE IF NOT EXISTS users (
    id BIGINT NOT NULL PRIMARY KEY,
    username VARCHAR(64) NOT NULL,
    balance DECIMAL(18,2) NOT NULL DEFAULT 0.00,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_username (username)
);

CREATE TABLE IF NOT EXISTS transactions (
    id BIGINT NOT NULL PRIMARY KEY,
    from_user_id BIGINT,
    to_user_id BIGINT,
    amount DECIMAL(18,2) NOT NULL,
    type VARCHAR(32) NOT NULL COMMENT 'transfer/red_packet_send/red_packet_receive',
    remark VARCHAR(255),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    KEY idx_from_user (from_user_id),
    KEY idx_to_user (to_user_id),
    KEY idx_created_at (created_at)
);

CREATE TABLE IF NOT EXISTS red_packets (
    id BIGINT NOT NULL PRIMARY KEY,
    sender_id BIGINT NOT NULL,
    total_amount DECIMAL(18,2) NOT NULL,
    total_count INT NOT NULL,
    remaining_count INT NOT NULL,
    remaining_amount DECIMAL(18,2) NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'active' COMMENT 'active/finished/expired',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    KEY idx_sender_id (sender_id),
    KEY idx_status_created_at (status, created_at)
);

CREATE TABLE IF NOT EXISTS red_packet_grabs (
    id BIGINT NOT NULL PRIMARY KEY,
    red_packet_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    amount DECIMAL(18,2) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    KEY idx_packet_id (red_packet_id),
    KEY idx_user_id (user_id),
    UNIQUE KEY uk_packet_user (red_packet_id, user_id)
);
