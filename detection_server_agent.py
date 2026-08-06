#!/usr/bin/env python3
"""Detection server agent service (async HTTP API, no SSH required)."""

from __future__ import annotations

import argparse
import copy
import hashlib
import hmac
import ipaddress
import json
import logging
import os
import sqlite3
import socket
import subprocess
import shutil
import threading
import time
import uuid
from dataclasses import dataclass
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional, Union
from collections.abc import Mapping
from urllib.parse import urlparse, urlunparse

import requests
from flask import Flask, jsonify, request, send_file


@dataclass
class AgentConfig:
    probe_script_path: str = "/home/ubuntu/ip_probe/probe.py"
    encrypted_artifact_dir: str = "/home/ubuntu/encrypt_res"
    encrypted_artifact_pattern: str = "*_enc.7z"
    probe_python_bin: str = "python3"
    probe_timeout_seconds: int = 0  # 0 = no timeout
    agent_token: str = ""
    tls_cert_file: str = ""
    tls_key_file: str = ""
    callback_timeout_seconds: int = 8
    callback_retries: int = 3
    callback_backoff_seconds: float = 1.2
    callback_allow_insecure_http: bool = False
    callback_allow_private_hosts: bool = False
    callback_require_token: bool = True
    callback_allowed_hosts: tuple[str, ...] = ()
    callback_allowed_ports: tuple[int, ...] = ()

    log_level: str = "INFO"
    log_file: str = "/var/log/detection-agent/agent.log"
    log_max_bytes: int = 10 * 1024 * 1024
    log_backup_count: int = 5
    max_concurrent_jobs: int = 4


# Path of the dotenv file that actually contributed variables (logged once the
# logger is configured in create_app()).
_AGENT_DOTENV_LOADED_PATH: Optional[str] = None


def load_agent_dotenv(env_file: Optional[Union[str, Path]] = None) -> None:
    global _AGENT_DOTENV_LOADED_PATH
    try:
        from dotenv import load_dotenv
    except ImportError:
        return

    base_dir = Path(__file__).resolve().parent
    target = Path(env_file).expanduser() if env_file else (base_dir / 'detection_server_agent.env.local')
    # override=False: variables already set by systemd EnvironmentFile or the
    # process environment win over the local dotenv file.
    if load_dotenv(target, override=False):
        _AGENT_DOTENV_LOADED_PATH = str(target)


def _load_config(env: Optional[Mapping[str, str]] = None) -> AgentConfig:
    source = os.environ if env is None else env
    callback_allowed_hosts = []
    for item in (source.get("AGENT_CALLBACK_ALLOWED_HOSTS") or "").split(","):
        host = item.strip().lower()
        if host:
            callback_allowed_hosts.append(host)

    callback_allowed_ports = []
    for item in (source.get("AGENT_CALLBACK_ALLOWED_PORTS") or "").split(","):
        raw = item.strip()
        if not raw:
            continue
        try:
            port = int(raw)
        except ValueError as exc:
            raise RuntimeError("AGENT_CALLBACK_ALLOWED_PORTS contains an invalid port") from exc
        if port < 1 or port > 65535:
            raise RuntimeError("AGENT_CALLBACK_ALLOWED_PORTS contains an out-of-range port")
        callback_allowed_ports.append(port)

    return AgentConfig(
        probe_script_path=(source.get("PROBE_SCRIPT_PATH") or "/home/ubuntu/ip_probe/probe.py").strip(),
        encrypted_artifact_dir=(source.get("ENCRYPTED_ARTIFACT_DIR") or "/home/ubuntu/encrypt_res").strip(),
        encrypted_artifact_pattern=(source.get("ENCRYPTED_ARTIFACT_PATTERN") or "*_enc.7z").strip(),
        probe_python_bin=(source.get("PROBE_PYTHON_BIN") or "python3").strip(),
        probe_timeout_seconds=int((source.get("PROBE_TIMEOUT_SECONDS") or "0").strip()),
        agent_token=(source.get("AGENT_TOKEN") or "").strip(),
        tls_cert_file=(source.get("AGENT_TLS_CERT_FILE") or "").strip(),
        tls_key_file=(source.get("AGENT_TLS_KEY_FILE") or "").strip(),
        callback_timeout_seconds=int((source.get("AGENT_CALLBACK_TIMEOUT_SECONDS") or "8").strip()),
        callback_retries=int((source.get("AGENT_CALLBACK_RETRIES") or "3").strip()),
        callback_backoff_seconds=float((source.get("AGENT_CALLBACK_BACKOFF_SECONDS") or "1.2").strip()),
        callback_allow_insecure_http=(source.get("AGENT_CALLBACK_ALLOW_INSECURE_HTTP") or "false").strip().lower() in {"1", "true", "yes", "on"},
        callback_allow_private_hosts=(source.get("AGENT_CALLBACK_ALLOW_PRIVATE_HOSTS") or "false").strip().lower() in {"1", "true", "yes", "on"},
        callback_require_token=(source.get("AGENT_CALLBACK_REQUIRE_TOKEN") or "true").strip().lower() in {"1", "true", "yes", "on"},
        callback_allowed_hosts=tuple(dict.fromkeys(callback_allowed_hosts)),
        callback_allowed_ports=tuple(dict.fromkeys(callback_allowed_ports)),
        log_level=(source.get("AGENT_LOG_LEVEL") or "INFO").strip().upper(),
        log_file=(source.get("AGENT_LOG_FILE") or "/var/log/detection-agent/agent.log").strip(),
        log_max_bytes=int((source.get("AGENT_LOG_MAX_BYTES") or str(10 * 1024 * 1024)).strip()),
        log_backup_count=int((source.get("AGENT_LOG_BACKUP_COUNT") or "5").strip()),
        max_concurrent_jobs=max(1, int((source.get("AGENT_MAX_CONCURRENT_JOBS") or "4").strip())),
    )


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "agent_jobs.db"
load_agent_dotenv()


class ClosingConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            return super().__exit__(exc_type, exc_val, exc_tb)
        finally:
            self.close()
_PROCESS_MAP: dict[str, subprocess.Popen] = {}
_PROCESS_LOCK = threading.Lock()
MAX_PROBE_REGIONS = 5
# Bounded semaphore initialized in create_app() from cfg.max_concurrent_jobs.
# None means "no limit" (module used without create_app, e.g. in tests).
_JOB_SLOTS: Optional[threading.BoundedSemaphore] = None

LOGGER = logging.getLogger("detection-agent")
_LOGGER_INITIALIZED = False


def _try_acquire_job_slot() -> bool:
    slots = _JOB_SLOTS
    if slots is None:
        return True
    return slots.acquire(blocking=False)


def _release_job_slot() -> None:
    slots = _JOB_SLOTS
    if slots is None:
        return
    try:
        slots.release()
    except ValueError:
        # Defensive: BoundedSemaphore raises when released more than acquired.
        LOGGER.warning("job slot release skipped: semaphore already at capacity")


class CallbackValidationError(ValueError):
    pass


def _normalize_probe_regions(raw_regions) -> list[str]:
    if not isinstance(raw_regions, list):
        return []

    normalized = []
    seen = set()
    for item in raw_regions:
        if not isinstance(item, str):
            continue
        parts = [p.strip() for p in item.split(',')]
        if len(parts) != 3 or not all(parts):
            continue

        key = ','.join(parts)
        if key in seen:
            continue

        seen.add(key)
        normalized.append(key)

    return normalized


def _parse_probe_region_list(raw: str) -> list[str]:
    text = (raw or '').strip()
    if not text:
        return []
    return _normalize_probe_regions([item.strip() for item in text.split(';') if item.strip()])


