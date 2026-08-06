#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import shutil
import unittest
import uuid
from pathlib import Path

from repositories import detection_job_repository as job_repo
from repositories import runtime_state_repository as state_repo
from services import detection_orchestrator_service as orchestrator

TMP_ROOT = Path(__file__).resolve().parent / '.tmp'


def make_test_dir(prefix: str) -> Path:
    TMP_ROOT.mkdir(exist_ok=True)
    path = TMP_ROOT / f'{prefix}{uuid.uuid4().hex}'
    path.mkdir(parents=True, exist_ok=False)
    return path


class DetectionOrchestratorLockReleaseTests(unittest.TestCase):
    def setUp(self):
        self._old_state_data_dir = state_repo.DATA_DIR
        self._old_state_db_path = state_repo.DB_PATH
        self._old_job_data_dir = job_repo.DATA_DIR
        self._old_job_db_path = job_repo.DB_PATH
        self._tmp_dir = make_test_dir('detection_orchestrator_test_')

        state_repo.DATA_DIR = self._tmp_dir
        state_repo.DB_PATH = self._tmp_dir / 'runtime_state.db'
        job_repo.DATA_DIR = self._tmp_dir
        job_repo.DB_PATH = self._tmp_dir / 'detection_jobs.db'

        state_repo.init_db()
        job_repo.init_db()

    def tearDown(self):
        state_repo.DATA_DIR = self._old_state_data_dir
        state_repo.DB_PATH = self._old_state_db_path
        job_repo.DATA_DIR = self._old_job_data_dir
        job_repo.DB_PATH = self._old_job_db_path
        shutil.rmtree(self._tmp_dir, ignore_errors=True)

    def test_terminal_job_does_not_leave_runtime_lock_behind(self):
        job = job_repo.create_job('global', 1, 'tester')
        job_repo.update_job(job['id'], status='activated', progress=100, step='activated')

        orchestrator.run_detection_job(job['id'])

        lock_key = f'detection_job_lock:{job["id"]}'
        acquired, _ = state_repo.acquire_lock(lock_key, 'assert-owner', 60)
        self.assertTrue(acquired)


if __name__ == '__main__':
    unittest.main()
