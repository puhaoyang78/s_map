#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
热力图服务
封装热力图数据查询与缓存逻辑
"""

from functools import lru_cache
import os
from repositories.device_repository import DeviceRepository
from utils.logger import logger
from services.cache_service import heatmap_preload_status


def _env_int(name: str, default: int, minimum: int = 1) -> int:
    raw = (os.environ.get(name) or '').strip()
    if not raw:
        return max(default, minimum)
    try:
        value = int(raw)
    except ValueError:
        return max(default, minimum)
    return max(value, minimum)


def get_db_signature_for_snapshot(snapshot=None) -> str:
    """基于数据库文件路径+mtime+size 生成签名，用于缓存键自动失效。"""
    from config import get_db_path_for_snapshot

    db_path = get_db_path_for_snapshot(snapshot)
    if not db_path:
        return 'missing-db-path'
    try:
        stat = os.stat(db_path)
        return f'{db_path}:{stat.st_mtime_ns}:{stat.st_size}'
    except OSError:
        return f'{db_path}:missing'


@lru_cache(maxsize=32)
def get_cached_heatmap_data(min_count: int, snapshot, cache_version_key: int, db_signature: str):
    """全局热力图缓存（按城市聚合）。lru_cache 本身无 TTL，依赖缓存键中的 cache_version 与 db_signature 变化而失效。"""
    repo = DeviceRepository(snapshot)
    max_rows = _env_int('HEATMAP_GLOBAL_MAX_CITIES', 3000, minimum=100)
    return repo.get_heatmap_data(min_count=min_count, max_rows=max_rows)


@lru_cache(maxsize=64)
def get_cached_heatmap_data_for_region(
        min_lat: float, max_lat: float, min_lng: float, max_lng: float,
        min_count: int, snapshot, cache_version_key: int, db_signature: str):
    """区域热力图缓存（限定地理范围）"""
    repo = DeviceRepository(snapshot)
    max_rows = _env_int('HEATMAP_BBOX_MAX_CITIES', 1200, minimum=100)
    return repo.get_heatmap_data(
        min_count=min_count,
        bbox=(min_lat, max_lat, min_lng, max_lng),
        max_rows=max_rows,
    )


@lru_cache(maxsize=16)
def get_cached_heatmap_full(snapshot, cache_version_key: int, db_signature: str = ''):
    """完整热力图缓存，用于 /api/refresh-heatmap"""
    global heatmap_preload_status

    heatmap_preload_status['loading'] = True
    heatmap_preload_status['progress'] = 0

    try:
        repo = DeviceRepository(snapshot)
        max_rows = _env_int('HEATMAP_FULL_PRELOAD_MAX_CITIES', 5000, minimum=200)

        heatmap_preload_status['progress'] = 10
        logger.info('开始查询热力图数据...')

        city_counts = repo.get_heatmap_data(min_count=1, max_rows=max_rows)

        heatmap_preload_status['progress'] = 100
        heatmap_preload_status['ready'] = True
        heatmap_preload_status['loading'] = False
        heatmap_preload_status['error'] = None
        logger.info('热力图数据加载完成，共 %d 个城市', len(city_counts))
        return city_counts

    except Exception as e:
        heatmap_preload_status['loading'] = False
        heatmap_preload_status['error'] = str(e)
        logger.error('热力图数据加载失败: %s', e)
        raise


def get_heatmap(min_lat=None, max_lat=None, min_lng=None, max_lng=None,
                min_count: int = 1, snapshot=None):
    """入口：根据参数选择全局或区域热力图缓存"""
    from services.cache_service import get_cache_version
    ver = get_cache_version()
    db_signature = get_db_signature_for_snapshot(snapshot)

    if all(v is not None for v in [min_lat, max_lat, min_lng, max_lng]):
        return get_cached_heatmap_data_for_region(
            min_lat, max_lat, min_lng, max_lng, min_count, snapshot, ver, db_signature
        )
    return get_cached_heatmap_data(min_count, snapshot, ver, db_signature)
