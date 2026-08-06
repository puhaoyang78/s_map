#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import shutil
import unittest
import uuid
from pathlib import Path

from repositories import user_repository as repo

TMP_ROOT = Path(__file__).resolve().parent / '.tmp'


def make_test_dir(prefix: str) -> Path:
    TMP_ROOT.mkdir(exist_ok=True)
    path = TMP_ROOT / f'{prefix}{uuid.uuid4().hex}'
    path.mkdir(parents=True, exist_ok=False)
    return path


class UserRepositorySecurityTests(unittest.TestCase):
    def setUp(self):
        self._old_user_dir = repo.USER_DIR
        self._old_db_path = repo.DB_PATH
        self._tmp_dir = make_test_dir('user_repo_test_')
        repo.USER_DIR = self._tmp_dir
        repo.DB_PATH = repo.USER_DIR / 'users.db'
        repo.init_db()

    def tearDown(self):
        repo.USER_DIR = self._old_user_dir
        repo.DB_PATH = self._old_db_path
        shutil.rmtree(self._tmp_dir, ignore_errors=True)

    def test_create_user_marks_force_password_change(self):
        user_id = repo.create_user(
            username='alice',
            password_hash='h',
            role='user',
            status='active',
            now_iso='2026-03-14T00:00:00',
        )
        row = repo.find_by_id(user_id)
        self.assertEqual(int(row['force_password_change']), 1)

    def test_password_reset_token_lifecycle(self):
        user_id = repo.create_user(
            username='bob',
            password_hash='h2',
            role='user',
            status='active',
            now_iso='2026-03-14T00:00:00',
        )
        token_hash = 'abc123'
        repo.set_password_reset_token(
            user_id=user_id,
            token_hash=token_hash,
            expires_at_iso='2026-12-31T00:00:00',
            now_iso='2026-03-14T00:00:00',
        )
        row = repo.find_by_valid_reset_token(token_hash, '2026-03-14T00:00:01')
        self.assertIsNotNone(row)
        self.assertEqual(int(row['id']), user_id)

        repo.clear_password_reset_token(user_id, '2026-03-14T00:00:02')
        row2 = repo.find_by_valid_reset_token(token_hash, '2026-03-14T00:00:03')
        self.assertIsNone(row2)


if __name__ == '__main__':
    unittest.main()
