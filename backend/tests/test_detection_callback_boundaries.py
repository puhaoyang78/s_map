#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import shutil
import unittest
import uuid
from pathlib import Path

from repositories import detection_job_repository as repo

TMP_ROOT = Path(__file__).resolve().parent / '.tmp'


def make_test_dir(prefix: str) -> Path:
    TMP_ROOT.mkdir(exist_ok=True)
    path = TMP_ROOT / f'{prefix}{uuid.uuid4().hex}'
    path.mkdir(parents=True, exist_ok=False)
    return path


class DetectionCallbackBoundariesTests(unittest.TestCase):
    def setUp(self):
        self._old_data_dir = repo.DATA_DIR
        self._old_db_path = repo.DB_PATH
        self._tmp_dir = make_test_dir('detection_cb_test_')
        repo.DATA_DIR = self._tmp_dir
        repo.DB_PATH = self._tmp_dir / 'detection_jobs.db'
        repo.init_db()

    def tearDown(self):
        repo.DATA_DIR = self._old_data_dir
        repo.DB_PATH = self._old_db_path
        shutil.rmtree(self._tmp_dir, ignore_errors=True)

    def _create_running_job(self, remote_job_id='remote-1'):
        job = repo.create_job('device-1', 1, 'tester')
        repo.update_job(
            job['id'],
            status='running',
            remote_job_id=remote_job_id,
            remote_status='queued',
        )
        return repo.get_job(job['id'])

    def test_stale_callback_is_ignored(self):
        job = self._create_running_job()
        repo.update_job(job['id'], remote_last_callback_at='2025-01-01T00:00:00Z')
        result = repo.apply_remote_callback(
            job_id=job['id'],
            remote_job_id='remote-1',
            remote_status='running',
            message='progress',
            error_message='',
            artifact_download_url='',
            event_id='evt-1',
            occurred_at='2024-01-01T00:00:00Z',
        )
        self.assertFalse(result.get('applied'))
        self.assertEqual(result.get('reason'), 'stale_event')

    def test_terminal_job_rejects_remote_status_mutation(self):
        job = self._create_running_job()
        repo.update_job(job['id'], remote_status='succeeded')

        result = repo.apply_remote_callback(
            job_id=job['id'],
            remote_job_id='remote-1',
            remote_status='running',
            message='progress',
            error_message='',
            artifact_download_url='',
            event_id='evt-2',
            occurred_at='2035-01-01T00:00:00Z',
        )
        self.assertFalse(result.get('applied'))
        self.assertEqual(result.get('reason'), 'remote_terminal_immutable')

    def test_duplicate_event_id_is_idempotent(self):
        job = self._create_running_job()
        first = repo.apply_remote_callback(
            job_id=job['id'],
            remote_job_id='remote-1',
            remote_status='completed',
            message='done',
            error_message='',
            artifact_download_url='http://example.com/a.zip',
            event_id='evt-dup',
            occurred_at='2035-01-01T00:00:00Z',
        )
        self.assertTrue(first.get('applied', False))

        second = repo.apply_remote_callback(
            job_id=job['id'],
            remote_job_id='remote-1',
            remote_status='completed',
            message='done-again',
            error_message='',
            artifact_download_url='http://example.com/b.zip',
            event_id='evt-dup',
            occurred_at='2035-01-01T00:00:01Z',
        )
        self.assertFalse(second.get('applied'))
        self.assertEqual(second.get('reason'), 'duplicate_event')


if __name__ == '__main__':
    unittest.main()
