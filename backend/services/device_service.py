#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
设备数据服务
封装设备列表查询、统计、导出等业务逻辑
"""

import csv
import io
import os
import re
from functools import lru_cache

from repositories.device_repository import DeviceRepository


def _get_db_timestamp(db_path: str) -> str:
    db_filename = os.path.basename(db_path)
    match = re.search(r'(\d{8})', db_filename)
    if match:
        d = match.group(1)
        try:
            return f'{d[:4]}-{d[4:6]}-{d[6:]}'
        except Exception:
            return d
    return ''


def _get_db_signature(db_path: str) -> str:
    """基于数据库文件路径+mtime+size 生成签名，用于缓存键自动失效。"""
    if not db_path:
        return 'missing-db-path'
    try:
        stat = os.stat(db_path)
        return f'{db_path}:{stat.st_mtime_ns}:{stat.st_size}'
    except OSError:
        return f'{db_path}:missing'


@lru_cache(maxsize=32)
def get_cached_stats(snapshot, cache_version_key, db_signature):
    """缓存设备统计，避免同一快照反复重复聚合。"""
    repo = DeviceRepository(snapshot)
    return repo.get_stats()


@lru_cache(maxsize=128)
def get_cached_city_stats(snapshot, country, cache_version_key, db_signature):
    """缓存按国家筛选后的城市统计，减少高频筛选时的重复查询。"""
    repo = DeviceRepository(snapshot)
    return repo.get_city_stats(country)


def get_devices(page: int, page_size: int, country: str, city: str,
                keyword: str, snapshot: str):
    """设备列表业务逻辑，返回分页结果与统计信息。"""
    from config import get_db_path_for_snapshot
    from services.cache_service import get_cache_version

    cache_version = get_cache_version()
    db_path = get_db_path_for_snapshot(snapshot)
    db_signature = _get_db_signature(db_path)

    repo = DeviceRepository(snapshot)
    total_count, items = repo.query_devices(
        page=page,
        page_size=page_size,
        country=country,
        city=city,
        keyword=keyword,
    )

    stats = get_cached_stats(snapshot, cache_version, db_signature)
    db_timestamp = _get_db_timestamp(db_path)

    result = {
      'items': items,
      'total': total_count,
      'stats': stats,
      'dbTimestamp': db_timestamp,
    }

    if page == 1:
        result['countryStats'] = stats.get('countryStats', {})
        result['cityStats'] = get_cached_city_stats(snapshot, country, cache_version, db_signature) if country else {}

    return result


class ExportLimitExceededError(Exception):
    """导出行数超过上限。"""


def _export_max_rows() -> int:
    """CSV 导出行数上限，默认 200000，可通过 DEVICE_EXPORT_MAX_ROWS 覆盖。"""
    raw = (os.environ.get('DEVICE_EXPORT_MAX_ROWS') or '').strip()
    try:
        value = int(raw)
    except ValueError:
        value = 0
    return value if value > 0 else 200000


def export_devices_csv(keyword: str, snapshot: str) -> io.BytesIO:
    """导出设备数据为 CSV 文件流。"""
    repo = DeviceRepository(snapshot)
    max_rows = _export_max_rows()
    # 多取 1 行用于判断是否超限；超限时明确报错，不做静默截断
    rows = repo.export_all(keyword, max_rows=max_rows + 1)
    if len(rows) > max_rows:
        raise ExportLimitExceededError(
            f'导出数据超过上限（{max_rows} 行），请增加筛选条件缩小范围后重试'
        )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'IP地址', '国家/地区', '省份/州', '城市', '纬度', '经度'])
    for row in rows:
        writer.writerow([
            row['id'],
            row['ip'],
            row['country'],
            row['region'],
            row['city'],
            row['lat'],
            row['lng'],
        ])

    mem = io.BytesIO()
    mem.write(output.getvalue().encode('utf-8-sig'))
    mem.seek(0)
    output.close()
    return mem
