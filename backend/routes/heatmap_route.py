#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
热力图相关路由
GET  /api/heatmap-data    - 获取热力图数据（支持区域筛选）
GET  /api/refresh-heatmap - 强制刷新热力图数据
GET  /api/heatmap-status  - 获取预热状态
GET  /api/refresh-stats   - 刷新统计数据
GET  /api/cache-version   - 获取当前缓存版本
POST /api/clear-cache     - 手动清除缓存
"""

import time
import threading
import sys
import os

from flask import Blueprint, request
from utils.response import success, error
from utils.validators import is_valid_snapshot
from utils.logger import logger
from utils import error_codes
from utils.auth import require_auth

heatmap_bp = Blueprint('heatmap', __name__, url_prefix='/api')


def _self_restart_enabled() -> bool:
    return (os.environ.get('SELF_RESTART_ENABLED', 'false').strip().lower() == 'true')


@heatmap_bp.route('/heatmap-data', methods=['GET'])
@require_auth()
def get_heatmap_data():
    try:
        min_lat   = request.args.get('minLat', type=float)
        max_lat   = request.args.get('maxLat', type=float)
        min_lng   = request.args.get('minLng', type=float)
        max_lng   = request.args.get('maxLng', type=float)
        min_count = request.args.get('minCount', 1, type=int)
        raw_snap  = request.args.get('snapshot', '').strip()
        snapshot  = raw_snap if is_valid_snapshot(raw_snap) else None

        from services.heatmap_service import get_heatmap
        city_counts = get_heatmap(
            min_lat=min_lat, max_lat=max_lat,
            min_lng=min_lng, max_lng=max_lng,
            min_count=min_count, snapshot=snapshot
        )

        return success(
            data=city_counts,
            message='热力图数据获取成功',
            total_regions=len(city_counts)
        ), 200, {'Cache-Control': 'private, max-age=3600'}

    except Exception as e:
        logger.exception('获取热力图数据失败')
        return error('获取热力图数据失败', 500, error_codes.COMMON_INTERNAL_ERROR)


@heatmap_bp.route('/refresh-heatmap', methods=['GET'])
@require_auth()
def refresh_heatmap():
    try:
        start_time = time.time()
        fast_mode  = request.args.get('fast', 'false').lower() == 'true'
        raw_snap   = request.args.get('snapshot', '').strip()
        snapshot   = raw_snap if is_valid_snapshot(raw_snap) else None

        from services.heatmap_service import get_cached_heatmap_full, get_db_signature_for_snapshot
        from services.cache_service import get_cache_version, heatmap_preload_status

        city_counts = get_cached_heatmap_full(snapshot, get_cache_version(), get_db_signature_for_snapshot(snapshot))

        if fast_mode:
            city_counts = dict(
                sorted(city_counts.items(), key=lambda x: x[1]['count'], reverse=True)[:1000]
            )

        elapsed = time.time() - start_time
        logger.info('热力图数据返回耗时: %.2fs (快速模式: %s)', elapsed, fast_mode)

        return success(
            data=city_counts,
            message='热力图数据已加载',
            cache_version=get_cache_version(),
            total_cities=len(city_counts),
            cached=heatmap_preload_status['ready'],
            fast_mode=fast_mode,
            elapsed=round(elapsed, 2)
        )

    except Exception as e:
        logger.exception('刷新热力图数据失败')
        return error(f'加载热力图数据失败: {str(e)}', 500, error_codes.COMMON_INTERNAL_ERROR)


@heatmap_bp.route('/heatmap-status', methods=['GET'])
@require_auth()
def heatmap_status():
    from services.cache_service import heatmap_preload_status
    return success(data=heatmap_preload_status, message='状态获取成功')


@heatmap_bp.route('/refresh-stats', methods=['GET'])
@require_auth()
def refresh_stats():
    try:
        raw_snap = request.args.get('snapshot', '').strip()
        snapshot = raw_snap if is_valid_snapshot(raw_snap) else None

        from repositories.device_repository import DeviceRepository
        from services.cache_service import get_cache_version
        repo = DeviceRepository(snapshot)
        stats = repo.get_stats()

        return success(
            data=stats,
            message='统计数据已刷新',
            cache_version=get_cache_version()
        )

    except Exception as e:
        logger.exception('刷新统计数据失败')
        return error(f'刷新统计数据失败: {str(e)}', 500, error_codes.COMMON_INTERNAL_ERROR)


@heatmap_bp.route('/cache-version', methods=['GET'])
@require_auth()
def get_cache_version_api():
    from services.cache_service import get_cache_version
    return success(data={'cache_version': get_cache_version()}, message='缓存版本获取成功')


@heatmap_bp.route('/clear-cache', methods=['POST'])
@require_auth({'admin'})
def clear_cache_api():
    try:
        from services.cache_service import bust_cache
        new_version = bust_cache()

        will_restart = False
        message = '缓存已清除'
        if _self_restart_enabled():
            def _restart():
                time.sleep(2)
                logger.info('正在重启服务器以确保所有数据最新...')
                try:
                    os.execv(sys.executable, ['python'] + sys.argv)
                except Exception as e:
                    logger.error('重启失败: %s', e)
                    os._exit(0)

            threading.Thread(target=_restart, daemon=True).start()
            will_restart = True
            message = '缓存已清除，服务器将在 2 秒后重启'
        else:
            logger.warning('SELF_RESTART_ENABLED=false，已跳过进程内自重启')

        return success(message=message, cache_version=new_version, will_restart=will_restart)

    except Exception as e:
        logger.exception('清除缓存失败')
        return error(f'清除缓存失败: {str(e)}', 500, error_codes.COMMON_INTERNAL_ERROR)
