#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
缓存服务
统一管理 LRU 缓存的版本控制与清除操作
"""

import time
from utils.logger import logger


# 全局缓存版本号，变更时所有缓存失效
_cache_version = int(time.time())

# 热力图预热状态
heatmap_preload_status = {
    'loading': False,
    'ready': False,
    'progress': 0,
    'error': None
}


def get_cache_version() -> int:
    return _cache_version


def bust_cache():
    """使所有 LRU 缓存失效（通过更新版本号实现）"""
    global _cache_version
    old = _cache_version
    _cache_version = int(time.time())

    # 清除各模块中注册的缓存函数
    from services.device_service import get_cached_stats, get_cached_city_stats
    from services.heatmap_service import (
        get_cached_heatmap_data,
        get_cached_heatmap_data_for_region,
        get_cached_heatmap_full,
    )

    get_cached_stats.cache_clear()
    get_cached_city_stats.cache_clear()
    get_cached_heatmap_data.cache_clear()
    get_cached_heatmap_data_for_region.cache_clear()
    get_cached_heatmap_full.cache_clear()

    logger.info('缓存已清除，版本号: %d -> %d', old, _cache_version)
    return _cache_version
