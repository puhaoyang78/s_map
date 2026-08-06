#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
from collections.abc import Mapping

from utils.startup_validation import validate_backend_startup_config


BACKEND_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_ROOT.parent
FRONT_ROOT = REPO_ROOT / 'front'

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from detection_server_agent import _load_config, _validate_agent_config  # noqa: E402


_PLACEHOLDER_PREFIXES = (
    'replace-with-',
    'pk.replace-with-',
)


@dataclass
class CheckItem:
    level: str
    message: str
    hint: str = ''


@dataclass
class SectionReport:
    name: str
    items: list[CheckItem] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    def add(self, level: str, message: str, hint: str = '') -> None:
        self.items.append(CheckItem(level=level, message=message, hint=hint))

    def add_ok(self, message: str) -> None:
        self.add('ok', message)

    def add_warning(self, message: str, hint: str = '') -> None:
        self.add('warning', message, hint)

    def add_error(self, message: str, hint: str = '') -> None:
        self.add('error', message, hint)

    @property
    def errors(self) -> list[CheckItem]:
        return [item for item in self.items if item.level == 'error']

    @property
    def warnings(self) -> list[CheckItem]:
        return [item for item in self.items if item.level == 'warning']

    @property
    def oks(self) -> list[CheckItem]:
        return [item for item in self.items if item.level == 'ok']

    def to_dict(self) -> dict[str, Any]:
        return {
            'name': self.name,
            'status': 'error' if self.errors else ('warning' if self.warnings else 'ok'),
            'items': [
                {
                    'level': item.level,
                    'message': item.message,
                    'hint': item.hint,
                }
                for item in self.items
            ],
            'details': self.details,
        }


def _parse_env_file(path: Path) -> dict[str, str]:
    parsed: dict[str, str] = {}
    if not path.exists() or not path.is_file():
        return parsed

    for raw_line in path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('export '):
            line = line[7:].strip()
        if '=' not in line:
            continue

        key, value = line.split('=', 1)
        key = key.strip()
        value = value.strip()
        if value.startswith(("'", '"')) and value.endswith(("'", '"')) and len(value) >= 2:
            value = value[1:-1]
        parsed[key] = value
    return parsed


def _merge_env_layers(*layers: Optional[Mapping[str, str]]) -> dict[str, str]:
    merged: dict[str, str] = {}
    for layer in layers:
        if not layer:
            continue
        for key, value in layer.items():
            if value is None:
                continue
            merged[str(key)] = str(value)
    return merged


def _is_placeholder(value: str) -> bool:
    normalized = (value or '').strip().lower()
    if not normalized:
        return True
    return any(normalized.startswith(prefix) for prefix in _PLACEHOLDER_PREFIXES)


def _resolve_path(raw_value: str, base_dir: Path) -> Path:
    candidate = Path((raw_value or '').strip()).expanduser()
    if not candidate.is_absolute():
        candidate = base_dir / candidate
    return candidate.resolve()


def _path_state(target: Path, expected_kind: str) -> dict[str, Any]:
    exists = target.exists()
    is_dir = target.is_dir()
    is_file = target.is_file()
    parent = target if expected_kind == 'dir' else target.parent

    if exists:
        writable = os.access(target, os.W_OK)
    else:
        writable = parent.exists() and os.access(parent, os.W_OK)

    return {
        'path': str(target),
        'exists': exists,
        'is_dir': is_dir,
        'is_file': is_file,
        'writable': writable,
        'parent': str(parent),
        'parent_exists': parent.exists(),
    }


def _load_backend_env(
    backend_root: Path = BACKEND_ROOT,
    process_env: Optional[Mapping[str, str]] = None,
) -> tuple[dict[str, str], Path, Path]:
    base_env_file = backend_root / '.env'
    local_env_file = backend_root / '.env.local'
    env = _merge_env_layers(
        _parse_env_file(base_env_file),
        _parse_env_file(local_env_file),
        process_env or os.environ,
    )
    return env, base_env_file, local_env_file


def _load_frontend_env(
    front_root: Path = FRONT_ROOT,
    process_env: Optional[Mapping[str, str]] = None,
) -> tuple[dict[str, str], Path, Path, Path, Path]:
    example_env_file = front_root / '.env.example'
    local_env_file = front_root / '.env.local'
    production_env_file = front_root / '.env.production'
    production_local_env_file = front_root / '.env.production.local'
    env = _merge_env_layers(
        _parse_env_file(example_env_file),
        _parse_env_file(local_env_file),
        _parse_env_file(production_env_file),
        _parse_env_file(production_local_env_file),
        process_env or os.environ,
    )
    return env, example_env_file, local_env_file, production_env_file, production_local_env_file


