#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""回归测试：全局异常处理透传未单独注册的 HTTPException 状态码（修复项 13）。"""

import os
import shutil
import sys
import types
import unittest
import uuid
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

if 'tasks.celery_app' not in sys.modules:
    fake_celery_app = types.ModuleType('tasks.celery_app')
    fake_celery_app.enqueue_detection_job = lambda *args, **kwargs: 'fake-task-id'
    fake_celery_app.init_celery = lambda: None
    sys.modules['tasks.celery_app'] = fake_celery_app

from repositories import runtime_state_repository as runtime_state_repo
from repositories import user_repository

TMP_ROOT = Path(__file__).resolve().parent / '.tmp'

# import app 会执行 create_app()（启动校验 + 用户库初始化）。
# 先备份环境与仓库路径，导入完成后立刻恢复，避免影响同进程的其他测试。
_env_backup = dict(os.environ)
os.environ['AUTH_SECRET'] = 'A' * 48
os.environ['DEFAULT_ADMIN_PASSWORD'] = 'StrongPass!2026'
os.environ['DETECTION_ARTIFACT_PASSWORD'] = 'artifact-secret-123'
os.environ['DETECTION_LOCAL_ARTIFACT_PATH'] = 'dummy'
for _key in ('DETECTION_WEBHOOK_BASE_URL', 'DETECTION_AGENT_BASE_URL', 'DETECTION_AGENT_TOKEN'):
    os.environ.pop(_key, None)

_TMP_DIR = TMP_ROOT / f'app_import_{uuid.uuid4().hex}'
_TMP_DIR.mkdir(parents=True, exist_ok=True)
_old_user_dir = user_repository.USER_DIR
_old_user_db = user_repository.DB_PATH
_old_state_dir = runtime_state_repo.DATA_DIR
_old_state_db = runtime_state_repo.DB_PATH
user_repository.USER_DIR = _TMP_DIR
user_repository.DB_PATH = _TMP_DIR / 'users.db'
runtime_state_repo.DATA_DIR = _TMP_DIR
runtime_state_repo.DB_PATH = _TMP_DIR / 'runtime_state.db'

try:
    import app as app_module  # noqa: E402
finally:
    user_repository.USER_DIR = _old_user_dir
    user_repository.DB_PATH = _old_user_db
    runtime_state_repo.DATA_DIR = _old_state_dir
    runtime_state_repo.DB_PATH = _old_state_db
    os.environ.clear()
    os.environ.update(_env_backup)
    shutil.rmtree(_TMP_DIR, ignore_errors=True)


class HttpExceptionPassthroughTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from werkzeug.exceptions import RequestEntityTooLarge

        flask_app = app_module.app

        @flask_app.route('/api/test-passthrough-413', methods=['POST'])
        def _raise_413():
            raise RequestEntityTooLarge()

        @flask_app.route('/api/test-passthrough-500', methods=['POST'])
        def _raise_500():
            raise RuntimeError('boom')

        cls.client = flask_app.test_client()

    def test_unregistered_http_exception_keeps_its_status_code(self):
        resp = self.client.post('/api/test-passthrough-413')

        self.assertEqual(resp.status_code, 413)
        self.assertFalse(resp.get_json()['success'])

    def test_plain_exception_still_maps_to_500(self):
        resp = self.client.post('/api/test-passthrough-500')

        self.assertEqual(resp.status_code, 500)
        self.assertEqual(resp.get_json()['message'], '服务器内部错误')


if __name__ == '__main__':
    unittest.main()
