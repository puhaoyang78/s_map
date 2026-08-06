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
FRONTEND_ROOT = REPO_ROOT / 'front'


def _npm_command() -> str:
    return 'npm.cmd' if os.name == 'nt' else 'npm'


def _run_step(title: str, command: list[str], cwd: Path) -> None:
    print(f'==> {title}')
    subprocess.run(command, cwd=str(cwd), check=True)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description='Run the CI-friendly minimum acceptance pipeline.')
    parser.add_argument(
        '--agent-env-file',
        default='',
        help='Optional agent EnvironmentFile path forwarded to scripts/preflight_check.py',
    )
    parser.add_argument(
        '--skip-preflight',
        action='store_true',
        help='Skip the preflight step when it has already been run by a higher-level release gate.',
    )
    args = parser.parse_args(argv)

    steps = []
    if not args.skip_preflight:
        preflight_cmd = [sys.executable, str(REPO_ROOT / 'scripts' / 'preflight_check.py')]
        if args.agent_env_file:
            preflight_cmd.extend(['--agent-env-file', args.agent_env_file])
        steps.append(('preflight check', preflight_cmd, REPO_ROOT))

    steps.extend([
        ('backend unit tests', [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'], BACKEND_ROOT),
        ('frontend lint', [_npm_command(), 'run', 'lint'], FRONTEND_ROOT),
        ('frontend build', [_npm_command(), 'run', 'build'], FRONTEND_ROOT),
    ])

    for title, command, cwd in steps:
        _run_step(title, command, cwd)

    print('Acceptance pipeline passed.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
