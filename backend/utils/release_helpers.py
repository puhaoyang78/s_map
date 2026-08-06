#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from urllib import error, request

from utils.deployment_checks import (
    BACKEND_ROOT,
    FRONT_ROOT,
    REPO_ROOT,
    _load_agent_env,
    _path_state,
    _read_database_path,
    build_agent_runtime_status,
    build_backend_runtime_status,
    run_preflight_checks,
    summarize_reports,
)


@dataclass
class HealthProbeResult:
    url: str
    http_status: int
    service: str
    status: str
    warnings: list[str]
    errors: list[str]
    message: str
    ok: bool
    details: dict[str, Any]


def _extract_health_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], str]:
    if isinstance(payload.get('data'), dict):
        return payload['data'], str(payload.get('message') or '')
    return payload, str(payload.get('message') or '')


def probe_health_endpoint(url: str, timeout_seconds: int = 5) -> HealthProbeResult:
    req = request.Request(url, method='GET', headers={'Accept': 'application/json'})
    try:
        with request.urlopen(req, timeout=timeout_seconds) as resp:
            body = resp.read().decode('utf-8')
            payload = json.loads(body)
            http_status = int(resp.status)
    except error.HTTPError as exc:
        body = exc.read().decode('utf-8', errors='replace')
        try:
            payload = json.loads(body)
        except Exception:
            payload = {'message': body or str(exc)}
        normalized, message = _extract_health_payload(payload)
        return HealthProbeResult(
            url=url,
            http_status=int(exc.code),
            service=str(normalized.get('service') or 'unknown'),
            status=str(normalized.get('status') or 'error'),
            warnings=list(normalized.get('warnings') or []),
            errors=list(normalized.get('errors') or []) or [message or f'HTTP {exc.code}'],
            message=message or str(exc),
            ok=False,
            details=normalized,
        )
    except Exception as exc:
        return HealthProbeResult(
            url=url,
            http_status=0,
            service='unknown',
            status='error',
            warnings=[],
            errors=[str(exc)],
            message=str(exc),
            ok=False,
            details={},
        )

    normalized, message = _extract_health_payload(payload)
    status = str(normalized.get('status') or 'error')
    warnings = list(normalized.get('warnings') or [])
    errors = list(normalized.get('errors') or [])
    ok = http_status < 400 and status != 'error'
    return HealthProbeResult(
        url=url,
        http_status=http_status,
        service=str(normalized.get('service') or 'unknown'),
        status=status,
        warnings=warnings,
        errors=errors,
        message=message,
        ok=ok,
        details=normalized,
    )


