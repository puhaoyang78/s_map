#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
from pathlib import Path
from urllib.parse import urljoin
from urllib.parse import urlparse

import requests


class ProbeRunnerError(Exception):
    pass


def _env_int(name: str, default: int, minimum: int = 0) -> int:
    raw = (os.environ.get(name) or '').strip()
    if not raw:
        return max(default, minimum)
    try:
        value = int(raw)
    except ValueError as e:
        raise ProbeRunnerError(f'{name} 必须是整数') from e
    return max(value, minimum)


def _env_float(name: str, default: float, minimum: float = 0.0) -> float:
    raw = (os.environ.get(name) or '').strip()
    if not raw:
        return max(default, minimum)
    try:
        value = float(raw)
    except ValueError as e:
        raise ProbeRunnerError(f'{name} 必须是数字') from e
    return max(value, minimum)


def _required_env(name: str) -> str:
    val = (os.environ.get(name) or '').strip()
    if not val:
        raise ProbeRunnerError(f'缺少环境变量: {name}')
    return val


def _agent_base_url() -> str:
    base = _required_env('DETECTION_AGENT_BASE_URL').rstrip('/') + '/'
    parsed = urlparse(base)
    allow_http = (os.environ.get('DETECTION_AGENT_ALLOW_INSECURE_HTTP') or 'false').strip().lower() in ('1', 'true', 'yes', 'on')
    if parsed.scheme != 'https' and not allow_http:
        raise ProbeRunnerError('DETECTION_AGENT_BASE_URL 必须使用 https（如需调试可显式开启 DETECTION_AGENT_ALLOW_INSECURE_HTTP=true）')
    return base


def _agent_token() -> str:
    return _required_env('DETECTION_AGENT_TOKEN')


def _agent_headers() -> dict:
    return {
        'Authorization': f'Bearer {_agent_token()}',
        'Content-Type': 'application/json',
    }


def _verify_tls_value():
    verify_tls = (os.environ.get('DETECTION_AGENT_VERIFY_TLS') or 'true').strip().lower() in ('1', 'true', 'yes', 'on')
    if not verify_tls:
        return False

    ca_cert = (os.environ.get('DETECTION_AGENT_CA_CERT_PATH') or '').strip()
    if ca_cert:
        p = Path(ca_cert)
        if not p.is_absolute():
            backend_root = Path(__file__).resolve().parent.parent
            workspace_root = backend_root.parent
            candidates = [
                (backend_root / p).resolve(),
                (workspace_root / p).resolve(),
            ]
            p = next((cp for cp in candidates if cp.exists() and cp.is_file()), candidates[0])
        if not p.exists() or not p.is_file():
            raise ProbeRunnerError('DETECTION_AGENT_CA_CERT_PATH 文件不存在')
        return str(p)
    return True


def _request_json(method: str, url: str, timeout: int, json_body=None) -> dict:
    retries = _env_int('DETECTION_AGENT_HTTP_RETRIES', 2, minimum=0)
    backoff = _env_float('DETECTION_AGENT_HTTP_RETRY_BACKOFF_SECONDS', 1.5, minimum=0.1)
    last_err = ''

    for attempt in range(retries + 1):
        try:
            resp = requests.request(
                method=method,
                url=url,
                headers=_agent_headers(),
                timeout=timeout,
                verify=_verify_tls_value(),
                json=json_body,
            )
            if resp.status_code >= 500:
                last_err = f'探测服务返回 {resp.status_code}: {resp.text[:500]}'
            elif resp.status_code >= 300:
                raise ProbeRunnerError(f'探测服务返回异常: {resp.status_code} {resp.text[:500]}')
            else:
                return resp.json() if resp.content else {}
        except ProbeRunnerError:
            raise
        except Exception as e:
            last_err = f'调用探测服务失败: {e}'

        if attempt < retries:
            time.sleep(backoff * (attempt + 1))

    raise ProbeRunnerError(last_err or '调用探测服务失败')


def build_detection_callback(job_id: str) -> dict:
    base = (os.environ.get('DETECTION_WEBHOOK_BASE_URL') or '').strip()
    if not base:
        return {}
    token = (os.environ.get('DETECTION_WEBHOOK_TOKEN') or '').strip()
    if not token:
        raise ProbeRunnerError('已配置 DETECTION_WEBHOOK_BASE_URL，但缺少 DETECTION_WEBHOOK_TOKEN')
    parsed = urlparse(base if '://' in base else f'https://{base}')
    allow_http = (os.environ.get('DETECTION_WEBHOOK_ALLOW_INSECURE_HTTP') or 'false').strip().lower() in ('1', 'true', 'yes', 'on')
    if parsed.scheme not in {'http', 'https'}:
        raise ProbeRunnerError('DETECTION_WEBHOOK_BASE_URL must use http or https')
    if parsed.scheme != 'https' and not allow_http:
        raise ProbeRunnerError('DETECTION_WEBHOOK_BASE_URL must use https unless DETECTION_WEBHOOK_ALLOW_INSECURE_HTTP=true')
    if not parsed.hostname:
        raise ProbeRunnerError('DETECTION_WEBHOOK_BASE_URL is missing a hostname')
    base = parsed.geturl().rstrip('/') + '/'
    return {
        'url': urljoin(base, f'api/detection/jobs/{job_id}/callback'),
        'token': token,
    }


