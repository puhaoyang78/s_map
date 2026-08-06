#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import hmac
import csv
import os
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from flask import Blueprint, g, request
from utils.response import success, error
from utils import error_codes
from utils.auth import require_auth
from tasks.celery_app import enqueue_detection_job
from repositories import detection_job_repository as repo
from services.probe_runner_service import validate_probe_runtime_config, ProbeRunnerError
from services.import_pipeline_service import validate_import_runtime_config, ImportPipelineError
from utils.webhook_signing import verify_webhook_signature
from utils.logger import logger


detection_jobs_bp = Blueprint('detection_jobs', __name__, url_prefix='/api')

MAX_PROBE_REGIONS = 5
_COUNTRY_PRIORITY_RANK = {
    'JP': 0,
    'SG': 1,
    'MY': 1,
    'TH': 1,
    'VN': 1,
    'ID': 1,
    'PH': 1,
    'LA': 1,
    'KH': 1,
    'MM': 1,
    'BN': 1,
    'TL': 1,
    'IN': 2,
    'BD': 3,
    'PK': 3,
    'LK': 3,
    'NP': 3,
    'BT': 3,
}
_INDEX_WITH_GEO_PATH = Path(__file__).resolve().parent.parent / 'data' / 'index_with_geo_utf.csv'


def _split_probe_region(region_value: str) -> str:
    parts = [p.strip() for p in str(region_value or '').split(',')]
    if len(parts) != 3 or not all(parts):
        return ''
    return ','.join(parts)


def _normalize_probe_regions(raw_regions) -> list[str]:
    if not isinstance(raw_regions, list):
        return []
    normalized = []
    seen = set()
    for item in raw_regions:
        key = _split_probe_region(item)
        if not key or key in seen:
            continue
        normalized.append(key)
        seen.add(key)
    return normalized


def _extract_probe_regions_from_body(body: dict) -> list[str]:
    regions = _normalize_probe_regions(body.get('target_regions'))
    if regions:
        return regions

    probe_regions = _normalize_probe_regions(body.get('probe_regions'))
    if probe_regions:
        return probe_regions

    probe_region_list = (body.get('probe_region_list') or '').strip()
    if not probe_region_list:
        return []

    regions = []
    seen = set()
    for item in probe_region_list.split(';'):
        key = _split_probe_region(item)
        if not key or key in seen:
            continue
        regions.append(key)
        seen.add(key)
    return regions