def create_runtime_backup(
    repo_root: Path = REPO_ROOT,
    agent_env_file: Optional[Path] = None,
    output_root: Optional[Path] = None,
    include_env: bool = False,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    backend_root = repo_root / 'backend'
    front_root = repo_root / 'front'
    output_root = (output_root or (backend_root / 'db_backups')).resolve()
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup_dir = output_root / f'release-backup-{timestamp}'
    backup_dir.mkdir(parents=True, exist_ok=False)

    database_path = _read_database_path(backend_root)
    if not database_path.exists() or not database_path.is_file():
        raise RuntimeError(f'database file is missing and cannot be backed up: {database_path}')

    copied_files: list[dict[str, str]] = []

    db_copy_dir = backup_dir / 'database'
    db_copy_dir.mkdir(parents=True, exist_ok=True)
    db_target = db_copy_dir / database_path.name
    shutil.copy2(database_path, db_target)
    copied_files.append({'type': 'database', 'source': str(database_path), 'target': str(db_target)})

    config_copy_dir = backup_dir / 'config'
    config_copy_dir.mkdir(parents=True, exist_ok=True)
    db_config_path = backend_root / 'config' / 'db_config.json'
    if db_config_path.exists():
        db_config_target = config_copy_dir / db_config_path.name
        shutil.copy2(db_config_path, db_config_target)
        copied_files.append({'type': 'backend-config', 'source': str(db_config_path), 'target': str(db_config_target)})

    env_status = {
        'backendEnvLocal': str((backend_root / '.env.local').resolve()),
        'frontendEnvLocal': str((front_root / '.env.local').resolve()),
        'agentEnvFile': str(agent_env_file.resolve()) if agent_env_file else '',
    }

    if include_env:
        env_copy_dir = backup_dir / 'env'
        env_copy_dir.mkdir(parents=True, exist_ok=True)
        labeled_sources = (
            ('backend', backend_root / '.env.local'),
            ('front', front_root / '.env.local'),
            ('agent', agent_env_file),
        )
        for label, source in labeled_sources:
            if not source:
                continue
            src = source.resolve()
            if not src.exists() or not src.is_file():
                continue
            target = env_copy_dir / f'{label}-{src.name}'
            shutil.copy2(src, target)
            copied_files.append({'type': 'env', 'source': str(src), 'target': str(target)})

    backend_status = build_backend_runtime_status(backend_root=backend_root)
    agent_status = None
    if agent_env_file:
        agent_status = build_agent_runtime_status(repo_root=repo_root, agent_env_file=agent_env_file)

    manifest = {
        'createdAt': datetime.now(timezone.utc).isoformat(),
        'repoRoot': str(repo_root),
        'backupDir': str(backup_dir),
        'databasePath': str(database_path),
        'includeEnv': bool(include_env),
        'copiedFiles': copied_files,
        'envStatus': env_status,
        'backendRuntimeStatus': backend_status,
        'agentRuntimeStatus': agent_status,
        'runtimeDirectories': {
            'artifacts': str((backend_root / 'data' / 'artifacts').resolve()),
            'celery': str((backend_root / 'data' / 'celery').resolve()),
            'logs': str((backend_root / 'logs').resolve()),
            'control': str((backend_root / 'control').resolve()),
            'dbBackups': str((backend_root / 'db_backups').resolve()),
        },
        'restoreHints': [
            'Stop backend API, Celery worker, agent, and frontend before restoring mutable files.',
            'Restore backend/.env.local and the agent EnvironmentFile before restarting services if configuration changed.',
            'Restore the SQLite database file to the path recorded in db_config.json before bringing backend traffic back.',
        ],
    }
    manifest_path = backup_dir / 'manifest.json'
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')

    return {
        'backupDir': str(backup_dir),
        'manifestPath': str(manifest_path),
        'copiedFiles': copied_files,
    }


def build_release_gate_context(
    repo_root: Path = REPO_ROOT,
    agent_env_file: Optional[Path] = None,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    reports = run_preflight_checks(repo_root=repo_root, agent_env_file=agent_env_file)
    return {
        'preflightSummary': summarize_reports(reports),
        'backendRuntimeStatus': build_backend_runtime_status(backend_root=repo_root / 'backend'),
        'agentRuntimeStatus': build_agent_runtime_status(repo_root=repo_root, agent_env_file=agent_env_file) if agent_env_file else None,
        'distState': _path_state((repo_root / 'front' / 'dist' / 'index.html').resolve(), 'file'),
        'reports': [report.to_dict() for report in reports],
    }


def build_post_deploy_runtime_summary(
    repo_root: Path = REPO_ROOT,
    agent_env_file: Optional[Path] = None,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    backend_root = repo_root / 'backend'
    backend_status = build_backend_runtime_status(backend_root=backend_root)
    agent_status = build_agent_runtime_status(repo_root=repo_root, agent_env_file=agent_env_file) if agent_env_file else None

    log_dir = (backend_root / 'logs').resolve()
    backend_log = (log_dir / 'app.log').resolve()
    latest_backup = None
    backup_root = (backend_root / 'db_backups').resolve()
    if backup_root.exists() and backup_root.is_dir():
        candidates = sorted(backup_root.glob('release-backup-*'), key=lambda item: item.stat().st_mtime, reverse=True)
        if candidates:
            latest_backup = str(candidates[0].resolve())

    return {
        'backendRuntimeStatus': backend_status,
        'agentRuntimeStatus': agent_status,
        'distState': _path_state((repo_root / 'front' / 'dist' / 'index.html').resolve(), 'file'),
        'backendLogState': _path_state(backend_log, 'file'),
        'runtimeDirectories': {
            'artifacts': _path_state((backend_root / 'data' / 'artifacts').resolve(), 'dir'),
            'celery': _path_state((backend_root / 'data' / 'celery').resolve(), 'dir'),
            'logs': _path_state(log_dir, 'dir'),
            'control': _path_state((backend_root / 'control').resolve(), 'dir'),
            'dbBackups': _path_state(backup_root, 'dir'),
        },
        'latestBackupDir': latest_backup,
    }