def _load_agent_env(
    repo_root: Path = REPO_ROOT,
    agent_env_file: Optional[Path] = None,
    process_env: Optional[Mapping[str, str]] = None,
) -> tuple[dict[str, str], Path, Optional[Path]]:
    example_env_file = repo_root / 'detection_server_agent.env.example'
    selected_env_file = agent_env_file
    if selected_env_file is None:
        candidate = repo_root / 'detection_server_agent.env.local'
        if candidate.exists():
            selected_env_file = candidate
    env = _merge_env_layers(
        _parse_env_file(example_env_file),
        _parse_env_file(selected_env_file) if selected_env_file else {},
        process_env or os.environ,
    )
    return env, example_env_file, selected_env_file


def _read_database_path(backend_root: Path) -> Path:
    config_path = backend_root / 'config' / 'db_config.json'
    database_path = 'data/global_device_20250409.db'

    if config_path.exists() and config_path.is_file():
        try:
            data = json.loads(config_path.read_text(encoding='utf-8'))
            database_path = str(data.get('database_path') or database_path)
        except Exception:
            pass

    candidate = Path(database_path).expanduser()
    if not candidate.is_absolute():
        candidate = backend_root / candidate
    return candidate.resolve()


def _check_required_directory(report: SectionReport, label: str, path: Path) -> dict[str, Any]:
    state = _path_state(path, 'dir')
    if not state['exists']:
        report.add_error(
            f'{label} is missing: {path}',
            f'Create the directory before deployment: {path}',
        )
    elif not state['is_dir']:
        report.add_error(f'{label} is not a directory: {path}')
    elif not state['writable']:
        report.add_error(f'{label} is not writable: {path}')
    else:
        report.add_ok(f'{label} is ready: {path}')
    return state


def _check_optional_directory(report: SectionReport, label: str, path: Path) -> dict[str, Any]:
    state = _path_state(path, 'dir')
    if not state['exists']:
        report.add_warning(
            f'{label} is missing: {path}',
            f'Create it if your deployment expects this runtime boundary: {path}',
        )
    elif not state['is_dir']:
        report.add_error(f'{label} is not a directory: {path}')
    elif not state['writable']:
        report.add_warning(f'{label} exists but is not writable: {path}')
    else:
        report.add_ok(f'{label} is present: {path}')
    return state


def build_backend_runtime_status(
    backend_root: Path = BACKEND_ROOT,
    process_env: Optional[Mapping[str, str]] = None,
) -> dict[str, Any]:
    env, _base_env_file, _local_env_file = _load_backend_env(backend_root=backend_root, process_env=process_env)
    errors, warnings = validate_backend_startup_config(env)

    data_dir = (backend_root / 'data').resolve()
    artifacts_dir = (data_dir / 'artifacts').resolve()
    logs_dir = (backend_root / 'logs').resolve()
    backups_dir = (backend_root / 'db_backups').resolve()
    control_dir = (backend_root / 'control').resolve()

    celery_root_raw = (env.get('CELERY_FS_QUEUE_ROOT') or './data/celery').strip()
    celery_root = _resolve_path(celery_root_raw, backend_root)
    db_path = _read_database_path(backend_root)

    path_states = {
        'dataDir': _path_state(data_dir, 'dir'),
        'artifactDir': _path_state(artifacts_dir, 'dir'),
        'celeryQueueDir': _path_state(celery_root, 'dir'),
        'logDir': _path_state(logs_dir, 'dir'),
        'backupDir': _path_state(backups_dir, 'dir'),
        'controlDir': _path_state(control_dir, 'dir'),
        'databasePath': _path_state(db_path, 'file'),
    }

    for key in ('dataDir', 'artifactDir', 'celeryQueueDir', 'logDir', 'backupDir'):
        state = path_states[key]
        if not state['exists'] or not state['writable']:
            errors.append(f'{key} is not ready: {state["path"]}')

    if not path_states['databasePath']['exists']:
        warnings.append(f'databasePath does not exist yet: {path_states["databasePath"]["path"]}')

    callback_base = (env.get('DETECTION_WEBHOOK_BASE_URL') or '').strip()
    local_artifact = (env.get('DETECTION_LOCAL_ARTIFACT_PATH') or '').strip()
    mode = 'LOCAL_MODE' if local_artifact else 'REMOTE_HTTP_MODE'

    return {
        'status': 'error' if errors else ('warning' if warnings else 'ok'),
        'mode': mode,
        'callbackConfigured': bool(callback_base),
        'webhookSignatureRequired': (env.get('DETECTION_WEBHOOK_REQUIRE_SIGNATURE') or 'true').strip().lower() in {'1', 'true', 'yes', 'on'},
        'warnings': warnings,
        'errors': errors,
        'paths': path_states,
    }


