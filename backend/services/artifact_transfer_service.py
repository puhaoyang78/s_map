#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import pathlib
import re
import ipaddress
from pathlib import Path
from urllib.parse import urlparse

import requests


class ArtifactTransferError(Exception):
    pass


def _required_env(name: str) -> str:
    val = (os.environ.get(name) or '').strip()
    if not val:
        raise ArtifactTransferError(f'缺少环境变量: {name}')
    return val


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
            raise ArtifactTransferError('DETECTION_AGENT_CA_CERT_PATH 文件不存在')
        return str(p)
    return True


def _parse_allowed_ports() -> set[int]:
    ports: set[int] = {80, 443}

    base = (os.environ.get('DETECTION_AGENT_BASE_URL') or '').strip()
    if base:
        parsed = urlparse(base if '://' in base else f'https://{base}')
        if parsed.port:
            ports.add(int(parsed.port))

    extra = (os.environ.get('DETECTION_ARTIFACT_ALLOWED_PORTS') or '').strip()
    if extra:
        for item in extra.split(','):
            raw = item.strip()
            if not raw:
                continue
            try:
                port = int(raw)
            except ValueError as e:
                raise ArtifactTransferError('DETECTION_ARTIFACT_ALLOWED_PORTS 包含非法端口') from e
            if port < 1 or port > 65535:
                raise ArtifactTransferError('DETECTION_ARTIFACT_ALLOWED_PORTS 包含越界端口')
            ports.add(port)

    return ports


def _allow_insecure_http() -> bool:
    return (os.environ.get('DETECTION_AGENT_ALLOW_INSECURE_HTTP') or 'false').strip().lower() in ('1', 'true', 'yes', 'on')


def _parse_allowed_hosts() -> set[str]:
    hosts = set()
    base = (os.environ.get('DETECTION_AGENT_BASE_URL') or '').strip()
    if base:
        parsed = urlparse(base if '://' in base else f'https://{base}')
        if parsed.hostname:
            hosts.add(parsed.hostname.lower())

    extra = (os.environ.get('DETECTION_ARTIFACT_ALLOWED_HOSTS') or '').strip()
    if extra:
        hosts.update(h.strip().lower() for h in extra.split(',') if h.strip())

    return hosts


def _is_private_or_local_host(hostname: str) -> bool:
    try:
        ip = ipaddress.ip_address(hostname)
    except ValueError:
        return hostname.lower() in {'localhost'}
    return bool(ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved)


def _validate_artifact_url(remote_artifact_path: str) -> str:
    parsed = urlparse(remote_artifact_path)
    scheme = (parsed.scheme or '').lower()
    host = (parsed.hostname or '').lower()
    port = parsed.port

    if scheme not in {'http', 'https'}:
        raise ArtifactTransferError('下载地址协议非法')
    if scheme == 'http' and not _allow_insecure_http():
        raise ArtifactTransferError('仅允许 https 下载地址（调试环境可设置 DETECTION_AGENT_ALLOW_INSECURE_HTTP=true）')
    if not host:
        raise ArtifactTransferError('下载地址缺少主机名')

    allow_private = (os.environ.get('DETECTION_ARTIFACT_ALLOW_PRIVATE_HOSTS') or 'false').strip().lower() in ('1', 'true', 'yes', 'on')
    if not allow_private and _is_private_or_local_host(host):
        raise ArtifactTransferError('下载地址指向内网/本地地址，已拒绝')

    allowed_hosts = _parse_allowed_hosts()
    if not allowed_hosts:
        raise ArtifactTransferError('未配置允许的产物下载主机，请设置 DETECTION_AGENT_BASE_URL 或 DETECTION_ARTIFACT_ALLOWED_HOSTS')
    if allowed_hosts and host not in allowed_hosts:
        raise ArtifactTransferError('下载地址主机不在允许列表')

    allowed_ports = _parse_allowed_ports()
    if port is not None and port not in allowed_ports:
        raise ArtifactTransferError('下载地址端口不在允许范围')

    return remote_artifact_path


def validate_artifact_download_url(remote_artifact_path: str) -> str:
    return _validate_artifact_url(remote_artifact_path)


def _sanitize_download_filename(filename: str, job_id: str) -> str:
    raw = (filename or '').strip().strip('"').strip("'")
    if not raw:
        raw = f'{job_id}_artifact.7z'

    safe = os.path.basename(raw).replace('/', '_').replace('\\', '_')
    safe = re.sub(r'[^A-Za-z0-9._-]', '_', safe)
    if not safe:
        safe = f'{job_id}_artifact.7z'
    if not safe.lower().endswith('.7z'):
        safe = f'{safe}.7z'
    return safe


def _max_artifact_bytes() -> int:
    """产物下载字节上限，默认 2GB，可通过 DETECTION_ARTIFACT_MAX_BYTES 覆盖。"""
    raw = (os.environ.get('DETECTION_ARTIFACT_MAX_BYTES') or '').strip()
    try:
        value = int(raw)
    except ValueError:
        value = 0
    return value if value > 0 else 2 * 1024 * 1024 * 1024


def pull_artifact(remote_artifact_path: str, job_id: str) -> str:
    if not remote_artifact_path:
        raise ArtifactTransferError('远端产物下载地址为空')
    remote_artifact_path = _validate_artifact_url(remote_artifact_path)

    token = _required_env('DETECTION_AGENT_TOKEN')
    timeout = int((os.environ.get('DETECTION_AGENT_ARTIFACT_TIMEOUT_SECONDS') or '300').strip())

    local_dir = pathlib.Path(__file__).resolve().parent.parent / 'data' / 'artifacts'
    local_dir.mkdir(parents=True, exist_ok=True)

    try:
        with requests.get(
            remote_artifact_path,
            headers={'Authorization': f'Bearer {token}'},
            timeout=timeout,
            verify=_verify_tls_value(),
            stream=True,
            allow_redirects=False,
        ) as resp:
            if resp.status_code >= 300:
                raise ArtifactTransferError(f'下载产物失败: {resp.status_code} {resp.text[:500]}')

            content_disposition = resp.headers.get('Content-Disposition', '')
            filename = ''
            if 'filename=' in content_disposition:
                filename = content_disposition.split('filename=', 1)[1].strip().strip('"')
            safe_filename = _sanitize_download_filename(filename, job_id)

            local_path = (local_dir / f'{job_id}_{safe_filename}').resolve()
            if local_dir.resolve() not in local_path.parents:
                raise ArtifactTransferError('下载文件路径非法')
            # 先写入 .part 临时文件，完整下载且未超上限后再原子改名，避免残留半截文件
            part_path = local_path.with_name(local_path.name + '.part')
            max_bytes = _max_artifact_bytes()
            try:
                total_bytes = 0
                with open(part_path, 'wb') as f:
                    for chunk in resp.iter_content(chunk_size=1024 * 1024):
                        if not chunk:
                            continue
                        total_bytes += len(chunk)
                        if total_bytes > max_bytes:
                            raise ArtifactTransferError(
                                f'产物大小超过上限（{max_bytes} 字节），已中止下载'
                            )
                        f.write(chunk)
                os.replace(str(part_path), str(local_path))
            except Exception:
                try:
                    if part_path.exists():
                        part_path.unlink()
                except OSError:
                    pass
                raise

            return str(local_path)

    except ArtifactTransferError:
        raise
    except Exception as e:
        raise ArtifactTransferError(f'下载探测产物失败: {e}') from e
