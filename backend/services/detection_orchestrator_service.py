#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
from datetime import datetime, timezone
from utils.logger import logger, log_with_context
from repositories import detection_job_repository as repo
from repositories import runtime_state_repository as runtime_state_repo
from services.probe_runner_service import (
    run_global_probe,
    start_remote_probe,
    poll_remote_probe,
    cancel_remote_probe,
    ProbeRunnerError,
)
from services.artifact_transfer_service import (
    pull_artifact,
    ArtifactTransferError,
    validate_artifact_download_url,
)
from services.import_pipeline_service import import_and_activate, ImportPipelineError


def _now_iso() -> str:
    # 与 detection_job_repository 保持一致的 UTC 时间戳格式
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat()


def _log(job_id: str, level: str, message: str):
    repo.add_event(job_id, level, message)
    log_level = logger.info
    level_no = 20
    if level == 'error':
        log_level = logger.error
        level_no = 40
    elif level == 'warning':
        log_level = logger.warning
        level_no = 30

    log_level('[detection:%s] %s', job_id, message, extra={'job_id': job_id})
    log_with_context(level_no, f'detection event: {message}', job_id=job_id)


def _set(job_id: str, **fields):
    repo.update_job(job_id, **fields)


def _mark_failed(job_id: str, err: str):
    _set(
        job_id,
        status='failed',
        progress=100,
        step='failed',
        message='任务失败',
        error_message=err[:1000],
        finished_at=_now_iso(),
    )
    _log(job_id, 'error', err)


def _mark_canceled(job_id: str, msg: str = '任务已取消'):
    _set(
        job_id,
        status='canceled',
        progress=100,
        step='canceled',
        message=msg,
        finished_at=_now_iso(),
    )
    _log(job_id, 'warning', msg)


def _check_cancel(job_id: str) -> bool:
    return repo.is_cancel_requested(job_id)


def _env_int(name: str, default: int, minimum: int = 0) -> int:
    raw = (os.environ.get(name) or '').strip()
    if not raw:
        return max(default, minimum)
    try:
        value = int(raw)
    except ValueError:
        return max(default, minimum)
    return max(value, minimum)


def _normalize_artifact_url(remote_artifact_url: str) -> str:
    if not remote_artifact_url:
        return ''
    if remote_artifact_url.startswith('http://') or remote_artifact_url.startswith('https://'):
        return remote_artifact_url
    base = (os.environ.get('DETECTION_AGENT_BASE_URL') or '').strip().rstrip('/')
    if not base:
        return remote_artifact_url
    if remote_artifact_url.startswith('/'):
        return f'{base}{remote_artifact_url}'
    return f'{base}/{remote_artifact_url}'


