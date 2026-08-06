#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / 'backend'

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from utils.release_helpers import build_post_deploy_runtime_summary, build_release_gate_context, create_runtime_backup  # noqa: E402


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description='Create a lightweight runtime backup for the current deployment state.')
    parser.add_argument('--agent-env-file', default='', help='Optional deployed agent EnvironmentFile path to record or back up.')
    parser.add_argument('--output-dir', default='', help='Optional backup root directory. Defaults to backend/db_backups.')
    parser.add_argument('--include-env', action='store_true', help='Copy backend/.env.local, front/.env.local, and the agent env file into the backup directory.')
    args = parser.parse_args(argv)

    agent_env_file = Path(args.agent_env_file).expanduser() if args.agent_env_file else None
    output_dir = Path(args.output_dir).expanduser() if args.output_dir else None

    result = create_runtime_backup(
        repo_root=REPO_ROOT,
        agent_env_file=agent_env_file,
        output_root=output_dir,
        include_env=args.include_env,
    )
    context = build_release_gate_context(repo_root=REPO_ROOT, agent_env_file=agent_env_file)

    print('Runtime backup created.')
    print(f'- backup directory: {result["backupDir"]}')
    print(f'- manifest: {result["manifestPath"]}')
    print(f'- copied file count: {len(result["copiedFiles"])}')
    print(f'- backend database: {context["backendRuntimeStatus"]["paths"]["databasePath"]["path"]}')
    if context['agentRuntimeStatus']:
        print(f'- agent artifact dir: {context["agentRuntimeStatus"]["paths"]["artifactDir"]["path"]}')
    else:
        print('- agent artifact dir: (agent env file not provided)')

    manifest = json.loads(Path(result['manifestPath']).read_text(encoding='utf-8'))
    runtime_summary = build_post_deploy_runtime_summary(repo_root=REPO_ROOT, agent_env_file=agent_env_file)
    print('\nRestore hints:')
    for item in manifest.get('restoreHints') or []:
        print(f'- {item}')
    print('\nBackup validity checkpoints:')
    print(f'- latest backup directory recorded: {runtime_summary["latestBackupDir"] or result["backupDir"]}')
    print(f'- backend log file path: {runtime_summary["backendLogState"]["path"]}')
    print(f'- backend database exists now: {runtime_summary["backendRuntimeStatus"]["paths"]["databasePath"]["exists"]}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
