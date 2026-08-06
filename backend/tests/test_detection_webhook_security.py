#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import unittest

from services.probe_runner_service import ProbeRunnerError, build_detection_callback
from utils.webhook_signing import build_webhook_signature, verify_webhook_signature


class DetectionWebhookSecurityTests(unittest.TestCase):
    def setUp(self):
        self._env_backup = dict(os.environ)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env_backup)

    def test_verify_webhook_signature_accepts_valid_payload(self):
        os.environ['DETECTION_WEBHOOK_SIGNATURE_TTL_SECONDS'] = '300'
        payload = b'{"status":"running"}'
        timestamp = str(int(time.time()))
        signature = build_webhook_signature('webhook-secret', timestamp, payload)

        ok, reason = verify_webhook_signature(payload, 'webhook-secret', timestamp, signature, ttl_seconds=300)

        self.assertTrue(ok)
        self.assertEqual(reason, '')

    def test_verify_webhook_signature_rejects_bad_signature(self):
        os.environ['DETECTION_WEBHOOK_SIGNATURE_TTL_SECONDS'] = '300'
        payload = b'{"status":"running"}'
        timestamp = str(int(time.time()))

        ok, reason = verify_webhook_signature(payload, 'webhook-secret', timestamp, 'sha256=deadbeef', ttl_seconds=300)

        self.assertFalse(ok)
        self.assertEqual(reason, 'signature_mismatch')

    def test_verify_webhook_signature_rejects_expired_timestamp(self):
        os.environ['DETECTION_WEBHOOK_SIGNATURE_TTL_SECONDS'] = '10'
        payload = b'{"status":"running"}'
        timestamp = str(int(time.time()) - 120)
        signature = build_webhook_signature('webhook-secret', timestamp, payload)

        ok, reason = verify_webhook_signature(payload, 'webhook-secret', timestamp, signature, ttl_seconds=10)

        self.assertFalse(ok)
        self.assertEqual(reason, 'signature_expired')

    def test_build_detection_callback_requires_token_when_base_url_is_set(self):
        os.environ['DETECTION_WEBHOOK_BASE_URL'] = 'https://backend.example.com'
        os.environ.pop('DETECTION_WEBHOOK_TOKEN', None)

        with self.assertRaises(ProbeRunnerError):
            build_detection_callback('job-1')

    def test_build_detection_callback_rejects_http_by_default(self):
        os.environ['DETECTION_WEBHOOK_BASE_URL'] = 'http://backend.example.com:5000'
        os.environ['DETECTION_WEBHOOK_TOKEN'] = 'secret-token'
        os.environ.pop('DETECTION_WEBHOOK_ALLOW_INSECURE_HTTP', None)

        with self.assertRaises(ProbeRunnerError):
            build_detection_callback('job-1')

    def test_build_detection_callback_allows_https_base(self):
        os.environ['DETECTION_WEBHOOK_BASE_URL'] = 'https://backend.example.com:5443'
        os.environ['DETECTION_WEBHOOK_TOKEN'] = 'secret-token'

        callback = build_detection_callback('job-1')

        self.assertEqual(callback['url'], 'https://backend.example.com:5443/api/detection/jobs/job-1/callback')
        self.assertEqual(callback['token'], 'secret-token')


if __name__ == '__main__':
    unittest.main()
