#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""回归测试：创建检测任务的“活跃检查 + 插入”在同一写事务内完成（修复项 2）。"""

import shutil
import threading
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


class CreateJobIfIdleTests(unittest.TestCase):
    def setUp(self):
        self._old_data_dir = repo.DATA_DIR
        self._old_db_path = repo.DB_PATH
        self._tmp_dir = make_test_dir('create_job_atomic_test_')
        repo.DATA_DIR = self._tmp_dir
        repo.DB_PATH = self._tmp_dir / 'detection_jobs.db'
        repo.init_db()

    def tearDown(self):
        repo.DATA_DIR = self._old_data_dir
        repo.DB_PATH = self._old_db_path
        shutil.rmtree(self._tmp_dir, ignore_errors=True)

    def test_second_create_is_rejected_while_job_active(self):
        job, active = repo.create_job_if_idle('global', 1, 'tester')
        self.assertIsNotNone(job)
        self.assertEqual(active, 0)

        job2, active2 = repo.create_job_if_idle('global', 1, 'tester')
        self.assertIsNone(job2)
        self.assertEqual(active2, 1)

        self.assertEqual(len(repo.list_jobs(limit=10)), 1)

    def test_create_allowed_after_job_finished(self):
        job, _ = repo.create_job_if_idle('global', 1, 'tester')
        repo.update_job(job['id'], status='failed', progress=100)

        job2, active2 = repo.create_job_if_idle('global', 1, 'tester')
        self.assertIsNotNone(job2)
        self.assertEqual(active2, 0)

    def test_concurrent_create_allows_exactly_one_job(self):
        barrier = threading.Barrier(6)
        results = []
        results_lock = threading.Lock()

        def worker():
            barrier.wait()
            job, _active = repo.create_job_if_idle('global', 1, 'tester')
            with results_lock:
                results.append(job is not None)

        threads = [threading.Thread(target=worker) for _ in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(sum(1 for ok in results if ok), 1)
        self.assertEqual(len(repo.list_jobs(limit=10)), 1)


if __name__ == '__main__':
    unittest.main()
