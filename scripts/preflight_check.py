#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / 'backend'

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from utils.deployment_checks import (  # noqa: E402
    _load_agent_env,
    render_reports,
    run_preflight_checks,
    summarize_reports,
)


def _probe_timeout_warning(agent_env_file: Optional[Path]) -> str:
    """Warn when the agent probe timeout is disabled (0, unset, or unparsable).

    PROBE_TIMEOUT_SECONDS=0 means agent probes run without a timeout; a hung
    probe would leak a thread and a subprocess forever.
    """
    env, _example_env_file, _selected_env_file = _load_agent_env(repo_root=REPO_ROOT, agent_env_file=agent_env_file)
    raw = (env.get('PROBE_TIMEOUT_SECONDS') or '').strip()
    try:
        timeout_seconds = int(raw) if raw else 0
    except ValueError:
        timeout_seconds = 0
    if timeout_seconds > 0:
        return ''
    return (
        'PROBE_TIMEOUT_SECONDS is 0 or unset; agent probes run without a timeout and a hung probe '
        'would leak a thread and subprocess. Set a positive PROBE_TIMEOUT_SECONDS in the agent EnvironmentFile.'
    )


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description='Run deployment preflight checks for backend, frontend and agent.')
    parser.add_argument(
        '--mode',
        choices=['local', 'deploy'],
        default='local',
        help='Validation strictness. deploy keeps deploy-only requirements as errors; local downgrades them to warnings.',
    )
    parser.add_argument(
        '--agent-env-file',
        default='',
        help='Optional agent EnvironmentFile path, for example /etc/detection-agent/agent.env',
    )
    args = parser.parse_args(argv)

    agent_env_file = Path(args.agent_env_file).expanduser() if args.agent_env_file else None
    reports = run_preflight_checks(repo_root=REPO_ROOT, agent_env_file=agent_env_file, mode=args.mode)
    print(render_reports(reports))

    summary = summarize_reports(reports)
    warnings = summary['warnings']
    probe_warning = _probe_timeout_warning(agent_env_file)
    if probe_warning:
        warnings += 1
        print(f'  WARN {probe_warning}')

    if summary['errors']:
        print('\nPreflight failed. Fix the errors above and rerun this command.')
        return 1

    print('\nPreflight passed.')
    if warnings:
        print('Warnings remain. Review them before promoting to production.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