def run_backend_preflight(
    backend_root: Path = BACKEND_ROOT,
    process_env: Optional[Mapping[str, str]] = None,
) -> SectionReport:
    report = SectionReport('backend')
    env, base_env_file, local_env_file = _load_backend_env(backend_root=backend_root, process_env=process_env)

    if base_env_file.exists():
        report.add_ok(f'backend base env loaded: {base_env_file}')
    else:
        # backend/.env is a local-only file (ignored by Git); backend/.env.local is the required one
        report.add_ok(f'backend base env not present (optional): {base_env_file}')

    if local_env_file.exists():
        report.add_ok(f'backend local config loaded: {local_env_file}')
    else:
        report.add_error(
            f'backend local config is missing: {local_env_file}',
            'Copy backend/.env.example to backend/.env.local and fill real values before deployment',
        )

    errors, warnings = validate_backend_startup_config(env)
    for item in errors:
        report.add_error(item, 'Update backend/.env.local and rerun scripts/preflight_check.py')
    for item in warnings:
        report.add_warning(item)

    if not (env.get('DETECTION_WEBHOOK_BASE_URL') or '').strip():
        report.add_warning(
            'DETECTION_WEBHOOK_BASE_URL is empty; remote detection callbacks are disabled and backend will rely on polling only',
            'Set DETECTION_WEBHOOK_BASE_URL when agent -> backend webhook callbacks are expected',
        )

    runtime_status = build_backend_runtime_status(backend_root=backend_root, process_env=process_env)
    for label, state in runtime_status['paths'].items():
        path = Path(state['path'])
        if label == 'controlDir':
            _check_optional_directory(report, 'backend control dir', path)
            continue
        if label == 'databasePath':
            if state['exists'] and state['writable']:
                report.add_ok(f'backend database path is writable: {path}')
            elif state['exists']:
                report.add_error(f'backend database file is not writable: {path}')
            else:
                report.add_warning(
                    f'backend database file does not exist yet: {path}',
                    'Import data or activate a snapshot before production traffic depends on this database',
                )
            continue

        readable_label = {
            'dataDir': 'backend data dir',
            'artifactDir': 'backend artifact dir',
            'celeryQueueDir': 'backend celery queue dir',
            'logDir': 'backend log dir',
            'backupDir': 'backend backup dir',
        }.get(label, label)
        _check_required_directory(report, readable_label, path)

    local_artifact = (env.get('DETECTION_LOCAL_ARTIFACT_PATH') or '').strip()
    if local_artifact:
        artifact_path = _resolve_path(local_artifact, backend_root)
        state = _path_state(artifact_path, 'file')
        if state['exists'] and state['is_file']:
            report.add_ok(f'local artifact file is present: {artifact_path}')
        else:
            report.add_error(
                f'DETECTION_LOCAL_ARTIFACT_PATH does not point to a readable file: {artifact_path}',
                'Fix the path or clear DETECTION_LOCAL_ARTIFACT_PATH to use remote agent mode',
            )

    report.details = runtime_status
    return report


