#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
import unittest
import types
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import urlparse

from flask import Flask
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

if 'tasks.celery_app' not in sys.modules:
    fake_celery_app = types.ModuleType('tasks.celery_app')
    fake_celery_app.enqueue_detection_job = lambda *args, **kwargs: 'fake-task-id'
    fake_celery_app.init_celery = lambda: None
    sys.modules['tasks.celery_app'] = fake_celery_app

from routes import detection_jobs_route as callback_route
from services.probe_runner_service import build_detection_callback
from utils.webhook_signing import build_webhook_signature

from detection_server_agent import (  # noqa: E402
    AgentConfig,
    _normalize_callback_url,
    _notify_callback,
)


class DetectionWebhookIntegrationTests(unittest.TestCase):
    def setUp(self):
        self._env_backup = dict(os.environ)
        os.environ['AUTH_SECRET'] = 'A' * 48
        os.environ['DEFAULT_ADMIN_PASSWORD'] = 'StrongPass!2026'
        os.environ['DETECTION_LOCAL_ARTIFACT_PATH'] = 'dummy'
        os.environ['DETECTION_WEBHOOK_BASE_URL'] = 'https://backend.example.com'
        os.environ['DETECTION_WEBHOOK_TOKEN'] = 'webhook-shared-secret'
        os.environ['DETECTION_WEBHOOK_REQUIRE_SIGNATURE'] = 'true'
        os.environ['DETECTION_WEBHOOK_SIGNATURE_TTL_SECONDS'] = '300'
        os.environ['DETECTION_AGENT_BASE_URL'] = 'https://agent.example.com:18080'
        self.app = Flask(__name__)
        self.app.register_blueprint(callback_route.detection_jobs_bp)
        self.client = self.app.test_client()
        self.agent_cfg = AgentConfig(
            agent_token='A' * 48,
            callback_retries=0,
            callback_allowed_hosts=('backend.example.com',),
            callback_allowed_ports=(443,),
        )

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env_backup)

    def _build_callback_url(self, job_id: str) -> str:
        callback = build_detection_callback(job_id)
        with patch('detection_server_agent.socket.getaddrinfo', return_value=[(0, 0, 0, '', ('8.8.8.8', 443))]):
            return _normalize_callback_url(callback['url'], self.agent_cfg)

    def _backend_job(self, status='running'):
        return {'id': 'job-1', 'status': status}

    def _run_agent_notify(self, *, job_id='job-1', callback_token='webhook-shared-secret', mutate_forward=None):
        callback_url = self._build_callback_url(job_id)

        def fake_post(url, data=None, headers=None, timeout=None, allow_redirects=None):
            forwarded_headers = dict(headers or {})
            forwarded_data = data
            if mutate_forward:
                forwarded_data, forwarded_headers = mutate_forward(forwarded_data, forwarded_headers)
            response = self.client.post(
                urlparse(url).path,
                data=forwarded_data,
                headers=forwarded_headers,
                content_type='application/json',
            )
            return SimpleNamespace(status_code=response.status_code, text=response.get_data(as_text=True))

        with patch('detection_server_agent._get_job', return_value={
            'callback_url': callback_url,
            'callback_token': callback_token,
        }), patch('detection_server_agent.requests.post', side_effect=fake_post):
            _notify_callback(
                self.agent_cfg,
                job_id=job_id,
                status='running',
                message='probe running',
            )

    def test_generated_callback_url_is_rejected_when_host_not_whitelisted(self):
        callback = build_detection_callback('job-1')
        strict_cfg = AgentConfig(
            agent_token='A' * 48,
            callback_allowed_hosts=('other.example.com',),
            callback_allowed_ports=(443,),
        )

        with self.assertRaises(ValueError):
            _normalize_callback_url(callback['url'], strict_cfg)

    def test_agent_callback_reaches_backend_route_successfully(self):
        with patch.object(callback_route.repo, 'apply_remote_callback', return_value={'applied': True}) as apply_mock, \
             patch.object(callback_route.repo, 'get_job', return_value=self._backend_job()), \
             patch.object(callback_route.repo, 'update_job_if_active') as update_mock, \
             patch.object(callback_route.repo, 'add_event') as add_event_mock:
            self._run_agent_notify()

        apply_mock.assert_called_once()
        update_mock.assert_called()
        add_event_mock.assert_called()

    def test_agent_callback_with_wrong_token_is_rejected(self):
        with patch.object(callback_route.repo, 'apply_remote_callback') as apply_mock:
            self._run_agent_notify(callback_token='wrong-secret')

        apply_mock.assert_not_called()

    def test_agent_callback_with_missing_signature_header_is_rejected(self):
        def strip_signature(data, headers):
            headers.pop('X-Webhook-Signature', None)
            return data, headers

        with patch.object(callback_route.repo, 'apply_remote_callback') as apply_mock:
            self._run_agent_notify(mutate_forward=strip_signature)

        apply_mock.assert_not_called()

    def test_agent_callback_with_tampered_signature_is_rejected(self):
        def tamper_signature(data, headers):
            headers['X-Webhook-Signature'] = 'sha256=deadbeef'
            return data, headers

        with patch.object(callback_route.repo, 'apply_remote_callback') as apply_mock:
            self._run_agent_notify(mutate_forward=tamper_signature)

        apply_mock.assert_not_called()

    def test_agent_callback_with_expired_timestamp_is_rejected(self):
        def expire_signature(data, headers):
            old_timestamp = str(int(time.time()) - 3600)
            headers['X-Webhook-Timestamp'] = old_timestamp
            headers['X-Webhook-Signature'] = build_webhook_signature(
                'webhook-shared-secret',
                old_timestamp,
                data,
            )
            return data, headers

        with patch.object(callback_route.repo, 'apply_remote_callback') as apply_mock:
            self._run_agent_notify(mutate_forward=expire_signature)

        apply_mock.assert_not_called()


if __name__ == '__main__':
    unittest.main()
