#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import shutil
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from utils.deployment_checks import build_backend_runtime_status, run_preflight_checks, summarize_reports
from detection_server_agent import AgentConfig, create_app


class DeploymentChecksTests(unittest.TestCase):
    def setUp(self):
        tmp_root = Path(__file__).resolve().parent / '.tmp'
        tmp_root.mkdir(parents=True, exist_ok=True)
        self.repo_root = tmp_root / 'deployment-checks'
        shutil.rmtree(self.repo_root, ignore_errors=True)
        self.repo_root.mkdir(parents=True, exist_ok=True)

        backend_root = self.repo_root / 'backend'
        front_root = self.repo_root / 'front'
        backend_root.mkdir(parents=True, exist_ok=True)
        front_root.mkdir(parents=True, exist_ok=True)
        (backend_root / 'config').mkdir(parents=True, exist_ok=True)
        (backend_root / 'data' / 'artifacts').mkdir(parents=True, exist_ok=True)
        (backend_root / 'data' / 'celery').mkdir(parents=True, exist_ok=True)
        (backend_root / 'logs').mkdir(parents=True, exist_ok=True)
        (backend_root / 'db_backups').mkdir(parents=True, exist_ok=True)
        (backend_root / 'control').mkdir(parents=True, exist_ok=True)

        self.local_artifact = backend_root / 'data' / 'artifacts' / 'local-artifact.7z'
        self.local_artifact.write_bytes(b'archive')
        self.database_path = backend_root / 'data' / 'app.db'
        self.database_path.write_bytes(b'db')
        (backend_root / 'config' / 'db_config.json').write_text(
            json.dumps({'database_path': 'data/app.db'}, ensure_ascii=False, indent=2),
            encoding='utf-8',
        )

        (backend_root / '.env').write_text(
            '\n'.join([
                'AUTH_SECRET=replace-with-a-long-random-secret',
                'DEFAULT_ADMIN_PASSWORD=replace-with-a-strong-admin-password',
                'DETECTION_ARTIFACT_PASSWORD=replace-with-artifact-password',
                'DETECTION_LOCAL_ARTIFACT_PATH=',
                'DETECTION_WEBHOOK_BASE_URL=',
                'DETECTION_WEBHOOK_TOKEN=replace-with-strong-webhook-token',
                'DETECTION_WEBHOOK_REQUIRE_SIGNATURE=true',
                'CELERY_FS_QUEUE_ROOT=./data/celery',
            ]),
            encoding='utf-8',
        )
        (backend_root / '.env.local').write_text(
            '\n'.join([
                'AUTH_SECRET=' + ('A' * 48),
                'DEFAULT_ADMIN_PASSWORD=StrongPass!2026',
                'DETECTION_ARTIFACT_PASSWORD=StrongArtifactPass!2026',
                'AUTH_COOKIE_SECURE=true',
                f'DETECTION_LOCAL_ARTIFACT_PATH={self.local_artifact}',
                'DETECTION_WEBHOOK_BASE_URL=https://backend.example.com',
                'DETECTION_WEBHOOK_TOKEN=' + ('B' * 40),
                'CELERY_FS_QUEUE_ROOT=./data/celery',
            ]),
            encoding='utf-8',
        )

        (front_root / '.env.example').write_text(
            'VITE_API_BASE_URL=http://127.0.0.1:5000\nVITE_MAPBOX_TOKEN=pk.replace-with-your-public-mapbox-token\n',
            encoding='utf-8',
        )
        (front_root / '.env.local').write_text(
            'VITE_API_BASE_URL=https://backend.example.com\nVITE_MAPBOX_TOKEN=pk.abcdefghijklmnopqrstuvwxyz123456\n',
            encoding='utf-8',
        )

        (self.repo_root / 'detection_server_agent.env.example').write_text(
            '\n'.join([
                'AGENT_TOKEN=replace-with-a-long-random-agent-token',
                'PROBE_SCRIPT_PATH=/opt/probe.py',
                'ENCRYPTED_ARTIFACT_DIR=/var/lib/agent-artifacts',
                'PROBE_PYTHON_BIN=python3',
                'AGENT_CALLBACK_ALLOWED_HOSTS=backend.example.com',
                'AGENT_CALLBACK_ALLOWED_PORTS=443',
                'AGENT_LOG_FILE=/var/log/detection-agent/agent.log',
            ]),
            encoding='utf-8',
        )

        probe_script = self.repo_root / 'probe.py'
        probe_script.write_text("print('ok')\n", encoding='utf-8')
        agent_artifact_dir = self.repo_root / 'agent-artifacts'
        agent_artifact_dir.mkdir(parents=True, exist_ok=True)
        agent_log_dir = self.repo_root / 'agent-logs'
        agent_log_dir.mkdir(parents=True, exist_ok=True)
        self.agent_env_file = self.repo_root / 'agent.env'
        self.agent_env_file.write_text(
            '\n'.join([
                'AGENT_TOKEN=' + ('C' * 48),
                f'PROBE_SCRIPT_PATH={probe_script}',
                f'ENCRYPTED_ARTIFACT_DIR={agent_artifact_dir}',
                f'PROBE_PYTHON_BIN={sys.executable}',
                'AGENT_CALLBACK_ALLOWED_HOSTS=backend.example.com',
                'AGENT_CALLBACK_ALLOWED_PORTS=443',
                f'AGENT_LOG_FILE={agent_log_dir / "agent.log"}',
            ]),
            encoding='utf-8',
        )

    def tearDown(self):
        shutil.rmtree(self.repo_root, ignore_errors=True)

    def test_run_preflight_checks_passes_with_valid_layout(self):
        reports = run_preflight_checks(
            repo_root=self.repo_root,
            agent_env_file=self.agent_env_file,
            process_env={},
        )

        summary = summarize_reports(reports)
        self.assertEqual(summary['errors'], 0)
        self.assertEqual(summary['warnings'], 0)

        backend_status = build_backend_runtime_status(
            backend_root=self.repo_root / 'backend',
            process_env={},
        )
        self.assertEqual(backend_status['status'], 'ok')
        self.assertEqual(backend_status['mode'], 'LOCAL_MODE')

    def test_run_preflight_checks_reports_missing_agent_env_file(self):
        missing_agent_env = self.repo_root / 'missing-agent.env'
        reports = run_preflight_checks(
            repo_root=self.repo_root,
            agent_env_file=missing_agent_env,
            process_env={},
        )

        agent_report = next(report for report in reports if report.name == 'agent')
        self.assertTrue(any('missing-agent.env' in item.message for item in agent_report.errors))

    def test_run_preflight_checks_reads_frontend_env_production(self):
        front_root = self.repo_root / 'front'
        (front_root / '.env.local').write_text(
            'VITE_MAPBOX_TOKEN=pk.abcdefghijklmnopqrstuvwxyz123456\n',
            encoding='utf-8',
        )
        (front_root / '.env.production').write_text(
            'VITE_API_BASE_URL=http://192.0.2.10:5000\n',
            encoding='utf-8',
        )

        reports = run_preflight_checks(
            repo_root=self.repo_root,
            agent_env_file=self.agent_env_file,
            process_env={},
        )

        summary = summarize_reports(reports)
        self.assertEqual(summary['errors'], 0)

        frontend_report = next(report for report in reports if report.name == 'frontend')
        self.assertTrue(any('frontend production config loaded' in item.message for item in frontend_report.oks))

    def test_agent_health_endpoint_exposes_runtime_summary(self):
        probe_script = self.repo_root / 'probe.py'
        agent_artifact_dir = self.repo_root / 'agent-artifacts'
        agent_log_file = self.repo_root / 'agent-logs' / 'agent.log'
        cfg = AgentConfig(
            agent_token='D' * 48,
            probe_script_path=str(probe_script),
            encrypted_artifact_dir=str(agent_artifact_dir),
            probe_python_bin=sys.executable,
            callback_allowed_hosts=('backend.example.com',),
            callback_allowed_ports=(443,),
            log_file=str(agent_log_file),
        )

        with patch('detection_server_agent.DB_PATH', self.repo_root / 'agent-jobs.db'):
            app = create_app(cfg)

        client = app.test_client()
        response = client.get('/api/v1/health', headers={'Authorization': 'Bearer ' + 'D' * 48})
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload['status'], 'ok')
        self.assertIn('paths', payload)
        self.assertTrue(payload['paths']['artifactDir']['writable'])


if __name__ == '__main__':
    unittest.main()