def validate_probe_runtime_config():
    """检查探测运行所需配置，返回(local_mode, mode_name)。"""
    local_artifact = (os.environ.get('DETECTION_LOCAL_ARTIFACT_PATH') or '').strip()
    if local_artifact:
        p = Path(local_artifact)
        if not p.exists() or not p.is_file():
            raise ProbeRunnerError('DETECTION_LOCAL_ARTIFACT_PATH 指向的文件不存在')
        return True, 'LOCAL_MODE'

    _required_env('DETECTION_AGENT_BASE_URL')
    _required_env('DETECTION_AGENT_TOKEN')
    return False, 'REMOTE_HTTP_MODE'


def run_global_probe() -> dict:
    """兼容旧调用：仅用于 LOCAL_MODE。"""
    local_mode, _ = validate_probe_runtime_config()
    if not local_mode:
        raise ProbeRunnerError('REMOTE_HTTP_MODE 下请使用 start_remote_probe / poll_remote_probe')

    local_artifact = (os.environ.get('DETECTION_LOCAL_ARTIFACT_PATH') or '').strip()
    return {
        'local_artifact_path': local_artifact,
        'stdout': 'LOCAL_MODE',
        'stderr': '',
    }


def _normalize_probe_regions(regions) -> list[str]:
    if not isinstance(regions, list):
        return []
    normalized = []
    seen = set()
    for item in regions:
        if not isinstance(item, str):
            continue
        parts = [p.strip() for p in item.split(',')]
        if len(parts) != 3 or not all(parts):
            continue
        key = ','.join(parts)
        if key in seen:
            continue
        normalized.append(key)
        seen.add(key)
    return normalized


def start_remote_probe(job_id: str, target_scope: str = 'global', target_regions=None) -> dict:
    base = _agent_base_url()
    url = urljoin(base, 'api/v1/jobs')
    timeout = _env_int('DETECTION_AGENT_START_TIMEOUT_SECONDS', 30, minimum=1)

    payload = {
        'target_scope': 'selected' if (target_scope or '').strip().lower() == 'selected' else 'global',
    }
    callback = build_detection_callback(job_id)
    if callback:
        payload['callback'] = callback

    probe_regions = _normalize_probe_regions(target_regions)
    if payload['target_scope'] == 'selected' and probe_regions:
        payload['probe_regions'] = probe_regions
        payload['probe_region_list'] = ';'.join(probe_regions)

    data = _request_json('POST', url, timeout, json_body=payload)
    job = data.get('job') or {}
    remote_job_id = (job.get('id') or '').strip()
    if not remote_job_id:
        raise ProbeRunnerError('探测服务未返回 remote job id')

    return {'remote_job_id': remote_job_id}


def poll_remote_probe(remote_job_id: str) -> dict:
    base = _agent_base_url()
    url = urljoin(base, f'api/v1/jobs/{remote_job_id}')
    timeout = _env_int('DETECTION_AGENT_STATUS_TIMEOUT_SECONDS', 30, minimum=1)

    data = _request_json('GET', url, timeout)
    job = data.get('job') or {}
    if not job:
        raise ProbeRunnerError('探测服务状态响应缺少 job 数据')

    status = (job.get('status') or '').strip().lower()
    message = (job.get('message') or '').strip()
    error_message = (job.get('error_message') or '').strip()

    artifact_download_url = (job.get('artifact_download_url') or '').strip()
    if artifact_download_url and artifact_download_url.startswith('/'):
        artifact_download_url = urljoin(base, artifact_download_url.lstrip('/'))

    return {
        'status': status,
        'message': message,
        'error_message': error_message,
        'artifact_download_url': artifact_download_url,
    }


def cancel_remote_probe(remote_job_id: str):
    base = _agent_base_url()
    url = urljoin(base, f'api/v1/jobs/{remote_job_id}/cancel')
    timeout = _env_int('DETECTION_AGENT_CANCEL_TIMEOUT_SECONDS', 30, minimum=1)

    _request_json('POST', url, timeout, json_body={})

    return True