def _decode_probe_regions(raw: str) -> list[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except Exception:
        return []
    return _normalize_probe_regions(data)


def _setup_logger(cfg: AgentConfig) -> logging.Logger:
    global _LOGGER_INITIALIZED

    logger = logging.getLogger("detection-agent")
    if _LOGGER_INITIALIZED:
        return logger

    level = getattr(logging, cfg.log_level.upper(), logging.INFO)
    logger.setLevel(level)
    logger.propagate = False

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(threadName)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # stdout / journalctl
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(level)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    # file logger
    try:
        log_path = Path(cfg.log_file).expanduser().resolve()
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = RotatingFileHandler(
            filename=str(log_path),
            maxBytes=cfg.log_max_bytes,
            backupCount=cfg.log_backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        logger.info("logger initialized, level=%s, file=%s", cfg.log_level, log_path)
    except Exception as exc:
        logger.warning("file logger disabled: %s", exc)
        logger.info("logger initialized, level=%s, stdout only", cfg.log_level)

    _LOGGER_INITIALIZED = True
    return logger


def _is_placeholder_value(value: str) -> bool:
    raw = (value or "").strip().lower()
    if not raw:
        return True
    return raw.startswith("replace-with-")


def _validate_agent_config(cfg: AgentConfig) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    if len((cfg.agent_token or "").strip()) < 32 or _is_placeholder_value(cfg.agent_token):
        errors.append("AGENT_TOKEN must be set to a long random value before starting the agent")
    if not (cfg.probe_script_path or "").strip():
        errors.append("PROBE_SCRIPT_PATH is required")
    if not (cfg.encrypted_artifact_dir or "").strip():
        errors.append("ENCRYPTED_ARTIFACT_DIR is required")
    if not (cfg.probe_python_bin or "").strip():
        errors.append("PROBE_PYTHON_BIN is required")

    probe_script = Path(cfg.probe_script_path).expanduser()
    if cfg.probe_script_path and (not probe_script.exists() or not probe_script.is_file()):
        errors.append(f"PROBE_SCRIPT_PATH does not exist: {cfg.probe_script_path}")

    artifact_dir = Path(cfg.encrypted_artifact_dir).expanduser()
    if cfg.encrypted_artifact_dir and (not artifact_dir.exists() or not artifact_dir.is_dir()):
        errors.append(f"ENCRYPTED_ARTIFACT_DIR does not exist: {cfg.encrypted_artifact_dir}")
    elif cfg.encrypted_artifact_dir and not os.access(artifact_dir, os.W_OK):
        errors.append(f"ENCRYPTED_ARTIFACT_DIR is not writable: {cfg.encrypted_artifact_dir}")

    python_bin = (cfg.probe_python_bin or "").strip()
    if python_bin:
        python_path = Path(python_bin).expanduser()
        if python_path.name == python_bin and shutil.which(python_bin) is None:
            errors.append(f"PROBE_PYTHON_BIN is not available in PATH: {cfg.probe_python_bin}")
        elif python_path.name != python_bin and not python_path.exists():
            errors.append(f"PROBE_PYTHON_BIN does not exist: {cfg.probe_python_bin}")

    if bool(cfg.tls_cert_file) != bool(cfg.tls_key_file):
        errors.append("AGENT_TLS_CERT_FILE and AGENT_TLS_KEY_FILE must be configured together")

    for field_name, value in (
        ("AGENT_TLS_CERT_FILE", cfg.tls_cert_file),
        ("AGENT_TLS_KEY_FILE", cfg.tls_key_file),
    ):
        if value and not Path(value).expanduser().exists():
            errors.append(f"{field_name} does not exist: {value}")

    if cfg.callback_allow_insecure_http:
        warnings.append("AGENT_CALLBACK_ALLOW_INSECURE_HTTP=true weakens callback transport security and should stay off outside debugging")
    if cfg.callback_allow_private_hosts:
        warnings.append("AGENT_CALLBACK_ALLOW_PRIVATE_HOSTS=true allows callbacks to private or local addresses")
    if not cfg.callback_allowed_hosts:
        warnings.append("AGENT_CALLBACK_ALLOWED_HOSTS is empty; callback delivery will be rejected until an allowlist is configured")

    return errors, warnings


def get_agent_runtime_status(cfg: AgentConfig) -> dict:
    errors, warnings = _validate_agent_config(cfg)
    probe_script = Path(cfg.probe_script_path).expanduser().resolve()
    artifact_dir = Path(cfg.encrypted_artifact_dir).expanduser().resolve()
    log_file = Path(cfg.log_file).expanduser().resolve()
    return {
        "status": "error" if errors else ("warning" if warnings else "ok"),
        "warnings": warnings,
        "errors": errors,
        "tlsEnabled": bool(cfg.tls_cert_file and cfg.tls_key_file),
        "callbackAllowlistConfigured": bool(cfg.callback_allowed_hosts),
        "callbackRequireToken": bool(cfg.callback_require_token),
        "paths": {
            "probeScript": {
                "path": str(probe_script),
                "exists": probe_script.exists(),
            },
            "artifactDir": {
                "path": str(artifact_dir),
                "exists": artifact_dir.exists(),
                "writable": artifact_dir.exists() and os.access(artifact_dir, os.W_OK),
            },
            "logFile": {
                "path": str(log_file),
                "parentExists": log_file.parent.exists(),
                "parentWritable": log_file.parent.exists() and os.access(log_file.parent, os.W_OK),
            },
        },
    }


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def _host_matches_allowlist(host: str, allowed_hosts: tuple[str, ...]) -> bool:
    normalized_host = (host or "").strip().lower()
    for allowed in allowed_hosts:
        entry = (allowed or "").strip().lower()
        if not entry:
            continue
        if entry.startswith("*."):
            suffix = entry[1:]
            if normalized_host.endswith(suffix) and normalized_host != entry[2:]:
                return True
            continue
        if normalized_host == entry:
            return True
    return False


def _is_private_or_local_address(host: str) -> bool:
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return host.strip().lower() in {"localhost"}

    return bool(
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def _resolve_callback_addresses(host: str, port: int) -> set[str]:
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise CallbackValidationError("callback host cannot be resolved") from exc

    addresses = {item[4][0] for item in infos if item and item[4]}
    if not addresses:
        raise CallbackValidationError("callback host cannot be resolved")
    return addresses


def _normalize_callback_url(callback_url: str, cfg: AgentConfig) -> str:
    raw = (callback_url or "").strip()
    if not raw:
        return ""

    parsed = urlparse(raw)
    scheme = (parsed.scheme or "").lower()
    host = (parsed.hostname or "").strip().lower()
    try:
        port = parsed.port
    except ValueError as exc:
        raise CallbackValidationError("callback url uses an invalid port") from exc
    effective_port = port or (443 if scheme == "https" else 80 if scheme == "http" else None)

    if scheme not in {"http", "https"}:
        raise CallbackValidationError("callback url must use http or https")
    if scheme == "http" and not cfg.callback_allow_insecure_http:
        raise CallbackValidationError("callback url must use https")
    if not host:
        raise CallbackValidationError("callback url must include a host")
    if parsed.username or parsed.password:
        raise CallbackValidationError("callback url must not include userinfo")
    if parsed.fragment:
        raise CallbackValidationError("callback url must not include a fragment")
    if not cfg.callback_allowed_hosts:
        raise CallbackValidationError("callback host allowlist is not configured")
    if not _host_matches_allowlist(host, cfg.callback_allowed_hosts):
        raise CallbackValidationError("callback host is not in the allowlist")
    if effective_port is None:
        raise CallbackValidationError("callback url uses an invalid port")

    allowed_ports = set(cfg.callback_allowed_ports)
    allowed_ports.add(443)
    if cfg.callback_allow_insecure_http:
        allowed_ports.add(80)
    if effective_port not in allowed_ports:
        raise CallbackValidationError("callback port is not in the allowlist")

    if not cfg.callback_allow_private_hosts:
        if _is_private_or_local_address(host):
            raise CallbackValidationError("callback host resolves to a private or local address")
        for address in _resolve_callback_addresses(host, effective_port):
            if _is_private_or_local_address(address):
                raise CallbackValidationError("callback host resolves to a private or local address")

    normalized_netloc = host if port is None else f"{host}:{port}"
    normalized = parsed._replace(
        scheme=scheme,
        netloc=normalized_netloc,
        params="",
        fragment="",
    )
    return urlunparse(normalized)


def _serialize_callback_payload(payload: dict) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _build_callback_signature(secret: str, timestamp: str, payload_bytes: bytes) -> str:
    digest = hmac.new(
        secret.encode("utf-8"),
        timestamp.encode("utf-8") + b"." + payload_bytes,
        hashlib.sha256,
    ).hexdigest()
    return f"sha256={digest}"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, factory=ClosingConnection)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                message TEXT,
                artifact_path TEXT,
                callback_url TEXT,
                callback_token TEXT,
                target_scope TEXT,
                probe_regions_json TEXT,
                probe_region_list TEXT,
                error_message TEXT,
                cancel_requested INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                started_at TEXT,
                finished_at TEXT,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.commit()
        _ensure_column(conn, "jobs", "callback_url", "TEXT")
        _ensure_column(conn, "jobs", "callback_token", "TEXT")
        _ensure_column(conn, "jobs", "target_scope", "TEXT")
        _ensure_column(conn, "jobs", "probe_regions_json", "TEXT")
        _ensure_column(conn, "jobs", "probe_region_list", "TEXT")
        conn.commit()


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, column_type: str) -> None:
    cur = conn.execute(f"PRAGMA table_info({table})")
    existing = {row["name"] for row in cur.fetchall()}
    if column in existing:
        return
    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")


def _create_job(
    callback_url: str = "",
    callback_token: str = "",
    target_scope: str = "global",
    probe_regions: Optional[list[str]] = None,
    probe_region_list: str = "",
) -> str:
    job_id = uuid.uuid4().hex
    now = _now_iso()
    normalized_scope = "selected" if (target_scope or "").strip().lower() == "selected" else "global"
    normalized_regions = _normalize_probe_regions(probe_regions)
    normalized_region_list = (probe_region_list or '').strip()

    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO jobs (
                id, status, message, callback_url, callback_token,
                target_scope, probe_regions_json, probe_region_list,
                created_at, updated_at
            )
            VALUES (?, 'queued', 'job created', ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                callback_url,
                callback_token,
                normalized_scope,
                json.dumps(normalized_regions, ensure_ascii=False),
                normalized_region_list,
                now,
                now,
            ),
        )
        conn.commit()
    return job_id


