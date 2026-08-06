#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import shutil
import unittest
import uuid
from pathlib import Path

from repositories import runtime_state_repository as repo

TMP_ROOT = Path(__file__).resolve().parent / '.tmp'


def make_test_dir(prefix: str) -> Path:
    TMP_ROOT.mkdir(exist_ok=True)
    path = TMP_ROOT / f'{prefix}{uuid.uuid4().hex}'
    path.mkdir(parents=True, exist_ok=False)
    return path


class RuntimeStateRepositoryTests(unittest.TestCase):
    def setUp(self):
        self._old_data_dir = repo.DATA_DIR
        self._old_db_path = repo.DB_PATH
        self._tmp_dir = make_test_dir('runtime_state_test_')
        repo.DATA_DIR = self._tmp_dir
        repo.DB_PATH = self._tmp_dir / 'app_meta.db'
        repo.init_db()

    def tearDown(self):
        repo.DATA_DIR = self._old_data_dir
        repo.DB_PATH = self._old_db_path
        shutil.rmtree(self._tmp_dir, ignore_errors=True)

    def test_distributed_lock_acquire_and_release(self):
        ok1, _ = repo.acquire_lock('k1', 'owner-a', 5)
        self.assertTrue(ok1)

        ok2, retry = repo.acquire_lock('k1', 'owner-b', 5)
        self.assertFalse(ok2)
        self.assertGreaterEqual(retry, 1)

        repo.release_lock('k1', 'owner-a')
        ok3, _ = repo.acquire_lock('k1', 'owner-c', 5)
        self.assertTrue(ok3)

    def test_login_rate_limit(self):
        key = 'ip::user'
        allowed, _ = repo.check_login_allowed(key, 300)
        self.assertTrue(allowed)

        locked, _ = repo.record_login_failure(key, 300, 2, 60)
        self.assertFalse(locked)
        locked2, retry = repo.record_login_failure(key, 300, 2, 60)
        self.assertTrue(locked2)
        self.assertGreaterEqual(retry, 1)

        allowed2, retry2 = repo.check_login_allowed(key, 300)
        self.assertFalse(allowed2)
        self.assertGreaterEqual(retry2, 1)

        repo.clear_login_failures(key)
        allowed3, _ = repo.check_login_allowed(key, 300)
        self.assertTrue(allowed3)


if __name__ == '__main__':
    unittest.main()
