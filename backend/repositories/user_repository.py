#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
USER_DIR = BASE_DIR / 'user'
DB_PATH = USER_DIR / 'users.db'


class ClosingConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            return super().__exit__(exc_type, exc_val, exc_tb)
        finally:
            self.close()


def get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), factory=ClosingConnection)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.execute(
            '''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                status TEXT NOT NULL DEFAULT 'active',
                session_version INTEGER NOT NULL DEFAULT 1,
                force_password_change INTEGER NOT NULL DEFAULT 0,
                password_reset_token_hash TEXT,
                password_reset_expires_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_login_at TEXT
            )
            '''
        )
        # Schema migration: add session_version for existing deployments.
        cur = conn.execute("PRAGMA table_info(users)")
        cols = {row['name'] if isinstance(row, sqlite3.Row) else row[1] for row in cur.fetchall()}
        if 'session_version' not in cols:
            conn.execute('ALTER TABLE users ADD COLUMN session_version INTEGER NOT NULL DEFAULT 1')
        if 'force_password_change' not in cols:
            conn.execute('ALTER TABLE users ADD COLUMN force_password_change INTEGER NOT NULL DEFAULT 0')
        if 'password_reset_token_hash' not in cols:
            conn.execute('ALTER TABLE users ADD COLUMN password_reset_token_hash TEXT')
        if 'password_reset_expires_at' not in cols:
            conn.execute('ALTER TABLE users ADD COLUMN password_reset_expires_at TEXT')
        conn.commit()


def find_by_username(username: str):
    with get_conn() as conn:
        cur = conn.execute('SELECT * FROM users WHERE username = ?', (username,))
        return cur.fetchone()


def find_by_id(user_id: int):
    with get_conn() as conn:
        cur = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,))
        return cur.fetchone()


def list_users():
    with get_conn() as conn:
        cur = conn.execute(
            'SELECT id, username, role, status, force_password_change, created_at, updated_at, last_login_at FROM users ORDER BY id ASC'
        )
        return cur.fetchall()


def list_users_paginated(keyword: str = '', role: str = '', page: int = 1, page_size: int = 20):
    normalized_page = max(1, int(page or 1))
    normalized_page_size = max(1, min(100, int(page_size or 20)))
    offset = (normalized_page - 1) * normalized_page_size

    conditions = []
    params = []

    if role:
        conditions.append('role = ?')
        params.append(role)

    if keyword:
        like_value = f'%{keyword}%'
        conditions.append('(username LIKE ? OR CAST(id AS TEXT) LIKE ? OR role LIKE ?)')
        params.extend([like_value, like_value, like_value])

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ''

    with get_conn() as conn:
        count_cur = conn.execute(
            f'SELECT COUNT(*) AS c FROM users {where_clause}',
            tuple(params),
        )
        total_row = count_cur.fetchone()
        total = int(total_row['c']) if total_row else 0

        data_cur = conn.execute(
            f'''
            SELECT id, username, role, status, force_password_change, created_at, updated_at, last_login_at
            FROM users
            {where_clause}
            ORDER BY id ASC
            LIMIT ? OFFSET ?
            ''',
            tuple(params + [normalized_page_size, offset]),
        )
        return data_cur.fetchall(), total


def create_user(username: str, password_hash: str, role: str, status: str, now_iso: str, force_password_change: bool = True):
    with get_conn() as conn:
        cur = conn.execute(
            '''
            INSERT INTO users (username, password_hash, role, status, session_version, force_password_change, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (username, password_hash, role, status, 1, 1 if force_password_change else 0, now_iso, now_iso),
        )
        conn.commit()
        return cur.lastrowid


def update_login_time(user_id: int, now_iso: str):
    with get_conn() as conn:
        conn.execute(
            'UPDATE users SET last_login_at = ? WHERE id = ?',
            (now_iso, user_id),
        )
        conn.commit()


def update_user_meta(user_id: int, role: str = None, status: str = None, now_iso: str = None):
    fields = []
    values = []
    if role is not None:
        fields.append('role = ?')
        values.append(role)
    if status is not None:
        fields.append('status = ?')
        values.append(status)
    if now_iso is not None:
        fields.append('updated_at = ?')
        values.append(now_iso)

    # Role/status changes should revoke existing sessions for security.
    if role is not None or status is not None:
        fields.append('session_version = session_version + 1')

    if not fields:
        return

    values.append(user_id)
    sql = f"UPDATE users SET {', '.join(fields)} WHERE id = ?"
    with get_conn() as conn:
        conn.execute(sql, tuple(values))
        conn.commit()


def update_password(user_id: int, password_hash: str, now_iso: str):
    with get_conn() as conn:
        conn.execute(
            '''
            UPDATE users
            SET password_hash = ?,
                updated_at = ?,
                session_version = session_version + 1,
                force_password_change = 0,
                password_reset_token_hash = NULL,
                password_reset_expires_at = NULL
            WHERE id = ?
            ''',
            (password_hash, now_iso, user_id),
        )
        conn.commit()


def set_force_password_change(user_id: int, required: bool, now_iso: str):
    with get_conn() as conn:
        conn.execute(
            'UPDATE users SET force_password_change = ?, updated_at = ? WHERE id = ?',
            (1 if required else 0, now_iso, user_id),
        )
        conn.commit()


def set_password_reset_token(user_id: int, token_hash: str, expires_at_iso: str, now_iso: str):
    with get_conn() as conn:
        conn.execute(
            '''
            UPDATE users
            SET password_reset_token_hash = ?,
                password_reset_expires_at = ?,
                force_password_change = 1,
                updated_at = ?,
                session_version = session_version + 1
            WHERE id = ?
            ''',
            (token_hash, expires_at_iso, now_iso, user_id),
        )
        conn.commit()


def find_by_valid_reset_token(token_hash: str, now_iso: str):
    with get_conn() as conn:
        cur = conn.execute(
            '''
            SELECT *
            FROM users
            WHERE password_reset_token_hash = ?
              AND password_reset_expires_at IS NOT NULL
              AND password_reset_expires_at >= ?
              AND status = 'active'
            LIMIT 1
            ''',
            (token_hash, now_iso),
        )
        return cur.fetchone()


def clear_password_reset_token(user_id: int, now_iso: str):
    with get_conn() as conn:
        conn.execute(
            '''
            UPDATE users
            SET password_reset_token_hash = NULL,
                password_reset_expires_at = NULL,
                updated_at = ?
            WHERE id = ?
            ''',
            (now_iso, user_id),
        )
        conn.commit()


def delete_user(user_id: int):
    with get_conn() as conn:
        conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
        conn.commit()


def count_active_admin_users() -> int:
    with get_conn() as conn:
        cur = conn.execute("SELECT COUNT(*) AS c FROM users WHERE role = 'admin' AND status = 'active'")
        row = cur.fetchone()
        return int(row['c']) if row else 0


def count_admin_users() -> int:
    return count_active_admin_users()