def _create_job_or_none(**kwargs) -> Optional[str]:
    """Create a job row after acquiring a concurrency slot.

    Returns None when AGENT_MAX_CONCURRENT_JOBS is already reached. On success
    the slot is owned by the job thread (_run_job_supervised), which releases
    it when the run ends; if creation itself fails the slot is released here.
    """
    if not _try_acquire_job_slot():
        return None
    try:
        return _create_job(**kwargs)
    except Exception:
        _release_job_slot()
        raise


def _get_job(job_id: str) -> Optional[dict]:
    with _connect() as conn:
        cur = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def _update_job(job_id: str, **fields) -> None:
    if not fields:
        return
    fields["updated_at"] = _now_iso()
    keys = list(fields.keys())
    sql = f"UPDATE jobs SET {', '.join(k + ' = ?' for k in keys)} WHERE id = ?"
    vals = [fields[k] for k in keys] + [job_id]
    with _connect() as conn:
        conn.execute(sql, vals)
        conn.commit()


def _request_cancel(job_id: str) -> None:
    _update_job(job_id, cancel_requested=1, message="cancel requested")


def _notify_callback(
    cfg: AgentConfig,
    job_id: str,
    status: str,
    message: str = "",
    error_message: str = "",
    artifact_download_url: str = "",
) -> None:
    job = _get_job(job_id)
    if not job:
        LOGGER.warning("[job:%s] callback skipped: job missing", job_id)
        return

    callback_url = (job.get("callback_url") or "").strip()
    callback_token = (job.get("callback_token") or "").strip()
    if not callback_url:
        LOGGER.info("[job:%s] callback skipped: no callback_url", job_id)
        return

    payload = {
        "event_id": uuid.uuid4().hex,
        "remote_job_id": job_id,
        "status": status,
        "message": message,
        "error_message": error_message,
        "artifact_download_url": artifact_download_url,
        "occurred_at": _now_iso(),
    }

    payload_bytes = _serialize_callback_payload(payload)
    headers = {"Content-Type": "application/json"}
    if callback_token:
        headers["Authorization"] = f"Bearer {callback_token}"
        timestamp = str(int(time.time()))
        headers["X-Webhook-Timestamp"] = timestamp
        headers["X-Webhook-Signature"] = _build_callback_signature(callback_token, timestamp, payload_bytes)

    retries = max(0, int(cfg.callback_retries))
    backoff = max(0.1, float(cfg.callback_backoff_seconds))
    timeout_seconds = max(1, int(cfg.callback_timeout_seconds))

    LOGGER.info(
        "[job:%s] callback start | url=%s status=%s retries=%s timeout=%s token=%s",
        job_id,
        callback_url,
        status,
        retries,
        timeout_seconds,
        "present" if callback_token else "missing",
    )

    for attempt in range(retries + 1):
        try:
            resp = requests.post(
                callback_url,
                data=payload_bytes,
                headers=headers,
                timeout=timeout_seconds,
                allow_redirects=False,
            )
            if resp.status_code < 300:
                LOGGER.info(
                    "[job:%s] callback success | attempt=%s status_code=%s",
                    job_id,
                    attempt + 1,
                    resp.status_code,
                )
                return

            LOGGER.warning(
                "[job:%s] callback failed | attempt=%s status_code=%s body=%s",
                job_id,
                attempt + 1,
                resp.status_code,
                resp.text[:300],
            )
            if 400 <= resp.status_code < 500:
                # 4xx will never succeed on retry; record the failure and stop.
                LOGGER.error(
                    "[job:%s] callback failed permanently | status_code=%s body=%s",
                    job_id,
                    resp.status_code,
                    resp.text[:300],
                )
                return

        except Exception as exc:
            LOGGER.exception("[job:%s] callback request error on attempt %s: %s", job_id, attempt + 1, exc)

        if attempt < retries:
            sleep_seconds = backoff * (attempt + 1)
            LOGGER.info("[job:%s] callback retry sleep %.2fs", job_id, sleep_seconds)
            time.sleep(sleep_seconds)

    LOGGER.error("[job:%s] callback exhausted all retries", job_id)