def run_frontend_preflight(
    front_root: Path = FRONT_ROOT,
    process_env: Optional[Mapping[str, str]] = None,
    mode: str = 'local',
) -> SectionReport:
    report = SectionReport('frontend')
    env, example_env_file, local_env_file, production_env_file, production_local_env_file = _load_frontend_env(
        front_root=front_root,
        process_env=process_env,
    )

    if example_env_file.exists():
        report.add_ok(f'frontend template loaded: {example_env_file}')
    else:
        report.add_error(f'frontend template is missing: {example_env_file}')

    if local_env_file.exists():
        report.add_ok(f'frontend local config loaded: {local_env_file}')
    elif (env.get('VITE_API_BASE_URL') or '').strip() or (env.get('VITE_MAPBOX_TOKEN') or '').strip():
        report.add_warning(
            f'frontend local config file is missing: {local_env_file}',
            'The build will rely on process environment variables; keep front/.env.local for repeatable local deployments',
        )
    else:
        report.add_error(
            f'frontend local config is missing: {local_env_file}',
            'Copy front/.env.example to front/.env.local and fill runtime values before lint/build verification',
        )

    if production_local_env_file.exists():
        report.add_ok(f'frontend production local config loaded: {production_local_env_file}')
    elif production_env_file.exists():
        report.add_ok(f'frontend production config loaded: {production_env_file}')

    api_base = (env.get('VITE_API_BASE_URL') or '').strip()
    mapbox_token = (env.get('VITE_MAPBOX_TOKEN') or '').strip()

    if not api_base:
        if mode == 'deploy':
            report.add_error('VITE_API_BASE_URL is missing')
        else:
            report.add_warning(
                'VITE_API_BASE_URL is missing',
                'Local development can ignore this when the Vite /api proxy is used; set VITE_API_BASE_URL in front/.env.local for non-proxied or deployed builds',
            )
    else:
        report.add_ok(f'frontend API base is configured: {api_base}')

    if len(mapbox_token) < 20 or _is_placeholder(mapbox_token):
        report.add_error('VITE_MAPBOX_TOKEN must be replaced with a real public token')
    else:
        report.add_ok('frontend Mapbox token is present')

    report.details = {
        'apiBaseUrl': api_base,
        'mapboxTokenConfigured': bool(mapbox_token and not _is_placeholder(mapbox_token)),
    }
    return report


def build_agent_runtime_status(
    repo_root: Path = REPO_ROOT,
    agent_env_file: Optional[Path] = None,
    process_env: Optional[Mapping[str, str]] = None,
) -> dict[str, Any]:
    env, _example_env_file, _selected_env_file = _load_agent_env(
        repo_root=repo_root,
        agent_env_file=agent_env_file,
        process_env=process_env,
    )
    cfg = _load_config(env)
    errors, warnings = _validate_agent_config(cfg)

    probe_script = _resolve_path(cfg.probe_script_path, repo_root)
    artifact_dir = _resolve_path(cfg.encrypted_artifact_dir, repo_root)
    log_file = _resolve_path(cfg.log_file, repo_root)
    log_parent_state = _path_state(log_file, 'file')

    path_states = {
        'probeScript': _path_state(probe_script, 'file'),
        'artifactDir': _path_state(artifact_dir, 'dir'),
        'logFile': log_parent_state,
    }

    if not path_states['probeScript']['exists'] or not path_states['probeScript']['is_file']:
        errors.append(f'probeScript is not ready: {path_states["probeScript"]["path"]}')
    if not path_states['artifactDir']['exists'] or not path_states['artifactDir']['is_dir']:
        errors.append(f'artifactDir is not ready: {path_states["artifactDir"]["path"]}')
    elif not path_states['artifactDir']['writable']:
        errors.append(f'artifactDir is not writable: {path_states["artifactDir"]["path"]}')
    if not log_parent_state['parent_exists']:
        errors.append(f'logFile parent directory is missing: {log_parent_state["parent"]}')
    elif not log_parent_state['writable']:
        errors.append(f'logFile parent directory is not writable: {log_parent_state["parent"]}')

    return {
        'status': 'error' if errors else ('warning' if warnings else 'ok'),
        'warnings': warnings,
        'errors': errors,
        'paths': path_states,
        'callbackAllowlistConfigured': bool(cfg.callback_allowed_hosts),
        'callbackRequireToken': bool(cfg.callback_require_token),
        'tlsEnabled': bool(cfg.tls_cert_file and cfg.tls_key_file),
    }