def run_detection_job(job_id: str):
    lock_key = f'detection_job_lock:{job_id}'
    lock_owner = f'worker:{os.getpid()}'
    acquired, retry_after = runtime_state_repo.acquire_lock(lock_key, lock_owner, _env_int('DETECTION_JOB_LOCK_TTL_SECONDS', 3 * 3600, minimum=60))
    if not acquired:
        _log(job_id, 'warning', f'任务已在其他 Worker 执行中，忽略重复执行（retry_after={retry_after}s）')
        return

    try:
        job = repo.get_job(job_id)
        if not job:
            return

        # 若任务已被其他流程处理或已结束，直接跳过
        if job.get('status') not in ('queued', 'dispatching', 'running'):
            return

        if _check_cancel(job_id):
            _mark_canceled(job_id)
            return

        _set(job_id, status='dispatching', progress=5, step='dispatching', message='任务已分配到 Celery Worker')

        # LOCAL_MODE: 仅用于本地联调
        probe_result = None
        try:
            probe_result = run_global_probe()
        except ProbeRunnerError:
            probe_result = None

        local_artifact = (probe_result or {}).get('local_artifact_path')
        if local_artifact:
            _set(
                job_id,
                status='importing',
                progress=70,
                step='importing',
                message='LOCAL_MODE: 跳过远端拉取，正在导入激活',
                local_artifact_path=local_artifact,
            )
            _log(job_id, 'info', f'LOCAL_MODE: 使用本地产物 {local_artifact}')

            if _check_cancel(job_id):
                _mark_canceled(job_id, '任务已取消（导入前）')
                return

            import_result = import_and_activate(local_artifact)
            _set(
                job_id,
                status='activated',
                progress=100,
                step='activated',
                message='探测结果已导入并激活',
                snapshot_key=import_result['snapshot_key'],
                finished_at=_now_iso(),
            )
            _log(
                job_id,
                'info',
                f"激活成功: snapshot={import_result['snapshot_key']} rows={import_result['row_count']} cache={import_result['cache_version']}",
            )
            return

        # REMOTE_HTTP_MODE: 启动远端任务并轮询
        target_scope = (job.get('target_scope') or 'global').strip().lower()
        target_regions = job.get('target_regions') if isinstance(job.get('target_regions'), list) else []
        _set(job_id, status='running', progress=15, step='running', message='正在下发远端探测任务')
        start_result = start_remote_probe(job_id, target_scope=target_scope, target_regions=target_regions)
        remote_job_id = start_result['remote_job_id']
        _set(job_id, remote_job_id=remote_job_id, message='远端任务已启动（Webhook 回调优先，轮询兜底）')
        if target_scope == 'selected' and target_regions:
            _log(job_id, 'info', f'远端定向探测任务已创建: remote_job_id={remote_job_id}, regions={len(target_regions)}')
        else:
            _log(job_id, 'info', f'远端探测任务已创建: remote_job_id={remote_job_id}')

        poll_interval = max(3.0, float((os.environ.get('DETECTION_AGENT_POLL_INTERVAL_SECONDS') or '30').strip()))
        max_poll_failures = _env_int('DETECTION_AGENT_MAX_POLL_FAILURES', 5, minimum=1)
        max_runtime_seconds = _env_int('DETECTION_JOB_MAX_RUNTIME_SECONDS', 7200, minimum=60)
        started_ts = time.time()
        poll_failures = 0
        remote_artifact_url = ''

        while True:
            if time.time() - started_ts > max_runtime_seconds:
                raise ProbeRunnerError(f'任务执行超时（>{max_runtime_seconds} 秒）')

            if _check_cancel(job_id):
                try:
                    cancel_remote_probe(remote_job_id)
                except Exception as e:
                    _log(job_id, 'warning', f'远端取消请求失败(忽略): {e}')
                _mark_canceled(job_id)
                return

            latest = repo.get_job(job_id) or {}
            callback_status = (latest.get('remote_status') or '').strip().lower()
            callback_message = (latest.get('remote_message') or '').strip()
            callback_error = (latest.get('remote_error_message') or '').strip()
            callback_artifact_url = _normalize_artifact_url((latest.get('remote_artifact_url') or '').strip())

            remote_status = callback_status
            remote_message = callback_message or '远端任务执行中'

            if not remote_status:
                try:
                    status_result = poll_remote_probe(remote_job_id)
                    poll_failures = 0
                except ProbeRunnerError as e:
                    poll_failures += 1
                    _log(job_id, 'warning', f'轮询远端状态失败({poll_failures}/{max_poll_failures}): {e}')
                    if poll_failures >= max_poll_failures:
                        raise ProbeRunnerError(f'远端状态轮询连续失败，已达到上限: {e}') from e
                    time.sleep(poll_interval)
                    continue

                remote_status = status_result['status']
                remote_message = status_result.get('message') or '远端任务执行中'
                callback_artifact_url = _normalize_artifact_url(status_result.get('artifact_download_url') or '')

            if callback_artifact_url:
                try:
                    callback_artifact_url = validate_artifact_download_url(callback_artifact_url)
                except ArtifactTransferError as e:
                    raise ProbeRunnerError(f'远端产物地址校验失败: {e}') from e

            if remote_status in ('queued',):
                _set(job_id, status='running', progress=20, step='running', message='远端任务排队中')
            elif remote_status in ('running',):
                _set(job_id, status='running', progress=35, step='running', message=remote_message)
            elif remote_status in ('succeeded',):
                remote_artifact_url = callback_artifact_url
                if not remote_artifact_url:
                    # 回调丢失产物地址时尝试轮询兜底再取一次
                    status_result = poll_remote_probe(remote_job_id)
                    remote_artifact_url = _normalize_artifact_url(status_result.get('artifact_download_url') or '')
                if not remote_artifact_url:
                    raise ProbeRunnerError('远端任务成功但未返回 artifact_download_url')
                break
            elif remote_status in ('failed',):
                if callback_error:
                    raise ProbeRunnerError(callback_error)
                if not callback_status:
                    raise ProbeRunnerError((status_result.get('error_message') or '').strip() or '远端任务失败')
                raise ProbeRunnerError('远端任务失败')
            elif remote_status in ('canceled',):
                _mark_canceled(job_id, '远端任务已取消')
                return
            else:
                _log(job_id, 'warning', f'未知远端状态: {remote_status}')

            time.sleep(poll_interval)

        _set(
            job_id,
            status='artifact_ready',
            progress=50,
            step='artifact_ready',
            message='探测完成，正在拉取产物',
            remote_artifact_path=remote_artifact_url,
        )
        _log(job_id, 'info', f'远端探测完成，产物下载地址: {remote_artifact_url}')

        remote_artifact_url = validate_artifact_download_url(remote_artifact_url)
        local_artifact = pull_artifact(remote_artifact_url, job_id)
        _set(
            job_id,
            status='importing',
            progress=70,
            step='importing',
            message='产物已拉取，正在导入激活',
            local_artifact_path=local_artifact,
        )
        _log(job_id, 'info', f'产物拉取成功: {local_artifact}')

        if _check_cancel(job_id):
            _mark_canceled(job_id, '任务已取消（导入前）')
            return

        import_result = import_and_activate(local_artifact)
        _set(
            job_id,
            status='activated',
            progress=100,
            step='activated',
            message='探测结果已导入并激活',
            snapshot_key=import_result['snapshot_key'],
            finished_at=_now_iso(),
        )
        _log(
            job_id,
            'info',
            f"激活成功: snapshot={import_result['snapshot_key']} rows={import_result['row_count']} cache={import_result['cache_version']}",
        )

    except (ProbeRunnerError, ArtifactTransferError, ImportPipelineError) as e:
        _mark_failed(job_id, str(e))
    except Exception as e:
        _mark_failed(job_id, f'未预期异常: {e}')
    finally:
        runtime_state_repo.release_lock(lock_key, lock_owner)