def _snapshot_artifacts(cfg: AgentConfig) -> dict[str, float]:
    artifact_dir = Path(cfg.encrypted_artifact_dir).expanduser().resolve()
    if not artifact_dir.exists() or not artifact_dir.is_dir():
        raise RuntimeError(f"artifact dir not found: {artifact_dir}")

    snapshot: dict[str, float] = {}
    for path in artifact_dir.glob(cfg.encrypted_artifact_pattern):
        try:
            resolved = str(path.resolve())
            snapshot[resolved] = path.stat().st_mtime
        except FileNotFoundError:
            continue
    return snapshot


def _extract_artifact_path_from_stdout(stdout: str) -> Optional[Path]:
    """
    Optional enhancement:
    if probe script prints something like:
        ARTIFACT_PATH=/path/to/file.7z
    we can use it directly.
    """
    for line in stdout.splitlines():
        text = line.strip()
        if text.startswith("ARTIFACT_PATH="):
            candidate = text.split("=", 1)[1].strip()
            if candidate:
                return Path(candidate).expanduser().resolve()
    return None


def _is_within_artifact_dir(path: Path, artifact_dir: Path) -> bool:
    """True if resolved `path` lies inside resolved `artifact_dir`.

    Uses os.path.commonpath for Python 3.9 compatibility; returns False for
    mixed relative/absolute inputs or different Windows drives.
    """
    try:
        return os.path.commonpath([str(path), str(artifact_dir)]) == str(artifact_dir)
    except ValueError:
        return False


def _resolve_current_job_artifact(
    cfg: AgentConfig,
    before_snapshot: dict[str, float],
    job_started_ts: float,
    stdout: str,
) -> Path:
    artifact_dir = Path(cfg.encrypted_artifact_dir).expanduser().resolve()
    if not artifact_dir.exists() or not artifact_dir.is_dir():
        raise RuntimeError(f"artifact dir not found: {artifact_dir}")

    # 1) Highest priority: explicit path from script stdout
    explicit = _extract_artifact_path_from_stdout(stdout)
    if explicit:
        if not _is_within_artifact_dir(explicit, artifact_dir):
            raise RuntimeError(f"explicit artifact path is outside the artifact dir: {explicit}")
        if explicit.exists() and explicit.is_file():
            try:
                mtime = explicit.stat().st_mtime
            except FileNotFoundError:
                raise RuntimeError(f"explicit artifact disappeared: {explicit}")
            if mtime >= job_started_ts:
                return explicit
            raise RuntimeError(
                f"explicit artifact is older than current job start time: {explicit}"
            )

        raise RuntimeError(f"explicit artifact path not found: {explicit}")

    # 2) Fallback: only accept files created or updated after job start
    candidates = []
    for path in artifact_dir.glob(cfg.encrypted_artifact_pattern):
        try:
            resolved = str(path.resolve())
            stat = path.stat()
        except FileNotFoundError:
            continue

        current_mtime = stat.st_mtime
        previous_mtime = before_snapshot.get(resolved)

        is_new_file = previous_mtime is None
        is_updated_file = previous_mtime is not None and current_mtime > previous_mtime
        is_after_job_start = current_mtime >= job_started_ts

        if (is_new_file or is_updated_file) and is_after_job_start:
            candidates.append((current_mtime, path.resolve()))

    if not candidates:
        raise RuntimeError("no new artifact generated for current job")

    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


MAX_OUTPUT_TAIL_BYTES = 64 * 1024


def _tail_output(text: str, limit: int = MAX_OUTPUT_TAIL_BYTES) -> tuple[str, bool]:
    """Return (tail, truncated): only the trailing `limit` bytes of `text`.

    Probe stdout/stderr can be unbounded; only the tail is kept for logging
    and ARTIFACT_PATH parsing.
    """
    if not text:
        return "", False
    encoded = text.encode("utf-8", errors="replace")
    if len(encoded) <= limit:
        return text, False
    return encoded[-limit:].decode("utf-8", errors="ignore"), True


