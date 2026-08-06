#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import shutil
import unittest
import uuid
from pathlib import Path

from flask import Flask

from repositories import user_repository as repo
from routes import auth_route

TMP_ROOT = Path(__file__).resolve().parent / '.tmp'


def make_test_dir(prefix: str) -> Path:
    TMP_ROOT.mkdir(exist_ok=True)
    path = TMP_ROOT / f'{prefix}{uuid.uuid4().hex}'
    path.mkdir(parents=True, exist_ok=False)
    return path


class AuthAdminGuardrailTests(unittest.TestCase):
    def setUp(self):
        self._old_user_dir = repo.USER_DIR
        self._old_db_path = repo.DB_PATH
        self._tmp_dir = make_test_dir('auth_guardrails_test_')
        repo.USER_DIR = self._tmp_dir
        repo.DB_PATH = repo.USER_DIR / 'users.db'
        repo.init_db()

    def tearDown(self):
        repo.USER_DIR = self._old_user_dir
        repo.DB_PATH = self._old_db_path
        shutil.rmtree(self._tmp_dir, ignore_errors=True)

    def test_count_active_admin_users_ignores_disabled_admins(self):
        repo.create_user('active-admin', 'h1', 'admin', 'active', '2026-03-29T00:00:00', force_password_change=False)
        repo.create_user('disabled-admin', 'h2', 'admin', 'disabled', '2026-03-29T00:00:00', force_password_change=False)
        repo.create_user('active-user', 'h3', 'user', 'active', '2026-03-29T00:00:00', force_password_change=False)

        self.assertEqual(repo.count_active_admin_users(), 1)

    def test_client_ip_does_not_trust_forwarded_for_by_default(self):
        app = Flask(__name__)
        with app.test_request_context(
            '/api/auth/login',
            headers={'X-Forwarded-For': '1.1.1.1, 2.2.2.2'},
            environ_base={'REMOTE_ADDR': '9.9.9.9'},
        ):
            self.assertEqual(auth_route._client_ip(), '9.9.9.9')


if __name__ == '__main__':
    unittest.main()
