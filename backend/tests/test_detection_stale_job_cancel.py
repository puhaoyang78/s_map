#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""回归测试：卡死检测任务在 cancel 路径被强制终结（修复项 1）。"""

import os
import shutil
import sqlite3
import sys
import types
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import Flask

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

if 'tasks.celery_app' not in sys.modules:
    fake_celery_app = types.ModuleType('tasks.celery_app')
    fake_celery_app.enqueue_detection_job = lambda *args, **kwargs: 'fake-task-id'
    fake_celery_app.init_celery = lambda: None
    sys.modules['tasks.celery_app'] = fake_celery_app

from repositories import detection_job_repository as job_repo
from repositories import user_repository
from routes import detection_jobs_route
from utils.auth import issue_token

TMP_ROOT = Path(__file__).resolve().parent / '.tmp'


def make_test_dir(prefix: str) -> Path:
    TMP_ROOT.mkdir(exist_ok=True)
    path = TMP_ROOT / f'{prefix}{uuid.uuid4().hex}'
    path.mkdir(parents=True, exist_ok=False)
    return path


class StaleJobCancelTests(unittest.TestCase):
    def setUp(self):
        self._env_backup = dict(os.environ)
        os.environ['AUTH_SECRET'] = 'A' * 48

        self._old_job_data_dir = job_repo.DATA_DIR
        self._old_job_db_path = job_repo.DB_PATH
        self._old_user_dir = user_repository.USER_DIR
        self._old_user_db_path = user_repository.DB_PATH

        self._tmp_dir = make_test_dir('stale_cancel_test_')
        job_repo.DATA_DIR = self._tmp_dir
        job_repo.DB_PATH = self._tmp_dir / 'detection_jobs.db'
        user_repository.USER_DIR = self._tmp_dir
        user_repository.DB_PATH = self._tmp_dir / 'users.db'
        job_repo.init_db()
        user_repository.init_db()

        user_repository.create_user(
            'admin', 'unused-hash', 'admin', 'active', '2026-01-01T00:00:00',
            force_password_change=False,
        )
        user_row = user_repository.find_by_username('admin')
        self._token = issue_token(user_row)

        self.app = Flask(__name__)
        self.app.register_blueprint(detection_jobs_route.detection_jobs_bp)
        self.client = self.app.test_client()

    def tearDown(self):
        job_repo.DATA_DIR = self._old_job_data_dir
        job_repo.DB_PATH = self._old_job_db_path
        user_repository.USER_DIR = self._old_user_dir
        user_repository.DB_PATH = self._old_user_db_path
        os.environ.clear()
        os.environ.update(self._env_backup)
        shutil.rmtree(self._tmp_dir, ignore_errors=True)

    def _headers(self):
        return {'Authorization': f'Bearer {self._token}'}

    def _create_running_job(self, updated_at: str):
        job = job_repo.create_job('global', 1, 'admin')
        job_repo.update_job(job['id'], status='running', progress=35, step='running')
        conn = sqlite3.connect(str(job_repo.DB_PATH))
        try:
            conn.execute('UPDATE detection_jobs SET updated_at = ? WHERE id = ?', (updated_at, job['id']))
            conn.commit()
        finally:
            conn.close()
        return job

    def test_stale_job_is_force_canceled(self):
        # 默认最大运行时长 7200s，回溯 7300s 视为卡死
        old_ts = (datetime.now(timezone.utc) - timedelta(seconds=7300)).replace(tzinfo=None).isoformat()
        job = self._create_running_job(old_ts)

        resp = self.client.post(f'/api/detection/jobs/{job["id"]}/cancel', headers=self._headers())

        self.assertEqual(resp.status_code, 200)
        self.assertIn('强制取消', resp.get_json()['message'])
        final = job_repo.get_job(job['id'])
        self.assertEqual(final['status'], 'canceled')
        self.assertEqual(final['cancel_requested'], 1)
        self.assertTrue(final['finished_at'])

    def test_fresh_job_uses_normal_cancel_request(self):
        fresh_ts = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        job = self._create_running_job(fresh_ts)

        resp = self.client.post(f'/api/detection/jobs/{job["id"]}/cancel', headers=self._headers())

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()['message'], '取消请求已提交')
        final = job_repo.get_job(job['id'])
        self.assertEqual(final['status'], 'running')
        self.assertEqual(final['cancel_requested'], 1)

    def test_force_cancel_does_not_override_terminal_state(self):
        job = job_repo.create_job('global', 1, 'admin')
        job_repo.update_job(job['id'], status='failed', progress=100, step='failed')

        changed = job_repo.force_cancel_job(job['id'], message='强制取消')

        self.assertFalse(changed)
        self.assertEqual(job_repo.get_job(job['id'])['status'], 'failed')


if __name__ == '__main__':
    unittest.main()
