#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / 'data'
DB_PATH = DATA_DIR / 'app_meta.db'


class ClosingConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            return super().__exit__(exc_type, exc_val, exc_tb)
        finally:
            self.close()


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), factory=ClosingConnection)
    conn.row_factory = sqlite3.Row
    return conn


_init_lock = threading.Lock()
_initialized_db_path = None


def init_db():
    # 同一 DB 路径在进程内只初始化一次；测试替换 DB_PATH 后会按新路径重新初始化
    global _initialized_db_path
    with _init_lock:
        if _initialized_db_path == str(DB_PATH):
            return
        _init_db_schema()
        _initialized_db_path = str(DB_PATH)


def _init_db_schema():
    with _connect() as conn:
        conn.execute(
            '''
            CREATE TABLE IF NOT EXISTS runtime_locks (
                lock_key TEXT PRIMARY KEY,
                owner TEXT NOT NULL,
                expires_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
            '''
        )
        conn.execute(
            '''
            CREATE TABLE IF NOT EXISTS auth_rate_limits (
                rate_key TEXT PRIMARY KEY,
                window_start REAL NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                lock_until REAL NOT NULL DEFAULT 0,
                updated_at REAL NOT NULL
            )
            '''
        )
        conn.execute(
            '''
            CREATE TABLE IF NOT EXISTS password_reset_deliveries (
                delivery_id TEXT PRIMARY KEY,
                issuer_user_id INTEGER NOT NULL,
                target_user_id INTEGER NOT NULL,
                reset_token TEXT NOT NULL,
                reset_token_expires_at TEXT NOT NULL,
                created_at REAL NOT NULL,
                expires_at REAL NOT NULL,
                consumed_at REAL
            )
            '''
        )
        conn.execute('CREATE INDEX IF NOT EXISTS idx_runtime_locks_expires_at ON runtime_locks(expires_at)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_auth_rate_limits_lock_until ON auth_rate_limits(lock_until)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_password_reset_deliveries_expires_at ON password_reset_deliveries(expires_at)')
        conn.commit()


def _iso_to_ts(iso_value: str) -> float:
    try:
        dt = datetime.fromisoformat((iso_value or '').strip())
        # Reset token expiry is generated with datetime.utcnow().isoformat().
        # For naive datetime values, treat them as UTC to avoid local-time skew.
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except Exception:
        return 0.0


def save_password_reset_delivery(
    delivery_id: str,
    issuer_user_id: int,
    target_user_id: int,
    reset_token: str,
    reset_token_expires_at: str,
):
    init_db()
    now = time.time()
    token_expire_ts = _iso_to_ts(reset_token_expires_at)
    # Delivery record should never outlive token validity.
    delivery_expire_ts = token_expire_ts if token_expire_ts > now else now

    with _connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        conn.execute(
            '''
            INSERT OR REPLACE INTO password_reset_deliveries (
                delivery_id, issuer_user_id, target_user_id, reset_token,
                reset_token_expires_at, created_at, expires_at, consumed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL)
            ''',
            (
                delivery_id,
                int(issuer_user_id),
                int(target_user_id),
                reset_token,
                reset_token_expires_at,
                now,
                delivery_expire_ts,
            ),
        )
        # Opportunistic cleanup keeps table small without introducing a new task.
        conn.execute(
            'DELETE FROM password_reset_deliveries WHERE expires_at <= ? OR consumed_at IS NOT NULL',
            (now,),
        )
        conn.commit()


def consume_password_reset_delivery(delivery_id: str, issuer_user_id: int):
    """Consume and return reset token once.

    Returns tuple:
      ('ok', {'reset_token': str, 'reset_token_expires_at': str, 'target_user_id': int})
      ('not_found', None)
      ('forbidden', None)
      ('expired', None)
      ('used', None)
    """
    init_db()
    now = time.time()

    with _connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        cur = conn.execute(
            '''
            SELECT delivery_id, issuer_user_id, target_user_id, reset_token,
                   reset_token_expires_at, expires_at, consumed_at
            FROM password_reset_deliveries
            WHERE delivery_id = ?
            ''',
            (delivery_id,),
        )
        row = cur.fetchone()
        if not row:
            conn.commit()
            return 'not_found', None

        if int(row['issuer_user_id']) != int(issuer_user_id):
            conn.commit()
            return 'forbidden', None

        if row['consumed_at'] is not None:
            conn.commit()
            return 'used', None

        expires_at = float(row['expires_at'] or 0)
        token_expire_ts = _iso_to_ts(row['reset_token_expires_at'])
        if expires_at <= now or token_expire_ts <= now:
            conn.execute('DELETE FROM password_reset_deliveries WHERE delivery_id = ?', (delivery_id,))
            conn.commit()
            return 'expired', None

        conn.execute(
            'UPDATE password_reset_deliveries SET consumed_at = ? WHERE delivery_id = ?',
            (now, delivery_id),
        )
        conn.commit()
        return 'ok', {
            'reset_token': row['reset_token'],
            'reset_token_expires_at': row['reset_token_expires_at'],
            'target_user_id': int(row['target_user_id']),
        }


