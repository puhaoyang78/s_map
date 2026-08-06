#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
from urllib.parse import urlparse
from collections.abc import Mapping
from typing import Optional


_PLACEHOLDER_PREFIXES = (
    'replace-with-',
    'pk.replace-with-',
)


def _truthy(name: str, default: str = 'false', env: Optional[Mapping[str, str]] = None) -> bool:
    source = os.environ if env is None else env
    return (source.get(name) or default).strip().lower() in {'1', 'true', 'yes', 'on'}


def _env(name: str, env: Optional[Mapping[str, str]] = None) -> str:
    source = os.environ if env is None else env
    return (source.get(name) or '').strip()


def _is_placeholder(value: str) -> bool:
    raw = (value or '').strip().lower()
    if not raw:
        return True
    return any(raw.startswith(prefix) for prefix in _PLACEHOLDER_PREFIXES)


def validate_backend_startup_config(env: Optional[Mapping[str, str]] = None) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    auth_secret = _env('AUTH_SECRET', env)
    if len(auth_secret) < 32 or _is_placeholder(auth_secret):
        errors.append('AUTH_SECRET must be set to a long random value in backend/.env.local')

    artifact_password = _env('DETECTION_ARTIFACT_PASSWORD', env)
    if len(artifact_password) < 12 or _is_placeholder(artifact_password):
        errors.append('DETECTION_ARTIFACT_PASSWORD must be set to a non-template secret in backend/.env.local')

    default_admin_password = _env('DEFAULT_ADMIN_PASSWORD', env)
    if len(default_admin_password) < 12 or _is_placeholder(default_admin_password):
        warnings.append('DEFAULT_ADMIN_PASSWORD still looks like a template value; rotate it if bootstrap login may still rely on it')

    local_artifact = _env('DETECTION_LOCAL_ARTIFACT_PATH', env)
    if not local_artifact:
        agent_base = _env('DETECTION_AGENT_BASE_URL', env)
        agent_token = _env('DETECTION_AGENT_TOKEN', env)
        if _is_placeholder(agent_base):
            errors.append('DETECTION_AGENT_BASE_URL must be set in backend/.env.local when REMOTE_HTTP_MODE is used')
        if _is_placeholder(agent_token):
            errors.append('DETECTION_AGENT_TOKEN must be set in backend/.env.local when REMOTE_HTTP_MODE is used')

    webhook_base = _env('DETECTION_WEBHOOK_BASE_URL', env)
    webhook_token = _env('DETECTION_WEBHOOK_TOKEN', env)
    if webhook_base:
        parsed = urlparse(webhook_base if '://' in webhook_base else f'https://{webhook_base}')
        allow_http = _truthy('DETECTION_WEBHOOK_ALLOW_INSECURE_HTTP', env=env)
        if parsed.scheme not in {'http', 'https'}:
            errors.append('DETECTION_WEBHOOK_BASE_URL must use http or https')
        elif parsed.scheme != 'https' and not allow_http:
            errors.append('DETECTION_WEBHOOK_BASE_URL must use https unless DETECTION_WEBHOOK_ALLOW_INSECURE_HTTP=true')
        if not parsed.hostname:
            errors.append('DETECTION_WEBHOOK_BASE_URL must include a hostname')
        if len(webhook_token) < 32 or _is_placeholder(webhook_token):
            errors.append('DETECTION_WEBHOOK_TOKEN must be set in backend/.env.local when DETECTION_WEBHOOK_BASE_URL is configured')
    elif _truthy('DETECTION_WEBHOOK_REQUIRE_SIGNATURE', env=env) and webhook_token and (len(webhook_token) < 32 or _is_placeholder(webhook_token)):
        warnings.append('DETECTION_WEBHOOK_TOKEN still looks like a template value; callback signature verification will not be safe')

    if not _truthy('AUTH_COOKIE_SECURE', env=env):
        warnings.append('AUTH_COOKIE_SECURE=false; keep it false only for local HTTP development')
    if _truthy('DETECTION_AGENT_ALLOW_INSECURE_HTTP', env=env):
        warnings.append('DETECTION_AGENT_ALLOW_INSECURE_HTTP=true weakens transport security and should stay off outside debugging')
    if _truthy('DETECTION_WEBHOOK_ALLOW_INSECURE_HTTP', env=env):
        warnings.append('DETECTION_WEBHOOK_ALLOW_INSECURE_HTTP=true weakens callback transport security and should stay off outside debugging')

    return errors, warnings


def assert_backend_startup_config() -> None:
    errors, warnings = validate_backend_startup_config()
    for item in warnings:
        print(f'[startup-warning] {item}')
    if errors:
        raise RuntimeError('backend startup config validation failed:\n- ' + '\n- '.join(errors))
