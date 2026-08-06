#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import shutil
import sys
import unittest
from pathlib import Path

from utils.startup_validation import validate_backend_startup_config

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from detection_server_agent import AgentConfig, _validate_agent_config  # noqa: E402


class BackendStartupValidationTests(unittest.TestCase):
    def setUp(self):
        self._env_backup = dict(os.environ)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env_backup)

    def test_backend_validation_rejects_placeholder_auth_secret(self):
        os.environ['AUTH_SECRET'] = 'replace-with-a-long-random-secret'
        os.environ['DETECTION_ARTIFACT_PASSWORD'] = 'replace-with-artifact-password'
        os.environ['DETECTION_LOCAL_ARTIFACT_PATH'] = 'dummy'

        errors, warnings = validate_backend_startup_config()

        self.assertTrue(any('AUTH_SECRET' in item for item in errors))
        self.assertTrue(any('DETECTION_ARTIFACT_PASSWORD' in item for item in errors))
        self.assertTrue(any('DEFAULT_ADMIN_PASSWORD' in item for item in warnings))

    def test_backend_validation_rejects_missing_webhook_token_when_callback_enabled(self):
        os.environ['AUTH_SECRET'] = 'A' * 48
        os.environ['DETECTION_ARTIFACT_PASSWORD'] = 'StrongArtifactPass!2026'
        os.environ['DETECTION_LOCAL_ARTIFACT_PATH'] = 'dummy'
        os.environ['DETECTION_WEBHOOK_BASE_URL'] = 'https://backend.example.com'
        os.environ['DETECTION_WEBHOOK_TOKEN'] = 'replace-with-strong-webhook-token'

        errors, _warnings = validate_backend_startup_config()

        self.assertTrue(any('DETECTION_WEBHOOK_TOKEN' in item for item in errors))

    def test_backend_validation_allows_local_artifact_mode_with_real_secret(self):
        tmp_root = Path(__file__).resolve().parent / '.tmp'
        tmp_root.mkdir(parents=True, exist_ok=True)
        tmp_dir = tmp_root / 'startup-validation-artifact'
        shutil.rmtree(tmp_dir, ignore_errors=True)
        tmp_dir.mkdir(parents=True, exist_ok=True)
        try:
            artifact_path = tmp_dir / 'artifact.7z'
            artifact_path.write_bytes(b'test')
            os.environ['AUTH_SECRET'] = 'A' * 48
            os.environ['DEFAULT_ADMIN_PASSWORD'] = 'StrongPass!2026'
            os.environ['DETECTION_ARTIFACT_PASSWORD'] = 'StrongArtifactPass!2026'
            os.environ['DETECTION_LOCAL_ARTIFACT_PATH'] = str(artifact_path)
            os.environ.pop('DETECTION_WEBHOOK_BASE_URL', None)
            os.environ.pop('DETECTION_WEBHOOK_TOKEN', None)

            errors, _warnings = validate_backend_startup_config()

            self.assertEqual(errors, [])
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


class AgentStartupValidationTests(unittest.TestCase):
    def test_agent_validation_rejects_placeholder_token_and_partial_tls(self):
        cfg = AgentConfig(
          agent_token='replace-with-a-long-random-agent-token',
          tls_cert_file='/tmp/cert.pem',
          tls_key_file='',
          callback_allowed_hosts=('backend.example.com',),
        )

        errors, _warnings = _validate_agent_config(cfg)

        self.assertTrue(any('AGENT_TOKEN' in item for item in errors))
        self.assertTrue(any('AGENT_TLS_CERT_FILE and AGENT_TLS_KEY_FILE' in item for item in errors))

    def test_agent_validation_warns_when_callback_allowlist_is_missing(self):
        tmp_root = Path(__file__).resolve().parent / '.tmp'
        tmp_root.mkdir(parents=True, exist_ok=True)
        tmp_dir = tmp_root / 'agent-validation'
        shutil.rmtree(tmp_dir, ignore_errors=True)
        tmp_dir.mkdir(parents=True, exist_ok=True)
        probe_script = tmp_dir / 'probe.py'
        probe_script.write_text("print('ok')\n", encoding='utf-8')
        artifact_dir = tmp_dir / 'artifacts'
        artifact_dir.mkdir(parents=True, exist_ok=True)
        cfg = AgentConfig(
            agent_token='A' * 48,
            probe_script_path=str(probe_script),
            encrypted_artifact_dir=str(artifact_dir),
            probe_python_bin=sys.executable,
            callback_allowed_hosts=(),
        )

        try:
            errors, warnings = _validate_agent_config(cfg)

            self.assertEqual(errors, [])
            self.assertTrue(any('AGENT_CALLBACK_ALLOWED_HOSTS' in item for item in warnings))
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == '__main__':
    unittest.main()