def _run_job(job_id: str, cfg: AgentConfig) -> None:
    script_path = Path(cfg.probe_script_path).expanduser().resolve()
    LOGGER.info("[job:%s] starting, script=%s", job_id, script_path)

    if not script_path.exists() or not script_path.is_file():
        err = f"probe script not found: {script_path}"
        LOGGER.error("[job:%s] %s", job_id, err)
        _update_job(job_id, status="failed", error_message=err, finished_at=_now_iso())
        _notify_callback(cfg, job_id, status="failed", message="probe script missing", error_message=err)
        return

    try:
        before_snapshot = _snapshot_artifacts(cfg)
    except Exception as exc:
        err = f"artifact snapshot failed before job start: {exc}"
        LOGGER.exception("[job:%s] %s", job_id, err)
        _update_job(job_id, status="failed", error_message=err, finished_at=_now_iso())
        _notify_callback(cfg, job_id, status="failed", message="artifact snapshot failed", error_message=err)
        return

    job_started_ts = time.time()
    _update_job(job_id, status="running", message="probe running", started_at=_now_iso())
    _notify_callback(cfg, job_id, status="running", message="probe running")

    job = _get_job(job_id) or {}
    target_scope = (job.get("target_scope") or "global").strip().lower()
    probe_regions = _decode_probe_regions((job.get("probe_regions_json") or "").strip())
    probe_region_list = (job.get("probe_region_list") or "").strip()

    command = [cfg.probe_python_bin, str(script_path)]
    if target_scope == "selected":
        if probe_region_list:
            command.extend(["--probe-region-list", probe_region_list])
        else:
            for region in probe_regions:
                command.extend(["--probe-region", region])

    LOGGER.info("[job:%s] running command: %s", job_id, command)

    # Re-check cancellation right before spawning: a cancel that arrived during
    # the snapshot/running-callback window must short-circuit before Popen.
    job = _get_job(job_id)
    if job and int(job.get("cancel_requested") or 0) == 1:
        LOGGER.info("[job:%s] cancel requested before process start; skipping spawn", job_id)
        _update_job(job_id, status="canceled", message="job canceled", finished_at=_now_iso())
        _notify_callback(cfg, job_id, status="canceled", message="job canceled")
        return

    proc = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        shell=False,
    )

    LOGGER.info("[job:%s] spawned process pid=%s", job_id, proc.pid)

    with _PROCESS_LOCK:
        _PROCESS_MAP[job_id] = proc

    # A cancel that raced the spawn/registration window must still terminate
    # the process; the post-communicate check below marks the job canceled.
    job = _get_job(job_id)
    if job and int(job.get("cancel_requested") or 0) == 1 and proc.poll() is None:
        LOGGER.info("[job:%s] cancel raced process spawn; terminating pid=%s", job_id, proc.pid)
        proc.terminate()

    try:
        if cfg.probe_timeout_seconds > 0:
            stdout, stderr = proc.communicate(timeout=cfg.probe_timeout_seconds)
        else:
            stdout, stderr = proc.communicate()

        stdout_tail, stdout_truncated = _tail_output(stdout or "")
        stderr_tail, stderr_truncated = _tail_output(stderr or "")

        if stdout_tail:
            if stdout_truncated:
                LOGGER.info("[job:%s][stdout] output truncated to last %d bytes", job_id, MAX_OUTPUT_TAIL_BYTES)
            for line in stdout_tail.splitlines():
                LOGGER.info("[job:%s][stdout] %s", job_id, line)

        if stderr_tail:
            if stderr_truncated:
                LOGGER.warning("[job:%s][stderr] output truncated to last %d bytes", job_id, MAX_OUTPUT_TAIL_BYTES)
            for line in stderr_tail.splitlines():
                LOGGER.warning("[job:%s][stderr] %s", job_id, line)

        job = _get_job(job_id)
        if job and int(job.get("cancel_requested") or 0) == 1:
            LOGGER.info("[job:%s] canceled by request", job_id)
            _update_job(job_id, status="canceled", message="job canceled", finished_at=_now_iso())
            _notify_callback(cfg, job_id, status="canceled", message="job canceled")
            return

        if proc.returncode != 0:
            err = f"probe script failed with exit code {proc.returncode}"
            LOGGER.error("[job:%s] %s", job_id, err)
            _update_job(
                job_id,
                status="failed",
                error_message=err,
                finished_at=_now_iso(),
            )
            _notify_callback(
                cfg,
                job_id,
                status="failed",
                message="probe failed",
                error_message=err,
            )
            return

        artifact = _resolve_current_job_artifact(
            cfg=cfg,
            before_snapshot=before_snapshot,
            job_started_ts=job_started_ts,
            stdout=stdout_tail,
        )

        LOGGER.info("[job:%s] succeeded, artifact=%s", job_id, artifact)
        _update_job(
            job_id,
            status="succeeded",
            message="artifact ready",
            artifact_path=str(artifact),
            finished_at=_now_iso(),
        )
        _notify_callback(
            cfg,
            job_id,
            status="succeeded",
            message="artifact ready",
            artifact_download_url=f"/api/v1/jobs/{job_id}/artifact",
        )

    except subprocess.TimeoutExpired:
        LOGGER.error("[job:%s] probe timeout", job_id)
        proc.kill()
        # Drain the pipes and reap the child after kill so the probe cannot
        # linger as a zombie or leave unread PIPE buffers behind.
        proc.communicate()
        _update_job(job_id, status="failed", error_message="probe timeout", finished_at=_now_iso())
        _notify_callback(cfg, job_id, status="failed", message="probe timeout", error_message="probe timeout")
    except Exception as exc:
        LOGGER.exception("[job:%s] unhandled exception: %s", job_id, exc)
        _update_job(job_id, status="failed", error_message=str(exc), finished_at=_now_iso())
        _notify_callback(cfg, job_id, status="failed", message="probe exception", error_message=str(exc))
    finally:
        with _PROCESS_LOCK:
            _PROCESS_MAP.pop(job_id, None)
        LOGGER.info("[job:%s] finished cleanup", job_id)


def _run_job_supervised(job_id: str, cfg: AgentConfig) -> None:
    """Job thread entry point.

    Sends the "queued" callback from the job thread (instead of the request
    thread) so POST /api/v1/jobs returns immediately even when the callback
    endpoint is slow; callback payload/signature/event_id semantics are
    unchanged. Releases the concurrency slot on every exit path.
    """
    try:
        _notify_callback(cfg, job_id, status="queued", message="job created")
        _run_job(job_id, cfg)
    finally:
        _release_job_slot()


def _bearer_token() -> str:
    auth = (request.headers.get("Authorization") or "").strip()
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return ""


def _build_ssl_context(cfg: AgentConfig):
    if not cfg.tls_cert_file and not cfg.tls_key_file:
        return None

    cert = Path(cfg.tls_cert_file).expanduser().resolve()
    key = Path(cfg.tls_key_file).expanduser().resolve()

    if not cert.exists() or not cert.is_file():
        raise RuntimeError("AGENT_TLS_CERT_FILE not found")
    if not key.exists() or not key.is_file():
        raise RuntimeError("AGENT_TLS_KEY_FILE not found")

    LOGGER.info("ssl context enabled | cert=%s key=%s", cert, key)
    return (str(cert), str(key))


