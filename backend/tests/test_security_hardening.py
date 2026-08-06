#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import unittest

from utils.password_policy import validate_password_strength
from services.artifact_transfer_service import (
    _sanitize_download_filename,
    _validate_artifact_url,
    ArtifactTransferError,
)


class PasswordPolicyTests(unittest.TestCase):
    def test_rejects_weak_password(self):
        ok, msg = validate_password_strength('123456')
        self.assertFalse(ok)
        self.assertTrue(msg)

    def test_accepts_strong_password(self):
        ok, msg = validate_password_strength('GoodPass!2026')
        self.assertTrue(ok)
        self.assertEqual(msg, '')


class ArtifactTransferSecurityTests(unittest.TestCase):
    def setUp(self):
        self._env_backup = dict(os.environ)
        os.environ['DETECTION_AGENT_BASE_URL'] = 'https://agent.example.com'
        os.environ.pop('DETECTION_ARTIFACT_ALLOWED_HOSTS', None)
        os.environ.pop('DETECTION_ARTIFACT_ALLOW_PRIVATE_HOSTS', None)
        os.environ.pop('DETECTION_AGENT_ALLOW_INSECURE_HTTP', None)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env_backup)

    def test_validate_artifact_url_rejects_private_host(self):
        with self.assertRaises(ArtifactTransferError):
            _validate_artifact_url('https://127.0.0.1:443/file.7z')

    def test_validate_artifact_url_rejects_unknown_host(self):
        with self.assertRaises(ArtifactTransferError):
            _validate_artifact_url('https://evil.example.com/file.7z')

    def test_validate_artifact_url_allows_configured_host(self):
        url = _validate_artifact_url('https://agent.example.com/api/v1/jobs/1/artifact')
        self.assertIn('agent.example.com', url)

    def test_sanitize_filename_removes_traversal(self):
        name = _sanitize_download_filename('../../../../etc/passwd', 'job1')
        self.assertNotIn('..', name)
        self.assertNotIn('/', name)
        self.assertTrue(name.endswith('.7z'))


if __name__ == '__main__':
    unittest.main()