def run_agent_preflight(
    repo_root: Path = REPO_ROOT,
    agent_env_file: Optional[Path] = None,
    process_env: Optional[Mapping[str, str]] = None,
) -> SectionReport:
    report = SectionReport('agent')
    env, example_env_file, selected_env_file = _load_agent_env(
        repo_root=repo_root,
        agent_env_file=agent_env_file,
        process_env=process_env,
    )

    if example_env_file.exists():
        report.add_ok(f'agent template loaded: {example_env_file}')
    else:
        report.add_error(f'agent template is missing: {example_env_file}')

    if agent_env_file is not None and not agent_env_file.exists():
        report.add_error(
            f'agent env file is missing: {agent_env_file}',
            'Pass the deployed EnvironmentFile path, for example --agent-env-file /etc/detection-agent/agent.env',
        )
        report.details = {'checkedEnvFile': str(agent_env_file)}
        return report

    if selected_env_file and selected_env_file.exists():
        report.add_ok(f'agent config loaded: {selected_env_file}')
    else:
        report.add_warning(
            'agent env file was not found locally',
            'Pass --agent-env-file /etc/detection-agent/agent.env for deployment validation, or create detection_server_agent.env.local for local runs',
        )
        report.details = {
            'checkedEnvFile': '',
            'skipped': True,
        }
        return report

    try:
        cfg = _load_config(env)
    except RuntimeError as exc:
        report.add_error(str(exc))
        report.details = {'checkedEnvFile': str(selected_env_file) if selected_env_file else ''}
        return report

    errors, warnings = _validate_agent_config(cfg)
    for item in errors:
        report.add_error(item, 'Update the agent EnvironmentFile and rerun scripts/preflight_check.py')
    for item in warnings:
        report.add_warning(item)

    if selected_env_file and not cfg.callback_allowed_hosts:
        report.add_error(
            'AGENT_CALLBACK_ALLOWED_HOSTS must be configured before deployment',
            'Set the real backend ingress hostname(s) in the agent EnvironmentFile',
        )

    runtime_status = build_agent_runtime_status(
        repo_root=repo_root,
        agent_env_file=selected_env_file,
        process_env=process_env,
    )
    path_states = runtime_status['paths']

    probe_script = Path(path_states['probeScript']['path'])
    if path_states['probeScript']['exists'] and path_states['probeScript']['is_file']:
        report.add_ok(f'agent probe script is ready: {probe_script}')
    else:
        report.add_error(f'agent probe script is missing: {probe_script}')

    artifact_dir = Path(path_states['artifactDir']['path'])
    if path_states['artifactDir']['exists'] and path_states['artifactDir']['writable']:
        report.add_ok(f'agent artifact dir is writable: {artifact_dir}')
    else:
        report.add_error(f'agent artifact dir is not ready: {artifact_dir}')

    log_parent = Path(path_states['logFile']['parent'])
    if path_states['logFile']['parent_exists'] and path_states['logFile']['writable']:
        report.add_ok(f'agent log directory is writable: {log_parent}')
    else:
        report.add_error(
            f'agent log directory is not writable: {log_parent}',
            'Create the log directory or update AGENT_LOG_FILE before starting the service',
        )

    report.details = runtime_status | {
        'checkedEnvFile': str(selected_env_file) if selected_env_file else '',
    }
    return report


def run_preflight_checks(
    repo_root: Path = REPO_ROOT,
    agent_env_file: Optional[Path] = None,
    process_env: Optional[Mapping[str, str]] = None,
    mode: str = 'local',
) -> list[SectionReport]:
    repo_root = repo_root.resolve()
    backend_root = repo_root / 'backend'
    front_root = repo_root / 'front'
    return [
        run_backend_preflight(backend_root=backend_root, process_env=process_env),
        run_frontend_preflight(front_root=front_root, process_env=process_env, mode=mode),
        run_agent_preflight(repo_root=repo_root, agent_env_file=agent_env_file, process_env=process_env),
    ]


def summarize_reports(reports: list[SectionReport]) -> dict[str, int]:
    return {
        'errors': sum(len(report.errors) for report in reports),
        'warnings': sum(len(report.warnings) for report in reports),
        'ok': sum(len(report.oks) for report in reports),
    }


def render_reports(reports: list[SectionReport]) -> str:
    lines: list[str] = []
    for report in reports:
        lines.append(f'[{report.name}]')
        if not report.items:
            lines.append('  OK no findings')
            continue

        for item in report.items:
            prefix = {
                'ok': 'OK',
                'warning': 'WARN',
                'error': 'ERROR',
            }.get(item.level, item.level.upper())
            lines.append(f'  {prefix} {item.message}')
            if item.hint:
                lines.append(f'      -> {item.hint}')
        lines.append('')

    summary = summarize_reports(reports)
    lines.append(
        f'Summary: {summary["errors"]} error(s), {summary["warnings"]} warning(s), {summary["ok"]} ok item(s)'
    )
    return '\n'.join(lines).strip()