def _fail_stale_jobs(cfg: AgentConfig) -> None:
    """Fail jobs left in a non-terminal state by a previous agent process.

    After an agent restart, queued/running rows in the sqlite DB would
    otherwise linger forever. Best effort: exactly one callback attempt per
    stale job; callback failures are logged and never block startup.
    """
    with _connect() as conn:
        cur = conn.execute(
            "SELECT id FROM jobs WHERE status NOT IN ('succeeded', 'failed', 'canceled')"
        )
        stale_ids = [row["id"] for row in cur.fetchall()]

    if not stale_ids:
        return

    for job_id in stale_ids:
        LOGGER.warning("[job:%s] marking stale job as failed after agent restart", job_id)
        _update_job(job_id, status="failed", error_message="agent restarted", finished_at=_now_iso())

    stale_cfg = copy.copy(cfg)
    stale_cfg.callback_retries = 0  # single best-effort attempt per stale job
    for job_id in stale_ids:
        try:
            _notify_callback(
                stale_cfg,
                job_id,
                status="failed",
                message="agent restarted",
                error_message="agent restarted",
            )
        except Exception as exc:
            LOGGER.warning("[job:%s] stale-job callback failed after restart: %s", job_id, exc)


def create_app(cfg: Optional[AgentConfig] = None) -> Flask:
    global LOGGER, _JOB_SLOTS

    cfg = cfg or _load_config()
    LOGGER = _setup_logger(cfg)
    if _AGENT_DOTENV_LOADED_PATH:
        LOGGER.info("loaded agent env file: %s", _AGENT_DOTENV_LOADED_PATH)
    startup_errors, startup_warnings = _validate_agent_config(cfg)
    for item in startup_warnings:
        LOGGER.warning("startup config warning: %s", item)
    if startup_errors:
        raise RuntimeError("agent startup config validation failed:\n- " + "\n- ".join(startup_errors))
    _JOB_SLOTS = threading.BoundedSemaphore(max(1, int(cfg.max_concurrent_jobs)))
    init_db()
    _fail_stale_jobs(cfg)

    app = Flask(__name__)
    LOGGER.info("app created")

    @app.before_request
    def _log_request_start():
        LOGGER.info(
            "request start | method=%s path=%s remote=%s ua=%s",
            request.method,
            request.path,
            request.remote_addr,
            request.headers.get("User-Agent", "-"),
        )

    @app.before_request
    def _auth_guard():
        if request.path == "/api/v1/health":
            return None

        if not cfg.agent_token:
            LOGGER.error("request auth failed: AGENT_TOKEN not configured")
            return jsonify({"error": "AGENT_TOKEN not configured"}), 500

        if not hmac.compare_digest(_bearer_token(), cfg.agent_token):
            LOGGER.warning("request auth failed | path=%s remote=%s", request.path, request.remote_addr)
            return jsonify({"error": "unauthorized"}), 401

        return None

    @app.after_request
    def _log_request_end(response):
        LOGGER.info(
            "request end   | method=%s path=%s status=%s remote=%s",
            request.method,
            request.path,
            response.status_code,
            request.remote_addr,
        )
        return response

    @app.get("/api/v1/health")
    def health():
        runtime_status = get_agent_runtime_status(cfg)
        status_code = 503 if runtime_status["status"] == "error" else 200
        if not (cfg.agent_token and hmac.compare_digest(_bearer_token(), cfg.agent_token)):
            # Unauthenticated probes only get the coarse status; runtime
            # details (paths, TLS, allowlist state) require the agent token.
            return jsonify({"status": runtime_status["status"]}), status_code
        payload = {
            "status": runtime_status["status"],
            "service": "detection-agent",
            "config": {
                "tlsEnabled": runtime_status["tlsEnabled"],
                "callbackAllowlistConfigured": runtime_status["callbackAllowlistConfigured"],
                "callbackRequireToken": runtime_status["callbackRequireToken"],
            },
            "paths": runtime_status["paths"],
            "warnings": runtime_status["warnings"],
            "errors": runtime_status["errors"],
        }
        return jsonify(payload), status_code

    @app.post("/api/v1/jobs")
    def start_job():
        body = request.get_json(silent=True) or {}
        if not isinstance(body, dict):
            LOGGER.warning("create job rejected: request body must be a JSON object")
            return jsonify({"error": "request body must be a JSON object"}), 400
        callback = body.get("callback") or {}
        if not isinstance(callback, dict):
            LOGGER.warning("create job rejected: callback must be an object")
            return jsonify({"error": "callback must be an object"}), 400

        # backward compatible: support both nested and flat callback fields
        callback_url = (body.get("callback_url") or callback.get("url") or "").strip()
        callback_token = (body.get("callback_token") or callback.get("token") or "").strip()
        target_scope = (body.get("target_scope") or "global").strip().lower()

        if target_scope not in {"global", "selected"}:
            LOGGER.warning("create job rejected: invalid target_scope=%s", target_scope)
            return jsonify({"error": "invalid target_scope"}), 400

        probe_regions = _normalize_probe_regions(body.get("probe_regions"))
        if not probe_regions:
            probe_regions = _normalize_probe_regions(body.get("target_regions"))
        probe_region_list = (body.get("probe_region_list") or "").strip()

        if target_scope == "selected":
            if not probe_regions and probe_region_list:
                probe_regions = _parse_probe_region_list(probe_region_list)

            if not probe_regions:
                LOGGER.warning("create job rejected: selected scope requires probe regions")
                return jsonify({"error": "selected scope requires probe regions"}), 400

            if len(probe_regions) > MAX_PROBE_REGIONS:
                LOGGER.warning("create job rejected: too many regions=%s", len(probe_regions))
                return jsonify({"error": f"maximum {MAX_PROBE_REGIONS} probe regions allowed"}), 400
        else:
            probe_regions = []
            probe_region_list = ""

        if callback_url and cfg.callback_require_token and not callback_token:
            LOGGER.warning("create job rejected: callback token required")
            return jsonify({"error": "callback token required"}), 400
        if callback_url:
            try:
                callback_url = _normalize_callback_url(callback_url, cfg)
            except CallbackValidationError as exc:
                LOGGER.warning("create job rejected: invalid callback url=%s reason=%s", callback_url, exc)
                return jsonify({"error": str(exc)}), 400

        LOGGER.info(
            "create job requested | scope=%s regions=%s callback_url=%s",
            target_scope,
            len(probe_regions),
            callback_url or "-",
        )

        job_id = _create_job_or_none(
            callback_url=callback_url,
            callback_token=callback_token,
            target_scope=target_scope,
            probe_regions=probe_regions,
            probe_region_list=probe_region_list,
        )
        if job_id is None:
            LOGGER.warning("create job rejected: max concurrent jobs reached")
            return jsonify({"error": "agent busy: max concurrent jobs reached"}), 409

        LOGGER.info("[job:%s] created", job_id)

        t = threading.Thread(
            target=_run_job_supervised,
            args=(job_id, cfg),
            daemon=True,
            name=f"job-{job_id[:8]}",
        )
        try:
            t.start()
        except Exception:
            _release_job_slot()
            LOGGER.exception("[job:%s] failed to start job thread", job_id)
            return jsonify({"error": "failed to start job worker"}), 500

        return jsonify({
            "job": {
                "id": job_id,
                "status": "queued",
                "target_scope": target_scope,
                "probe_region_list": probe_region_list,
                "probe_regions": probe_regions,
            }
        })

    @app.get("/api/v1/jobs/<job_id>")
    def get_job(job_id: str):
        LOGGER.info("[job:%s] status queried", job_id)
        job = _get_job(job_id)
        if not job:
            return jsonify({"error": "job not found"}), 404

        payload = {
            "job": {
                "id": job["id"],
                "status": job["status"],
                "message": job.get("message") or "",
                "error_message": job.get("error_message") or "",
                "artifact_path": job.get("artifact_path") or "",
                "cancel_requested": bool(job.get("cancel_requested") or 0),
                "target_scope": (job.get("target_scope") or "global"),
                "probe_region_list": (job.get("probe_region_list") or ""),
                "probe_regions": _decode_probe_regions((job.get("probe_regions_json") or "").strip()),
            }
        }

        if job["status"] == "succeeded":
            payload["job"]["artifact_download_url"] = f"/api/v1/jobs/{job_id}/artifact"

        return jsonify(payload)

    @app.post("/api/v1/jobs/<job_id>/cancel")
    def cancel_job(job_id: str):
        LOGGER.info("[job:%s] cancel requested", job_id)
        job = _get_job(job_id)
        if not job:
            return jsonify({"error": "job not found"}), 404

        if job["status"] in ("succeeded", "failed", "canceled"):
            LOGGER.info("[job:%s] cancel ignored: already finished status=%s", job_id, job["status"])
            return jsonify({"message": "job already finished"})

        _request_cancel(job_id)
        with _PROCESS_LOCK:
            proc = _PROCESS_MAP.get(job_id)

        if proc and proc.poll() is None:
            LOGGER.info("[job:%s] terminating subprocess pid=%s", job_id, proc.pid)
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                LOGGER.warning("[job:%s] subprocess ignored terminate; killing pid=%s", job_id, proc.pid)
                proc.kill()

        _notify_callback(cfg, job_id, status="canceled", message="cancel requested")
        return jsonify({"message": "cancel requested"})

    @app.get("/api/v1/jobs/<job_id>/artifact")
    def download_artifact(job_id: str):
        LOGGER.info("[job:%s] artifact download requested", job_id)
        job = _get_job(job_id)
        if not job:
            return jsonify({"error": "job not found"}), 404

        if job["status"] != "succeeded":
            return jsonify({"error": "artifact not ready"}), 409

        artifact_path = Path(job.get("artifact_path") or "")
        if not artifact_path.exists() or not artifact_path.is_file():
            LOGGER.error("[job:%s] artifact file missing: %s", job_id, artifact_path)
            return jsonify({"error": "artifact file missing"}), 404

        return send_file(str(artifact_path), as_attachment=True, download_name=artifact_path.name)

    return app


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Detection server agent service")
    parser.add_argument("command", choices=["serve"], help="Command to execute")
    parser.add_argument("--host", default=os.environ.get("AGENT_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("AGENT_PORT", "18080")))
    args = parser.parse_args(argv)

    if args.command != "serve":
        return 2

    cfg = _load_config()
    _setup_logger(cfg)

    LOGGER.info(
        "starting detection-agent | host=%s port=%s tls=%s callback_allowlist=%s",
        args.host,
        args.port,
        bool(cfg.tls_cert_file and cfg.tls_key_file),
        len(cfg.callback_allowed_hosts),
    )

    app = create_app(cfg)
    ssl_context = _build_ssl_context(cfg)

    app.run(
        host=args.host,
        port=args.port,
        debug=False,
        use_reloader=False,
        ssl_context=ssl_context,
        threaded=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(os.sys.argv[1:]))