@lru_cache(maxsize=1)
def _load_probe_regions_catalog() -> list[dict]:
    if not _INDEX_WITH_GEO_PATH.exists() or not _INDEX_WITH_GEO_PATH.is_file():
        return []

    rows = []
    seen = set()
    with _INDEX_WITH_GEO_PATH.open('r', encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        for raw in reader:
            code1 = (raw.get('code1') or '').strip()
            code2 = (raw.get('code2') or '').strip()
            code3 = (raw.get('code3') or '').strip()
            if not code1 or not code2 or not code3:
                continue

            value = f'{code1},{code2},{code3}'
            if value in seen:
                continue
            seen.add(value)

            country = (raw.get('Country') or '').strip()
            state = (raw.get('State') or '').strip()
            city = (raw.get('City') or '').strip()
            priority = _COUNTRY_PRIORITY_RANK.get(code1.upper(), 9)

            rows.append({
                'value': value,
                'code1': code1,
                'code2': code2,
                'code3': code3,
                'country': country,
                'state': state,
                'city': city,
                'display_name': f'{country} | {state} | {city}',
                'priority': priority,
            })

    rows.sort(
        key=lambda item: (
            item['priority'],
            item['code1'],
            item['code2'],
            item['code3'],
        )
    )
    return rows


def _get_valid_probe_region_set() -> set[str]:
    return {item.get('value') for item in _load_probe_regions_catalog() if item.get('value')}


def _get_webhook_token() -> str:
    return (os.environ.get('DETECTION_WEBHOOK_TOKEN') or '').strip()


def _webhook_signature_required() -> bool:
    return (os.environ.get('DETECTION_WEBHOOK_REQUIRE_SIGNATURE') or 'true').strip().lower() in {'1', 'true', 'yes', 'on'}


def _webhook_signature_ttl_seconds() -> int:
    raw = (os.environ.get('DETECTION_WEBHOOK_SIGNATURE_TTL_SECONDS') or '300').strip()
    try:
        ttl = int(raw)
    except ValueError:
        ttl = 300
    return max(1, ttl)


def _extract_bearer_token() -> str:
    auth = (request.headers.get('Authorization') or '').strip()
    if auth.lower().startswith('bearer '):
        return auth[7:].strip()
    return ''


def _verify_webhook_signature(payload_bytes: bytes, secret: str, timestamp: str, signature: str) -> tuple[bool, str]:
    return verify_webhook_signature(
        payload_bytes=payload_bytes,
        secret=secret,
        timestamp=timestamp,
        signature=signature,
        ttl_seconds=_webhook_signature_ttl_seconds(),
    )


def _normalize_artifact_url(url: str) -> str:
    if not url:
        return ''
    if url.startswith('http://') or url.startswith('https://'):
        return url

    base = (os.environ.get('DETECTION_AGENT_BASE_URL') or '').strip().rstrip('/')
    if not base:
        return url
    if url.startswith('/'):
        return f'{base}{url}'
    return f'{base}/{url}'


@detection_jobs_bp.route('/detection/jobs', methods=['POST'])
@require_auth({'admin'})
def create_detection_job():
    try:
        validate_probe_runtime_config()
        validate_import_runtime_config()
    except (ProbeRunnerError, ImportPipelineError) as e:
        return error(str(e), 400, error_codes.COMMON_INVALID_PARAM)

    # 当前先限制单活跃任务，后续可扩展队列并发策略
    active = repo.count_active_jobs()
    if active > 0:
        return error(
            '已有探测任务正在执行，请稍后再试',
            409,
            error_codes.COMMON_CONFLICT,
            activeJobs=active,
        )

    body = request.get_json(silent=True) or {}
    target_scope = (body.get('target_scope') or 'global').strip().lower()
    if target_scope not in {'global', 'selected'}:
        return error('target_scope 仅支持 global 或 selected', 400, error_codes.COMMON_INVALID_PARAM)

    target_regions = []
    if target_scope == 'selected':
        target_regions = _extract_probe_regions_from_body(body)
        if not target_regions:
            return error('请选择至少一个区域', 400, error_codes.COMMON_INVALID_PARAM)
        if len(target_regions) > MAX_PROBE_REGIONS:
            return error(f'最多仅支持选择 {MAX_PROBE_REGIONS} 个区域', 400, error_codes.COMMON_INVALID_PARAM)

        valid_regions = _get_valid_probe_region_set()
        invalid = [item for item in target_regions if item not in valid_regions]
        if invalid:
            return error(
                '存在无效区域参数，请从区域列表重新选择',
                400,
                error_codes.COMMON_INVALID_PARAM,
                invalidRegions=invalid,
            )

    # 活跃任务数检查与创建在 repository 层同一写事务内完成，避免并发创建竞态
    job, active = repo.create_job_if_idle(
        target_scope=target_scope,
        created_by_id=g.current_user['id'],
        created_by_username=g.current_user['username'],
        target_regions=target_regions,
    )
    if job is None:
        return error(
            '已有探测任务正在执行，请稍后再试',
            409,
            error_codes.COMMON_CONFLICT,
            activeJobs=active,
        )
    try:
        enqueue_detection_job(job['id'])
    except Exception as e:
        repo.update_job(job['id'], status='failed', progress=100, step='failed', message='任务投递失败', error_message=str(e))
        repo.add_event(job['id'], 'error', f'任务投递 Celery 失败: {e}')
        return error('任务创建成功但投递失败，请检查 Celery Worker 与队列配置', 500, error_codes.COMMON_INTERNAL_ERROR)
    return success(data={'job': job}, message='探测任务创建成功')


@detection_jobs_bp.route('/detection/regions', methods=['GET'])
@require_auth({'admin'})
def list_detection_regions():
    regions = _load_probe_regions_catalog()
    return success(
        data={
            'regions': regions,
            'total': len(regions),
            'maxSelections': MAX_PROBE_REGIONS,
        },
        message='获取探测区域列表成功',
    )


@detection_jobs_bp.route('/detection/jobs', methods=['GET'])
@require_auth({'admin'})
def list_detection_jobs():
    limit_raw = (request.args.get('limit') or '').strip()
    try:
        limit = int(limit_raw) if limit_raw else 100
    except ValueError:
        return error('limit 必须为整数', 400, error_codes.COMMON_INVALID_PARAM)
    limit = max(1, min(limit, 500))

    keyword = (request.args.get('keyword') or '').strip().lower()
    status = (request.args.get('status') or '').strip().lower()
    jobs = repo.list_jobs(limit=limit)

    if status:
        jobs = [j for j in jobs if (j.get('status') or '').strip().lower() == status]

    if keyword:
        def _match(j):
            haystack = [
                j.get('id') or '',
                j.get('target_scope') or '',
                j.get('status') or '',
                j.get('step') or '',
                j.get('message') or '',
                j.get('error_message') or '',
                j.get('created_by_username') or '',
            ]
            return keyword in ' '.join(haystack).lower()

        jobs = [j for j in jobs if _match(j)]

    return success(data={'jobs': jobs}, message='获取探测任务列表成功')


@detection_jobs_bp.route('/detection/jobs/history', methods=['DELETE', 'POST'])
@require_auth({'admin'})
def clear_detection_history():
    result = repo.clear_finished_jobs()
    return success(data=result, message='探测历史已清空')


@detection_jobs_bp.route('/detection/jobs/<job_id>', methods=['GET'])
@require_auth({'admin'})
def get_detection_job(job_id: str):
    job = repo.get_job(job_id)
    if not job:
        return error('任务不存在', 404, error_codes.COMMON_NOT_FOUND)
    events = repo.list_events(job_id, limit=500)
    return success(data={'job': job, 'events': events}, message='获取探测任务详情成功')


def _max_job_runtime_seconds() -> int:
    raw = (os.environ.get('DETECTION_JOB_MAX_RUNTIME_SECONDS') or '7200').strip()
    try:
        value = int(raw)
    except ValueError:
        value = 7200
    return max(60, value)


def _is_stale_running_job(job: dict) -> bool:
    """非终态任务长时间未更新（如 worker 在 artifact_ready/importing 阶段崩溃），视为卡死。"""
    raw = (job.get('updated_at') or '').strip()
    try:
        updated_at = datetime.fromisoformat(raw)
    except ValueError:
        return False
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    elapsed = (datetime.now(timezone.utc) - updated_at).total_seconds()
    return elapsed > _max_job_runtime_seconds()


@detection_jobs_bp.route('/detection/jobs/<job_id>/cancel', methods=['POST'])
@require_auth({'admin'})
def cancel_detection_job(job_id: str):
    job = repo.get_job(job_id)
    if not job:
        return error('任务不存在', 404, error_codes.COMMON_NOT_FOUND)

    if job['status'] in ('activated', 'failed', 'canceled'):
        return error('任务已结束，无法取消', 400, error_codes.COMMON_CONFLICT)

    if job['status'] in ('queued', 'dispatching'):
        repo.update_job(
            job_id,
            status='canceled',
            progress=100,
            step='canceled',
            message='任务已取消（尚未开始执行）',
            cancel_requested=1,
            finished_at=datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
        )
        repo.add_event(job_id, 'warning', '任务已取消（尚未开始执行）')
        return success(message='任务已取消')

    if _is_stale_running_job(job):
        forced = repo.force_cancel_job(
            job_id,
            message='任务已取消（任务长时间无进展，判定为卡死）',
            error_message=f'任务超过最大运行时长 {_max_job_runtime_seconds()}s 未更新，强制终结',
        )
        if forced:
            repo.add_event(job_id, 'warning', '任务超过最大运行时长未更新，已强制取消（卡死任务回收）')
            logger.warning('stale detection job force-canceled', extra={'job_id': job_id})
            return success(message='任务已强制取消（任务已超时卡死）')
        return error('任务已结束，无法取消', 400, error_codes.COMMON_CONFLICT)

    repo.request_cancel(job_id)
    repo.add_event(job_id, 'warning', '收到取消请求')
    repo.update_job(job_id, message='取消请求已提交')
    return success(message='取消请求已提交')


@detection_jobs_bp.route('/detection/jobs/<job_id>/callback', methods=['POST'])
def detection_job_callback(job_id: str):
    token = _get_webhook_token()
    if not token:
        logger.error('webhook callback rejected: DETECTION_WEBHOOK_TOKEN is not configured', extra={'job_id': job_id})
        return error('服务端未启用 webhook 回调令牌', 503, error_codes.COMMON_INTERNAL_ERROR)

    incoming = _extract_bearer_token() or (request.headers.get('X-Webhook-Token') or '').strip()
    if not incoming or not hmac.compare_digest(incoming, token):
        logger.warning(
            'webhook callback rejected: token mismatch',
            extra={'job_id': job_id, 'path': request.path, 'error_code': error_codes.AUTH_UNAUTHORIZED},
        )
        return error('未授权的 webhook 回调', 401, error_codes.AUTH_UNAUTHORIZED)

    payload_bytes = request.get_data(cache=True) or b'{}'
    if _webhook_signature_required():
        signature_ok, signature_reason = _verify_webhook_signature(
            payload_bytes=payload_bytes,
            secret=token,
            timestamp=(request.headers.get('X-Webhook-Timestamp') or '').strip(),
            signature=(request.headers.get('X-Webhook-Signature') or '').strip(),
        )
        if not signature_ok:
            logger.warning(
                'webhook callback rejected: signature verification failed (%s)',
                signature_reason,
                extra={'job_id': job_id, 'path': request.path, 'error_code': error_codes.AUTH_UNAUTHORIZED},
            )
            return error(f'webhook 签名校验失败: {signature_reason}', 401, error_codes.AUTH_UNAUTHORIZED)

    payload = request.get_json(silent=True) or {}
    remote_job_id = (payload.get('remote_job_id') or '').strip()
    remote_status = (payload.get('status') or '').strip().lower()
    remote_message = (payload.get('message') or '').strip()
    remote_error_message = (payload.get('error_message') or '').strip()
    artifact_download_url = _normalize_artifact_url((payload.get('artifact_download_url') or '').strip())
    event_id = (payload.get('event_id') or '').strip()
    occurred_at = (payload.get('occurred_at') or '').strip()

    if remote_status not in {'queued', 'running', 'succeeded', 'failed', 'canceled'}:
        logger.warning('webhook callback rejected: invalid remote status=%s', remote_status, extra={'job_id': job_id})
        return error('非法状态值', 400, error_codes.COMMON_INVALID_PARAM)

    apply_result = repo.apply_remote_callback(
        job_id=job_id,
        remote_job_id=remote_job_id,
        remote_status=remote_status,
        message=remote_message,
        error_message=remote_error_message,
        artifact_download_url=artifact_download_url,
        event_id=event_id,
        occurred_at=occurred_at,
    )

    if not apply_result.get('applied'):
        reason = apply_result.get('reason')
        logger.warning('webhook callback not applied: reason=%s', reason, extra={'job_id': job_id})
        if reason in {'duplicate_event', 'stale_event', 'job_finished', 'remote_terminal_immutable'}:
            return success(message='重复回调已忽略', data={'ignored': True})
        if reason == 'remote_job_id_mismatch':
            return error('remote_job_id 不匹配', 409, error_codes.COMMON_CONFLICT)
        if reason == 'job_not_found':
            return error('任务不存在', 404, error_codes.COMMON_NOT_FOUND)
        return error('回调写入失败', 500, error_codes.COMMON_INTERNAL_ERROR)

    job = repo.get_job(job_id)
    if not job:
        return error('任务不存在', 404, error_codes.COMMON_NOT_FOUND)

    if job['status'] in ('activated', 'failed', 'canceled'):
        return success(message='任务已结束，回调已记录')

    if remote_status in ('queued', 'running'):
        repo.update_job_if_active(job_id, status='running', progress=35, step='running', message=remote_message or '远端任务执行中')
    elif remote_status == 'succeeded':
        # 仅推进到 artifact_ready，实际导入激活仍由编排任务执行，保证流程单入口。
        repo.update_job_if_active(
            job_id,
            status='artifact_ready',
            progress=50,
            step='artifact_ready',
            message='收到远端完成回调，等待拉取产物',
            remote_artifact_path=artifact_download_url,
        )
    elif remote_status == 'failed':
        repo.update_job_if_active(
            job_id,
            status='failed',
            progress=100,
            step='failed',
            message='远端任务失败',
            error_message=(remote_error_message or '远端任务失败')[:1000],
        )
    elif remote_status == 'canceled':
        repo.update_job_if_active(job_id, status='canceled', progress=100, step='canceled', message='远端任务已取消')

    repo.add_event(job_id, 'info', f'收到远端 webhook 回调: status={remote_status}')
    return success(message='回调接收成功')
