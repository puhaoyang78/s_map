#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from detection_server_agent import (  # noqa: E402
    AgentConfig,
    CallbackValidationError,
    _build_callback_signature,
    _normalize_callback_url,
)


class DetectionAgentCallbackSecurityTests(unittest.TestCase):
    def _cfg(self, **overrides):
        base = AgentConfig(
            callback_allow_insecure_http=False,
            callback_allow_private_hosts=False,
            callback_require_token=True,
            callback_allowed_hosts=('backend.example.com', '*.internal.example.com'),
            callback_allowed_ports=(8443,),
        )
        data = base.__dict__.copy()
        data.update(overrides)
        return AgentConfig(**data)

    @patch('detection_server_agent.socket.getaddrinfo', return_value=[(0, 0, 0, '', ('8.8.8.8', 8443))])
    def test_normalize_callback_url_allows_whitelisted_host_and_port(self, _mock_getaddrinfo):
        cfg = self._cfg()
        normalized = _normalize_callback_url('https://backend.example.com:8443/api/detection/jobs/1/callback', cfg)
        self.assertEqual(normalized, 'https://backend.example.com:8443/api/detection/jobs/1/callback')

    @patch('detection_server_agent.socket.getaddrinfo', return_value=[(0, 0, 0, '', ('8.8.8.8', 8443))])
    def test_normalize_callback_url_rejects_host_outside_allowlist(self, _mock_getaddrinfo):
        with self.assertRaises(CallbackValidationError):
            _normalize_callback_url('https://evil.example.com:8443/api/callback', self._cfg())

    def test_normalize_callback_url_rejects_localhost(self):
        with self.assertRaises(CallbackValidationError):
            _normalize_callback_url('https://localhost:8443/api/callback', self._cfg())

    def test_normalize_callback_url_rejects_private_ip_literal(self):
        with self.assertRaises(CallbackValidationError):
            _normalize_callback_url('https://127.0.0.1:8443/api/callback', self._cfg())

    @patch('detection_server_agent.socket.getaddrinfo', return_value=[(0, 0, 0, '', ('8.8.8.8', 5000))])
    def test_normalize_callback_url_rejects_disallowed_port(self, _mock_getaddrinfo):
        with self.assertRaises(CallbackValidationError):
            _normalize_callback_url('https://backend.example.com:5000/api/callback', self._cfg())

    @patch('detection_server_agent.socket.getaddrinfo', return_value=[(0, 0, 0, '', ('10.0.0.5', 8443))])
    def test_normalize_callback_url_rejects_hostname_resolving_to_private_ip(self, _mock_getaddrinfo):
        with self.assertRaises(CallbackValidationError):
            _normalize_callback_url('https://backend.example.com:8443/api/callback', self._cfg())

    @patch('detection_server_agent.socket.getaddrinfo', return_value=[(0, 0, 0, '', ('8.8.8.8', 443))])
    def test_normalize_callback_url_allows_default_https_port(self, _mock_getaddrinfo):
        normalized = _normalize_callback_url('https://api.internal.example.com/api/callback', self._cfg())
        self.assertEqual(normalized, 'https://api.internal.example.com/api/callback')

    def test_build_callback_signature_is_stable(self):
        payload = b'{"event_id":"evt-1","status":"queued"}'
        signature = _build_callback_signature('shared-secret', '1710000000', payload)
        self.assertEqual(
            signature,
            'sha256=aa37b98d3d241e8244f150cdc1635c0c5b982c8b3dbee13721d8a332f24ea017',
        )


if __name__ == '__main__':
    unittest.main()
