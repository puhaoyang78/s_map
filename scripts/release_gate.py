#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / 'backend'

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from utils.deployment_checks import render_reports, run_preflight_checks, summarize_reports  # noqa: E402
from utils.release_helpers import build_release_gate_context, probe_health_endpoint  # noqa: E402


def _status_line(level: str, message: str) -> str:
    prefix = {
        'ok': 'PASS',
        'warning': 'WARN',
        'error': 'FAIL',
    }.get(level, level.upper())
    return f'[{prefix}] {message}'


def _npm_build_artifact_message(dist_state: dict) -> tuple[str, str]:
    if dist_state['exists'] and dist_state['is_file']:
        return 'ok', f'frontend build artifact is present: {dist_state["path"]}'
    return 'error', f'frontend build artifact is missing: {dist_state["path"]}'


def _run_acceptance(agent_env_file: str, skip_preflight: bool = True) -> tuple[bool, str]:
    command = [sys.executable, str(REPO_ROOT / 'scripts' / 'acceptance_check.py')]
    if skip_preflight:
        command.append('--skip-preflight')
    if agent_env_file:
        command.extend(['--agent-env-file', agent_env_file])

    try:
        subprocess.run(command, cwd=str(REPO_ROOT), check=True)
        return True, 'acceptance pipeline passed'
    except subprocess.CalledProcessError as exc:
        return False, f'acceptance pipeline failed with exit code {exc.returncode}'


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description='Run the final release gate for local or deploy-mode promotion.')
    parser.add_argument('--mode', choices=['local', 'deploy'], default='local')
    parser.add_argument('--agent-env-file', default='', help='Agent EnvironmentFile path for strict deploy validation.')
    parser.add_argument('--backend-health-url', default='', help='Backend health endpoint URL, for example http://replace-with-your-backend-host:5000/api/health')
    parser.add_argument('--agent-health-url', default='', help='Agent health endpoint URL, for example https://replace-with-your-agent-host:18080/api/v1/health')
    parser.add_argument('--health-timeout', type=int, default=5)
    parser.add_argument('--skip-acceptance', action='store_true', help='Skip backend tests and frontend lint/build when only post-deploy smoke is needed (local mode only; rejected in deploy mode).')
    parser.add_argument('--skip-health', action='store_true', help='Skip runtime health endpoint probes (local mode only; rejected in deploy mode).')
    parser.add_argument('--fail-on-warning', action='store_true', help='Treat warnings as release-gate failures.')
    args = parser.parse_args(argv)

    if args.mode == 'deploy' and args.skip_acceptance:
        parser.error('--skip-acceptance is not allowed in deploy mode; the release gate must run the acceptance pipeline before promotion')
    if args.mode == 'deploy' and args.skip_health:
        parser.error('--skip-health is not allowed in deploy mode; the release gate must probe runtime health endpoints before promotion')

    failures: list[str] = []
    warnings: list[str] = []
    passes: list[str] = []

    agent_env_file = Path(args.agent_env_file).expanduser() if args.agent_env_file else None

    reports = run_preflight_checks(repo_root=REPO_ROOT, agent_env_file=agent_env_file, mode=args.mode)
    print('==> preflight report')
    print(render_reports(reports))
    preflight_summary = summarize_reports(reports)
    if preflight_summary['errors']:
        failures.append(f'preflight reported {preflight_summary["errors"]} error(s)')
    else:
        passes.append('preflight passed without hard errors')
    if preflight_summary['warnings']:
        warnings.append(f'preflight reported {preflight_summary["warnings"]} warning(s)')

    if args.mode == 'deploy' and not agent_env_file:
        failures.append('deploy mode requires --agent-env-file so the real agent EnvironmentFile is checked')

    if not args.skip_acceptance:
        print('\n==> acceptance pipeline')
        ok, message = _run_acceptance(str(agent_env_file) if agent_env_file else '', skip_preflight=True)
        if ok:
            passes.append(message)
        else:
            failures.append(message)
    else:
        warnings.append('acceptance pipeline was skipped')

    context = build_release_gate_context(repo_root=REPO_ROOT, agent_env_file=agent_env_file)
    level, message = _npm_build_artifact_message(context['distState'])
    if level == 'ok':
        passes.append(message)
    else:
        failures.append(message)

    if not args.skip_health:
        if args.mode == 'deploy' and (not args.backend_health_url or not args.agent_health_url):
            failures.append('deploy mode requires --backend-health-url and --agent-health-url')
        else:
            for label, url in (
                ('backend', args.backend_health_url),
                ('agent', args.agent_health_url),
            ):
                if not url:
                    warnings.append(f'{label} health probe was skipped because no URL was provided')
                    continue
                result = probe_health_endpoint(url, timeout_seconds=max(1, int(args.health_timeout)))
                if not result.ok:
                    failures.append(f'{label} health probe failed: {result.message or ", ".join(result.errors)} ({url})')
                    continue
                if result.status == 'warning' or result.warnings:
                    warnings.append(f'{label} health returned warning status ({url})')
                else:
                    passes.append(f'{label} health is healthy: {url}')
    else:
        warnings.append('runtime health probes were skipped')

    print('\n==> release gate summary')
    for item in passes:
        print(_status_line('ok', item))
    for item in warnings:
        print(_status_line('warning', item))
    for item in failures:
        print(_status_line('error', item))

    print('\nContext:')
    print(f'- mode: {args.mode}')
    print(f'- agent env file: {agent_env_file or "(not provided)"}')
    print(f'- backend dist artifact: {context["distState"]["path"]}')
    print(f'- backend health url: {args.backend_health_url or "(not provided)"}')
    print(f'- agent health url: {args.agent_health_url or "(not provided)"}')

    if failures or (warnings and args.fail_on_warning):
        print('\nRelease gate failed.')
        if warnings and args.fail_on_warning and not failures:
            print('Warnings were treated as failures because --fail-on-warning was set.')
        return 1

    print('\nRelease gate passed.')
    if warnings:
        print('Warnings remain. Review them before promoting to production.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
