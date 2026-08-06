#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3
import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / 'data'
DB_PATH = DATA_DIR / 'app_meta.db'


class ClosingConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            return super().__exit__(exc_type, exc_val, exc_tb)
        finally:
            self.close()


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat()


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
            CREATE TABLE IF NOT EXISTS detection_jobs (
                id TEXT PRIMARY KEY,
                target_scope TEXT NOT NULL,
                status TEXT NOT NULL,
                progress INTEGER NOT NULL DEFAULT 0,
                step TEXT,
                message TEXT,
                created_by_id INTEGER,
                created_by_username TEXT,
                remote_job_id TEXT,
                remote_status TEXT,
                remote_message TEXT,
                remote_error_message TEXT,
                remote_artifact_url TEXT,
                remote_last_callback_at TEXT,
                webhook_last_event_id TEXT,
                remote_artifact_path TEXT,
                local_artifact_path TEXT,
                snapshot_key TEXT,
                error_message TEXT,
                cancel_requested INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                started_at TEXT,
                finished_at TEXT,
                updated_at TEXT NOT NULL
            )
            '''
        )
        conn.execute(
            '''
            CREATE TABLE IF NOT EXISTS detection_job_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL,
                level TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            '''
        )
        conn.execute('CREATE INDEX IF NOT EXISTS idx_detection_jobs_status ON detection_jobs(status)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_detection_events_job_id ON detection_job_events(job_id, id DESC)')
        _ensure_column(conn, 'detection_jobs', 'remote_status', 'TEXT')
        _ensure_column(conn, 'detection_jobs', 'remote_message', 'TEXT')
        _ensure_column(conn, 'detection_jobs', 'remote_error_message', 'TEXT')
        _ensure_column(conn, 'detection_jobs', 'remote_artifact_url', 'TEXT')
        _ensure_column(conn, 'detection_jobs', 'remote_last_callback_at', 'TEXT')
        _ensure_column(conn, 'detection_jobs', 'webhook_last_event_id', 'TEXT')
        _ensure_column(conn, 'detection_jobs', 'target_regions_json', 'TEXT')
        conn.commit()


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, column_type: str):
    cur = conn.execute(f'PRAGMA table_info({table})')
    existing = {row['name'] for row in cur.fetchall()}
    if column in existing:
        return
    conn.execute(f'ALTER TABLE {table} ADD COLUMN {column} {column_type}')


def _normalize_target_regions(regions) -> list[str]:
    if not isinstance(regions, list):
        return []
    normalized = []
    seen = set()
    for item in regions:
        if not isinstance(item, str):
            continue
        value = item.strip()
        if not value or value in seen:
            continue
        normalized.append(value)
        seen.add(value)
    return normalized


def _decode_target_regions(raw) -> list[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except Exception:
        return []
    return _normalize_target_regions(data)


def _row_to_dict(row):
    if not row:
        return None
    payload = dict(row)
    payload['target_regions'] = _decode_target_regions(payload.get('target_regions_json'))
    return payload


def create_job(target_scope: str, created_by_id: int, created_by_username: str, target_regions=None) -> dict:
    init_db()
    job_id = uuid.uuid4().hex
    now = _now_iso()
    normalized_regions = _normalize_target_regions(target_regions)
    target_regions_json = json.dumps(normalized_regions, ensure_ascii=False)
    with _connect() as conn:
        conn.execute(
            '''
            INSERT INTO detection_jobs (
                id, target_scope, status, progress, step, message,
                created_by_id, created_by_username,
                target_regions_json,
                created_at, updated_at
            ) VALUES (?, ?, 'queued', 0, 'queued', '任务已创建', ?, ?, ?, ?, ?)
            ''',
            (job_id, target_scope, created_by_id, created_by_username, target_regions_json, now, now),
        )
        conn.execute(
            'INSERT INTO detection_job_events (job_id, level, message, created_at) VALUES (?, ?, ?, ?)',
            (job_id, 'info', '任务已创建', now),
        )
        conn.commit()
    return get_job(job_id)


def create_job_if_idle(target_scope: str, created_by_id: int, created_by_username: str, target_regions=None):
    """在单个写事务（BEGIN IMMEDIATE）中原子完成“活跃任务检查 + 创建”，避免并发创建竞态。

    返回 (job, active_count)：创建成功时 active_count 为 0；
    已存在活跃任务时 job 为 None，active_count 为当前活跃任务数。
    """
    init_db()
    job_id = uuid.uuid4().hex
    now = _now_iso()
    normalized_regions = _normalize_target_regions(target_regions)
    target_regions_json = json.dumps(normalized_regions, ensure_ascii=False)
    with _connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        cur = conn.execute(
            """
            SELECT COUNT(*) AS c
            FROM detection_jobs
            WHERE status IN ('queued', 'dispatching', 'running', 'artifact_ready', 'importing')
            """
        )
        row = cur.fetchone()
        active = int(row['c']) if row else 0
        if active > 0:
            conn.commit()
            return None, active
        conn.execute(
            '''
            INSERT INTO detection_jobs (
                id, target_scope, status, progress, step, message,
                created_by_id, created_by_username,
                target_regions_json,
                created_at, updated_at
            ) VALUES (?, ?, 'queued', 0, 'queued', '任务已创建', ?, ?, ?, ?, ?)
            ''',
            (job_id, target_scope, created_by_id, created_by_username, target_regions_json, now, now),
        )
        conn.execute(
            'INSERT INTO detection_job_events (job_id, level, message, created_at) VALUES (?, ?, ?, ?)',
            (job_id, 'info', '任务已创建', now),
        )
        conn.commit()
    return get_job(job_id), 0


def force_cancel_job(job_id: str, message: str, error_message: str = '') -> bool:
    """强制终结任务（仅当任务仍处于非终态时生效）。返回是否实际生效。"""
    now = _now_iso()
    with _connect() as conn:
        cur = conn.execute(
            """
            UPDATE detection_jobs
            SET status = 'canceled', progress = 100, step = 'canceled',
                message = ?, error_message = ?, cancel_requested = 1,
                finished_at = ?, updated_at = ?
            WHERE id = ? AND status NOT IN ('activated', 'failed', 'canceled')
            """,
            (message, error_message, now, now, job_id),
        )
        conn.commit()
        return cur.rowcount > 0


def update_job_if_active(job_id: str, **fields) -> bool:
    """仅当任务处于非终态时更新，避免异步回调覆盖编排器刚写入的终态。返回是否生效。"""
    if not fields:
        return False
    fields['updated_at'] = _now_iso()
    keys = list(fields.keys())
    sql = (
        f"UPDATE detection_jobs SET {', '.join(k + ' = ?' for k in keys)}"
        " WHERE id = ? AND status NOT IN ('activated', 'failed', 'canceled')"
    )
    values = [fields[k] for k in keys] + [job_id]
    with _connect() as conn:
        cur = conn.execute(sql, values)
        conn.commit()
        return cur.rowcount > 0


def get_job(job_id: str):
    init_db()
    with _connect() as conn:
        cur = conn.execute('SELECT * FROM detection_jobs WHERE id = ?', (job_id,))
        return _row_to_dict(cur.fetchone())


def list_jobs(limit: int = 50):
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            'SELECT * FROM detection_jobs ORDER BY created_at DESC LIMIT ?',
            (max(1, int(limit)),),
        )
        return [_row_to_dict(r) for r in cur.fetchall()]


def list_events(job_id: str, limit: int = 200):
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            '''
            SELECT id, job_id, level, message, created_at
            FROM detection_job_events
            WHERE job_id = ?
            ORDER BY id DESC
            LIMIT ?
            ''',
            (job_id, max(1, int(limit))),
        )
        rows = [dict(r) for r in cur.fetchall()]
    rows.reverse()
    return rows


def add_event(job_id: str, level: str, message: str):
    now = _now_iso()
    with _connect() as conn:
        conn.execute(
            'INSERT INTO detection_job_events (job_id, level, message, created_at) VALUES (?, ?, ?, ?)',
            (job_id, level, message, now),
        )
        conn.commit()


def update_job(job_id: str, **fields):
    if not fields:
        return
    fields['updated_at'] = _now_iso()
    keys = list(fields.keys())
    sql = f"UPDATE detection_jobs SET {', '.join(k + ' = ?' for k in keys)} WHERE id = ?"
    values = [fields[k] for k in keys] + [job_id]
    with _connect() as conn:
        conn.execute(sql, values)
        conn.commit()


def request_cancel(job_id: str) -> bool:
    with _connect() as conn:
        cur = conn.execute(
            'UPDATE detection_jobs SET cancel_requested = 1, updated_at = ? WHERE id = ?',
            (_now_iso(), job_id),
        )
        conn.commit()
        return cur.rowcount > 0


def is_cancel_requested(job_id: str) -> bool:
    with _connect() as conn:
        cur = conn.execute('SELECT cancel_requested FROM detection_jobs WHERE id = ?', (job_id,))
        row = cur.fetchone()
        return bool(row and int(row['cancel_requested']) == 1)


def claim_next_queued_job():
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "SELECT id FROM detection_jobs WHERE status = 'queued' ORDER BY created_at ASC LIMIT 1"
        )
        row = cur.fetchone()
        if not row:
            return None
        job_id = row['id']
        now = _now_iso()
        upd = conn.execute(
            """
            UPDATE detection_jobs
            SET status = 'dispatching', progress = 5, step = 'dispatching', message = '正在下发探测任务', started_at = ?, updated_at = ?
            WHERE id = ? AND status = 'queued'
            """,
            (now, now, job_id),
        )
        conn.commit()
        if upd.rowcount == 0:
            return None
    return get_job(job_id)


def count_active_jobs() -> int:
    with _connect() as conn:
        cur = conn.execute(
            """
            SELECT COUNT(*) AS c
            FROM detection_jobs
            WHERE status IN ('queued', 'dispatching', 'running', 'artifact_ready', 'importing')
            """
        )
        row = cur.fetchone()
        return int(row['c']) if row else 0


def apply_remote_callback(
    job_id: str,
    remote_job_id: str,
    remote_status: str,
    message: str,
    error_message: str,
    artifact_download_url: str,
    event_id: str,
    occurred_at: str,
) -> dict:
    """
    幂等写入远端回调快照。
    返回: {applied: bool, reason: str}
    """
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            '''
            SELECT remote_job_id, webhook_last_event_id, remote_last_callback_at, status, remote_status
            FROM detection_jobs
            WHERE id = ?
            ''',
            (job_id,),
        )
        row = cur.fetchone()
        if not row:
            return {'applied': False, 'reason': 'job_not_found'}

        local_status = (row['status'] or '').strip().lower()
        if local_status in {'activated', 'failed', 'canceled'}:
            return {'applied': False, 'reason': 'job_finished'}

        existing_remote_job_id = (row['remote_job_id'] or '').strip()
        if existing_remote_job_id and remote_job_id and existing_remote_job_id != remote_job_id:
            return {'applied': False, 'reason': 'remote_job_id_mismatch'}

        last_event_id = (row['webhook_last_event_id'] or '').strip()
        if event_id and last_event_id and event_id == last_event_id:
            return {'applied': False, 'reason': 'duplicate_event'}

        last_callback_at = (row['remote_last_callback_at'] or '').strip()
        if occurred_at and last_callback_at and occurred_at < last_callback_at:
            return {'applied': False, 'reason': 'stale_event'}

        prev_remote_status = (row['remote_status'] or '').strip().lower()
        terminal_remote = {'succeeded', 'failed', 'canceled'}
        if prev_remote_status in terminal_remote and remote_status != prev_remote_status:
            return {'applied': False, 'reason': 'remote_terminal_immutable'}

        now = _now_iso()
        conn.execute(
            '''
            UPDATE detection_jobs
            SET
                remote_job_id = COALESCE(NULLIF(?, ''), remote_job_id),
                remote_status = ?,
                remote_message = ?,
                remote_error_message = ?,
                remote_artifact_url = ?,
                remote_last_callback_at = ?,
                webhook_last_event_id = COALESCE(NULLIF(?, ''), webhook_last_event_id),
                updated_at = ?
            WHERE id = ?
            ''',
            (
                remote_job_id,
                remote_status,
                message,
                error_message,
                artifact_download_url,
                occurred_at or now,
                event_id,
                now,
                job_id,
            ),
        )
        conn.commit()
        return {'applied': True, 'reason': 'ok'}


def clear_finished_jobs() -> dict:
    """Delete clearable jobs and orphan events.

    Clearable jobs include:
    - terminal jobs: activated / failed / canceled
    - orphan queued/dispatching jobs with no remote_job_id (typically stale local placeholders)
    """
    init_db()
    terminal = ('activated', 'failed', 'canceled')
    pre_total = 0
    pre_orphan = 0
    with _connect() as conn:
        cur_pre_total = conn.execute(
            f"SELECT COUNT(*) AS c FROM detection_jobs WHERE status IN ({','.join('?' for _ in terminal)})",
            terminal,
        )
        row_pre_total = cur_pre_total.fetchone()
        pre_total = int(row_pre_total['c']) if row_pre_total else 0

        cur_pre_orphan = conn.execute(
            """
            SELECT COUNT(*) AS c
            FROM detection_jobs
            WHERE status IN ('queued', 'dispatching')
              AND COALESCE(remote_job_id, '') = ''
            """
        )
        row_pre_orphan = cur_pre_orphan.fetchone()
        pre_orphan = int(row_pre_orphan['c']) if row_pre_orphan else 0

        cur_jobs = conn.execute(
            f"""
            DELETE FROM detection_jobs
            WHERE status IN ({','.join('?' for _ in terminal)})
               OR (
                   status IN ('queued', 'dispatching')
                   AND COALESCE(remote_job_id, '') = ''
               )
            """,
            terminal,
        )
        deleted_jobs = int(cur_jobs.rowcount or 0)

        cur_events = conn.execute(
            '''
            DELETE FROM detection_job_events
            WHERE job_id NOT IN (SELECT id FROM detection_jobs)
            '''
        )
        deleted_events = int(cur_events.rowcount or 0)
        conn.commit()

    return {
        'deletedJobs': deleted_jobs,
        'deletedTerminalJobs': pre_total,
        'deletedOrphanJobs': pre_orphan,
        'deletedEvents': deleted_events,
    }
