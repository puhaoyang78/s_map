#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / 'backend'

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from utils.release_helpers import build_post_deploy_runtime_summary, probe_health_endpoint  # noqa: E402


def _line(level: str, message: str) -> str:
    prefix = {
        'ok': 'PASS',
        'warning': 'WARN',
        'error': 'FAIL',
    }.get(level, level.upper())
    return f'[{prefix}] {message}'


def _latest_backup_age(backup_dir: str) -> Optional[timedelta]:
    """Age of the newest backup, parsed from its release-backup-<UTC timestamp> name.

    Falls back to the directory mtime (same source release_helpers uses to pick
    the latest backup) when the name carries no parseable timestamp.
    """
    path = Path(backup_dir)
    try:
        created_at = datetime.strptime(path.name, 'release-backup-%Y%m%dT%H%M%SZ').replace(tzinfo=timezone.utc)
    except ValueError:
        try:
            created_at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        except OSError:
            return None
    return datetime.now(timezone.utc) - created_at


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description='Run a lightweight post-deploy runtime check after services restart.')
    parser.add_argument('--backend-health-url', default='', help='Backend health endpoint URL, for example http://replace-with-your-backend-host:5000/api/health')
    parser.add_argument('--agent-health-url', default='', help='Agent health endpoint URL, for example https://replace-with-your-agent-host:18080/api/v1/health')
    parser.add_argument('--agent-env-file', default='', help='Optional deployed agent EnvironmentFile path for local runtime path summary.')
    parser.add_argument('--health-timeout', type=int, default=5)
    parser.add_argument('--fail-on-warning', action='store_true', help='Treat warnings as failures.')
    args = parser.parse_args(argv)

    failures: list[str] = []
    warnings: list[str] = []
    passes: list[str] = []

    agent_env_file = Path(args.agent_env_file).expanduser() if args.agent_env_file else None
    summary = build_post_deploy_runtime_summary(repo_root=REPO_ROOT, agent_env_file=agent_env_file)

    dist_state = summary['distState']
    if dist_state['exists'] and dist_state['is_file']:
        passes.append(f'frontend dist artifact exists: {dist_state["path"]}')
    else:
        failures.append(f'frontend dist artifact is missing: {dist_state["path"]}')

    backend_log_state = summary['backendLogState']
    if backend_log_state['exists'] and backend_log_state['is_file']:
        passes.append(f'backend log file exists: {backend_log_state["path"]}')
    else:
        warnings.append(f'backend log file is missing: {backend_log_state["path"]}')

    for label, state in summary['runtimeDirectories'].items():
        if state['exists'] and state['is_dir']:
            passes.append(f'runtime directory present: {state["path"]}')
        else:
            failures.append(f'runtime directory missing: {state["path"]}')

    for label, url in (
        ('backend', args.backend_health_url),
        ('agent', args.agent_health_url),
    ):
        if not url:
            warnings.append(f'{label} health URL was not provided')
            continue
        result = probe_health_endpoint(url, timeout_seconds=max(1, int(args.health_timeout)))
        if not result.ok:
            failures.append(f'{label} health probe failed: {result.message or ", ".join(result.errors)} ({url})')
            continue
        if result.status == 'warning' or result.warnings:
            warnings.append(f'{label} health returned warning status: {url}')
        else:
            passes.append(f'{label} health is healthy: {url}')

    latest_backup = summary.get('latestBackupDir')
    if latest_backup:
        backup_age = _latest_backup_age(latest_backup)
        if backup_age is not None and backup_age > timedelta(hours=24):
            warnings.append(
                f'latest runtime backup is older than 24 hours: {latest_backup}'
                ' (take a fresh backup with scripts/backup_runtime.py before relying on rollback)'
            )
        else:
            passes.append(f'latest runtime backup directory: {latest_backup}')
    else:
        warnings.append('no release-backup-* directory found under backend/db_backups')

    print('==> post-deploy summary')
    for item in passes:
        print(_line('ok', item))
    for item in warnings:
        print(_line('warning', item))
    for item in failures:
        print(_line('error', item))

    print('\nOperational hints:')
    print(f'- backend database path: {summary["backendRuntimeStatus"]["paths"]["databasePath"]["path"]}')
    if summary['agentRuntimeStatus']:
        print(f'- agent artifact dir: {summary["agentRuntimeStatus"]["paths"]["artifactDir"]["path"]}')
        print(f'- agent callback allowlist configured: {summary["agentRuntimeStatus"]["callbackAllowlistConfigured"]}')
    else:
        print('- agent artifact dir: (agent env file not provided)')

    if failures or (warnings and args.fail_on_warning):
        print('\nPost-deploy check failed.')
        if warnings and args.fail_on_warning and not failures:
            print('Warnings were treated as failures because --fail-on-warning was set.')
        return 1

    print('\nPost-deploy check passed.')
    if warnings:
        print('Warnings remain. Review them during day-1 operations.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
