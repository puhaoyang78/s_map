#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import io
import json
import shutil
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from utils.release_helpers import build_post_deploy_runtime_summary, create_runtime_backup, probe_health_endpoint


class _FakeResponse:
    def __init__(self, status: int, payload: dict):
        self.status = status
        self._payload = json.dumps(payload).encode('utf-8')

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False


class ReleaseHelpersTests(unittest.TestCase):
    def setUp(self):
        tmp_root = Path(__file__).resolve().parent / '.tmp'
        tmp_root.mkdir(parents=True, exist_ok=True)
        self.repo_root = tmp_root / 'release-helpers'
        shutil.rmtree(self.repo_root, ignore_errors=True)
        self.repo_root.mkdir(parents=True, exist_ok=True)

        backend_root = self.repo_root / 'backend'
        front_root = self.repo_root / 'front'
        backend_root.mkdir(parents=True, exist_ok=True)
        front_root.mkdir(parents=True, exist_ok=True)
        (front_root / 'dist').mkdir(parents=True, exist_ok=True)
        (front_root / 'dist' / 'index.html').write_text('<html></html>', encoding='utf-8')
        (backend_root / 'config').mkdir(parents=True, exist_ok=True)
        (backend_root / 'data' / 'artifacts').mkdir(parents=True, exist_ok=True)
        (backend_root / 'data' / 'celery').mkdir(parents=True, exist_ok=True)
        (backend_root / 'logs').mkdir(parents=True, exist_ok=True)
        (backend_root / 'db_backups').mkdir(parents=True, exist_ok=True)
        (backend_root / 'control').mkdir(parents=True, exist_ok=True)

        self.database_path = backend_root / 'data' / 'runtime.db'
        self.database_path.write_bytes(b'db')
        (backend_root / 'config' / 'db_config.json').write_text(
            json.dumps({'database_path': 'data/runtime.db'}, ensure_ascii=False, indent=2),
            encoding='utf-8',
        )
        (backend_root / '.env').write_text(
            'AUTH_SECRET=replace-with-a-long-random-secret\n'
            'DETECTION_ARTIFACT_PASSWORD=replace-with-artifact-password\n'
            'DETECTION_AGENT_TOKEN=replace-with-a-long-random-agent-token\n'
            'DETECTION_WEBHOOK_TOKEN=replace-with-strong-webhook-token\n',
            encoding='utf-8',
        )
        (backend_root / '.env.local').write_text(
            'AUTH_SECRET=' + ('A' * 48) + '\n'
            'DETECTION_ARTIFACT_PASSWORD=StrongArtifactPass!2026\n'
            'DETECTION_LOCAL_ARTIFACT_PATH=' + str(backend_root / 'data' / 'artifacts' / 'demo.7z') + '\n'
            'DETECTION_WEBHOOK_TOKEN=' + ('B' * 40) + '\n'
            'AUTH_COOKIE_SECURE=true\n',
            encoding='utf-8',
        )
        (backend_root / 'data' / 'artifacts' / 'demo.7z').write_bytes(b'artifact')

        (front_root / '.env.example').write_text(
            'VITE_API_BASE_URL=http://127.0.0.1:5000\nVITE_MAPBOX_TOKEN=pk.replace-with-token\n',
            encoding='utf-8',
        )
        (front_root / '.env.local').write_text(
            'VITE_API_BASE_URL=https://backend.example.com\nVITE_MAPBOX_TOKEN=pk.abcdefghijklmnopqrstuvwxyz123456\n',
            encoding='utf-8',
        )

        (self.repo_root / 'detection_server_agent.env.example').write_text(
            'AGENT_TOKEN=replace-with-a-long-random-agent-token\n'
            'PROBE_SCRIPT_PATH=/opt/probe.py\n'
            'ENCRYPTED_ARTIFACT_DIR=/var/lib/agent-artifacts\n'
            'PROBE_PYTHON_BIN=python3\n'
            'AGENT_CALLBACK_ALLOWED_HOSTS=backend.example.com\n'
            'AGENT_LOG_FILE=/var/log/detection-agent/agent.log\n',
            encoding='utf-8',
        )
        self.agent_env_file = self.repo_root / 'agent.env'
        probe_script = self.repo_root / 'probe.py'
        probe_script.write_text("print('ok')\n", encoding='utf-8')
        agent_artifacts = self.repo_root / 'agent-artifacts'
        agent_artifacts.mkdir(parents=True, exist_ok=True)
        agent_logs = self.repo_root / 'agent-logs'
        agent_logs.mkdir(parents=True, exist_ok=True)
        self.agent_env_file.write_text(
            'AGENT_TOKEN=' + ('C' * 48) + '\n'
            f'PROBE_SCRIPT_PATH={probe_script}\n'
            f'ENCRYPTED_ARTIFACT_DIR={agent_artifacts}\n'
            f'PROBE_PYTHON_BIN={sys.executable}\n'
            'AGENT_CALLBACK_ALLOWED_HOSTS=backend.example.com\n'
            'AGENT_CALLBACK_ALLOWED_PORTS=443\n'
            f'AGENT_LOG_FILE={agent_logs / "agent.log"}\n',
            encoding='utf-8',
        )

    def tearDown(self):
        shutil.rmtree(self.repo_root, ignore_errors=True)

    def test_create_runtime_backup_copies_database_and_env_files(self):
        result = create_runtime_backup(
            repo_root=self.repo_root,
            agent_env_file=self.agent_env_file,
            include_env=True,
        )

        backup_dir = Path(result['backupDir'])
        manifest_path = Path(result['manifestPath'])
        self.assertTrue((backup_dir / 'database' / 'runtime.db').exists())
        self.assertTrue((backup_dir / 'env' / 'backend-.env.local').exists())
        self.assertTrue((backup_dir / 'env' / 'front-.env.local').exists())
        self.assertTrue((backup_dir / 'env' / 'agent-agent.env').exists())
        self.assertTrue(manifest_path.exists())

        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        self.assertEqual(Path(manifest['databasePath']).name, 'runtime.db')
        self.assertTrue(manifest['includeEnv'])
        self.assertGreaterEqual(len(manifest['copiedFiles']), 3)

    def test_build_post_deploy_runtime_summary_reports_latest_backup(self):
        result = create_runtime_backup(
            repo_root=self.repo_root,
            agent_env_file=self.agent_env_file,
            include_env=False,
        )

        summary = build_post_deploy_runtime_summary(
            repo_root=self.repo_root,
            agent_env_file=self.agent_env_file,
        )

        self.assertEqual(summary['latestBackupDir'], result['backupDir'])
        self.assertTrue(summary['runtimeDirectories']['logs']['exists'])
        self.assertTrue(summary['distState']['parent_exists'])

    def test_probe_health_endpoint_handles_backend_success_wrapper(self):
        payload = {
            'success': True,
            'message': '服务健康',
            'data': {
                'status': 'warning',
                'service': 'my-map-app-backend',
                'warnings': ['demo warning'],
                'errors': [],
            },
        }
        with patch('utils.release_helpers.request.urlopen', return_value=_FakeResponse(200, payload)):
            result = probe_health_endpoint('https://backend.example.com/api/health')

        self.assertTrue(result.ok)
        self.assertEqual(result.status, 'warning')
        self.assertEqual(result.service, 'my-map-app-backend')
        self.assertEqual(result.warnings, ['demo warning'])

    def test_probe_health_endpoint_handles_http_error_payload(self):
        payload = {'status': 'error', 'service': 'detection-agent', 'errors': ['signature mismatch']}
        error_fp = io.BytesIO(json.dumps(payload).encode('utf-8'))
        http_error = HTTPError(
            url='https://agent.example.com/api/v1/health',
            code=503,
            msg='Service Unavailable',
            hdrs=None,
            fp=error_fp,
        )

        with patch('utils.release_helpers.request.urlopen', side_effect=http_error):
            result = probe_health_endpoint('https://agent.example.com/api/v1/health')

        self.assertFalse(result.ok)
        self.assertEqual(result.status, 'error')
        self.assertIn('signature mismatch', result.errors)


if __name__ == '__main__':
    unittest.main()
