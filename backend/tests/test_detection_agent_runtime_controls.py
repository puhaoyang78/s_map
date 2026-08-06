#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Regression tests for agent runtime controls:

- AGENT_MAX_CONCURRENT_JOBS concurrency gate (409 when full, slot released).
- Explicit ARTIFACT_PATH must stay inside ENCRYPTED_ARTIFACT_DIR.
- /api/v1/health hides runtime details unless the agent token is presented.
"""

import shutil
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import detection_server_agent as agent_module  # noqa: E402
from detection_server_agent import (  # noqa: E402
    AgentConfig,
    _resolve_current_job_artifact,
)


class _AgentAppMixin:
    """Spin up the agent Flask app against a throwaway sqlite DB."""

    def _make_client(self, **cfg_overrides):
        tmp = tempfile.mkdtemp(prefix='agent-runtime-test-')
        self.addCleanup(shutil.rmtree, tmp, True)
        root = Path(tmp)
        probe = root / 'probe.py'
        probe.write_text("print('ok')\n", encoding='utf-8')
        artifact_dir = root / 'artifacts'
        artifact_dir.mkdir()
        log_dir = root / 'logs'
        log_dir.mkdir()

        cfg_kwargs = dict(
            agent_token='T' * 48,
            probe_script_path=str(probe),
            encrypted_artifact_dir=str(artifact_dir),
            probe_python_bin=sys.executable,
            callback_allowed_hosts=('backend.example.com',),
            callback_allowed_ports=(443,),
            log_file=str(log_dir / 'agent.log'),
        )
        cfg_kwargs.update(cfg_overrides)
        cfg = AgentConfig(**cfg_kwargs)

        db_patcher = patch('detection_server_agent.DB_PATH', root / 'agent-jobs.db')
        db_patcher.start()
        self.addCleanup(db_patcher.stop)
        app = agent_module.create_app(cfg)
        return app.test_client(), cfg

    def _wait_for_free_slot(self, message):
        deadline = time.time() + 5
        while True:
            if agent_module._try_acquire_job_slot():
                agent_module._release_job_slot()
                return
            self.assertLess(time.time(), deadline, message)
            time.sleep(0.05)


class AgentConcurrencyGateTests(_AgentAppMixin, unittest.TestCase):
    def test_max_concurrent_jobs_returns_409_and_slot_is_released(self):
        client, cfg = self._make_client(max_concurrent_jobs=1)
        auth = {'Authorization': 'Bearer ' + cfg.agent_token}
        started = threading.Event()
        release = threading.Event()

        def fake_run_job(job_id, _cfg):
            started.set()
            release.wait(timeout=10)

        with patch('detection_server_agent._run_job', side_effect=fake_run_job):
            try:
                first = client.post('/api/v1/jobs', json={}, headers=auth)
                self.assertEqual(first.status_code, 200)
                self.assertTrue(started.wait(timeout=5))

                second = client.post('/api/v1/jobs', json={}, headers=auth)
                self.assertEqual(second.status_code, 409)
                self.assertIn('error', second.get_json())
            finally:
                release.set()

            self._wait_for_free_slot('job slot was not released after job finished')

            third = client.post('/api/v1/jobs', json={}, headers=auth)
            self.assertEqual(third.status_code, 200)
            self._wait_for_free_slot('job slot was not released after third job')


class AgentHealthRedactionTests(_AgentAppMixin, unittest.TestCase):
    def test_health_hides_runtime_details_without_token(self):
        client, cfg = self._make_client()

        anonymous = client.get('/api/v1/health')
        self.assertEqual(anonymous.status_code, 200)
        payload = anonymous.get_json()
        self.assertEqual(payload['status'], 'ok')
        self.assertNotIn('paths', payload)
        self.assertNotIn('config', payload)

        authed = client.get('/api/v1/health', headers={'Authorization': 'Bearer ' + cfg.agent_token})
        self.assertEqual(authed.status_code, 200)
        self.assertIn('paths', authed.get_json())


class ExplicitArtifactContainmentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='agent-artifact-test-')
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.artifact_dir = Path(self.tmp) / 'artifacts'
        self.artifact_dir.mkdir()
        self.cfg = AgentConfig(encrypted_artifact_dir=str(self.artifact_dir))
        self.job_started_ts = time.time() - 60

    def _resolve(self, path):
        return _resolve_current_job_artifact(
            cfg=self.cfg,
            before_snapshot={},
            job_started_ts=self.job_started_ts,
            stdout=f'ARTIFACT_PATH={path}\n',
        )

    def test_explicit_path_inside_artifact_dir_is_accepted(self):
        inside = self.artifact_dir / 'job_enc.7z'
        inside.write_bytes(b'payload')
        self.assertEqual(self._resolve(inside), inside.resolve())

    def test_explicit_path_outside_artifact_dir_is_rejected(self):
        outside = Path(self.tmp) / 'evil_enc.7z'
        outside.write_bytes(b'payload')
        with self.assertRaises(RuntimeError):
            self._resolve(outside)

    def test_explicit_path_in_sibling_prefix_dir_is_rejected(self):
        # startswith-based checks would wrongly accept this; commonpath must not.
        sibling = Path(self.tmp) / 'artifacts_evil'
        sibling.mkdir()
        candidate = sibling / 'job_enc.7z'
        candidate.write_bytes(b'payload')
        with self.assertRaises(RuntimeError):
            self._resolve(candidate)


if __name__ == '__main__':
    unittest.main()