def acquire_lock(lock_key: str, owner: str, ttl_seconds: int) -> tuple[bool, int]:
    """Try acquiring a lock with TTL. Return (acquired, retry_after_seconds)."""
    init_db()
    now = time.time()
    expires_at = now + max(1, int(ttl_seconds))

    with _connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        cur = conn.execute('SELECT owner, expires_at FROM runtime_locks WHERE lock_key = ?', (lock_key,))
        row = cur.fetchone()

        if not row:
            conn.execute(
                'INSERT INTO runtime_locks (lock_key, owner, expires_at, updated_at) VALUES (?, ?, ?, ?)',
                (lock_key, owner, expires_at, now),
            )
            conn.commit()
            return True, 0

        current_expires = float(row['expires_at'])
        if current_expires <= now:
            conn.execute(
                'UPDATE runtime_locks SET owner = ?, expires_at = ?, updated_at = ? WHERE lock_key = ?',
                (owner, expires_at, now, lock_key),
            )
            conn.commit()
            return True, 0

        conn.commit()
        return False, max(1, int(current_expires - now))


def release_lock(lock_key: str, owner: Optional[str] = None):
    init_db()
    with _connect() as conn:
        if owner:
            conn.execute('DELETE FROM runtime_locks WHERE lock_key = ? AND owner = ?', (lock_key, owner))
        else:
            conn.execute('DELETE FROM runtime_locks WHERE lock_key = ?', (lock_key,))
        conn.commit()


def check_login_allowed(rate_key: str, window_seconds: int) -> tuple[bool, int]:
    """Return (allowed, retry_after_seconds)."""
    init_db()
    now = time.time()
    window = max(1, int(window_seconds))

    with _connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        # 顺手清理窗口与锁均已过期的限流行，避免表无界增长
        conn.execute(
            'DELETE FROM auth_rate_limits WHERE lock_until <= ? AND window_start <= ?',
            (now, now - window),
        )
        cur = conn.execute(
            'SELECT window_start, attempts, lock_until FROM auth_rate_limits WHERE rate_key = ?',
            (rate_key,),
        )
        row = cur.fetchone()
        if not row:
            conn.execute(
                'INSERT INTO auth_rate_limits (rate_key, window_start, attempts, lock_until, updated_at) VALUES (?, ?, 0, 0, ?)',
                (rate_key, now, now),
            )
            conn.commit()
            return True, 0

        lock_until = float(row['lock_until'] or 0)
        if lock_until > now:
            conn.commit()
            return False, max(1, int(lock_until - now))

        window_start = float(row['window_start'] or now)
        if now - window_start > window:
            conn.execute(
                'UPDATE auth_rate_limits SET window_start = ?, attempts = 0, lock_until = 0, updated_at = ? WHERE rate_key = ?',
                (now, now, rate_key),
            )
        conn.commit()
        return True, 0


def record_login_failure(rate_key: str, window_seconds: int, max_attempts: int, lock_seconds: int) -> tuple[bool, int]:
    """Record failed login. Return (locked_now, retry_after_seconds)."""
    init_db()
    now = time.time()
    window = max(1, int(window_seconds))
    max_attempts = max(1, int(max_attempts))
    lock_seconds = max(1, int(lock_seconds))

    with _connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        cur = conn.execute(
            'SELECT window_start, attempts, lock_until FROM auth_rate_limits WHERE rate_key = ?',
            (rate_key,),
        )
        row = cur.fetchone()
        if not row:
            conn.execute(
                'INSERT INTO auth_rate_limits (rate_key, window_start, attempts, lock_until, updated_at) VALUES (?, ?, 1, 0, ?)',
                (rate_key, now, now),
            )
            conn.commit()
            return False, 0

        window_start = float(row['window_start'] or now)
        attempts = int(row['attempts'] or 0)

        if now - window_start > window:
            window_start = now
            attempts = 0

        attempts += 1
        lock_until = 0.0
        if attempts >= max_attempts:
            lock_until = now + lock_seconds

        conn.execute(
            'UPDATE auth_rate_limits SET window_start = ?, attempts = ?, lock_until = ?, updated_at = ? WHERE rate_key = ?',
            (window_start, attempts, lock_until, now, rate_key),
        )
        conn.commit()

        if lock_until > now:
            return True, max(1, int(lock_until - now))
        return False, 0


def clear_login_failures(rate_key: str):
    init_db()
    with _connect() as conn:
        conn.execute('DELETE FROM auth_rate_limits WHERE rate_key = ?', (rate_key,))
        conn.commit()
