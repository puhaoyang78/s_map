#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests

from utils.logger import logger


class StarlinkServiceError(Exception):
    pass


_cache_lock = threading.Lock()
# 单飞标记：True 表示已有线程正在执行网络刷新（在 _cache_lock 保护下读写）
_refresh_in_progress = False
_cache_data = {
    'updated_at': None,
    'last_network_fetch_at': None,
    'last_failure_at': None,
    'last_error': None,
    'items': [],
    'by_id': {},
    'meta': {},
}

_DISK_CACHE_FILE = Path(__file__).resolve().parent.parent / 'data' / 'starlink_tle_cache.txt'


def _now_iso_z() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def _env_int(name: str, default: int, minimum: int = 1) -> int:
    import os

    raw = (os.environ.get(name) or '').strip()
    if not raw:
        return max(default, minimum)
    try:
        value = int(raw)
    except ValueError:
        logger.warning('%s 配置非法，已回退默认值 %s', name, default)
        return max(default, minimum)
    return max(value, minimum)


def _env_str(name: str, default: str) -> str:
    import os

    raw = (os.environ.get(name) or '').strip()
    return raw or default


def _request_text(url: str, timeout: int) -> str:
    resp = requests.get(url, timeout=timeout)
    if resp.status_code >= 300:
        raise StarlinkServiceError(f'请求失败: {url} -> {resp.status_code}')
    return resp.text


def _env_urls() -> List[str]:
    raw = _env_str(
        'STARLINK_SOURCE_URLS',
        'https://celestrak.org/NORAD/elements/gp.php?GROUP=starlink&FORMAT=tle,https://www.celestrak.com/NORAD/elements/gp.php?GROUP=starlink&FORMAT=tle',
    )
    urls = [u.strip() for u in raw.split(',') if u.strip()]
    return urls


def _write_disk_cache(tle_text: str):
    try:
        _DISK_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _DISK_CACHE_FILE.write_text(tle_text, encoding='utf-8')
    except Exception as e:
        logger.warning('写入 Starlink 本地缓存失败: %s', e)


def _read_disk_cache() -> Optional[str]:
    try:
        if _DISK_CACHE_FILE.exists() and _DISK_CACHE_FILE.is_file():
            text = _DISK_CACHE_FILE.read_text(encoding='utf-8')
            return text if text.strip() else None
    except Exception as e:
        logger.warning('读取 Starlink 本地缓存失败: %s', e)
    return None


def _safe_int(value) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _slugify(value: str) -> str:
    s = (value or '').strip().lower()
    if not s:
        return 'unknown'
    s = re.sub(r'\s+', '-', s)
    s = re.sub(r'[^a-z0-9\-_.]+', '-', s)
    s = re.sub(r'-{2,}', '-', s).strip('-')
    return s or 'unknown'


def _parse_tle_text(tle_text: str) -> List[dict]:
    lines = [line.strip() for line in (tle_text or '').splitlines() if line and line.strip()]
    parsed = []

    i = 0
    while i + 2 < len(lines):
        name = lines[i]
        line1 = lines[i + 1]
        line2 = lines[i + 2]

        # 三行一组：名称 + TLE line1 + TLE line2
        if not line1.startswith('1 ') or not line2.startswith('2 '):
            i += 1
            continue

        norad_cat_id = _safe_int(line1[2:7].strip())
        parsed.append(
            {
                'name': name.strip() or 'UNKNOWN',
                'object_name': name.strip() or 'UNKNOWN',
                'norad_cat_id': norad_cat_id,
                'tle': {
                    'line1': line1,
                    'line2': line2,
                },
            }
        )
        i += 3

    return parsed


def _to_visualization_items(parsed_tle: List[dict], fetched_at: str) -> List[dict]:
    items: List[dict] = []
    used_ids = set()

    for idx, item in enumerate(parsed_tle):
        norad_cat_id = item.get('norad_cat_id')
        if norad_cat_id is not None:
            satellite_id = f'norad:{norad_cat_id}'
        else:
            satellite_id = f"name:{_slugify(item.get('name') or 'unknown')}"

        # 防止极少数重复 id 冲突
        if satellite_id in used_ids:
            satellite_id = f'{satellite_id}:{idx}'
        used_ids.add(satellite_id)

        items.append(
            {
                'id': satellite_id,
                'name': item.get('name') or 'UNKNOWN',
                'object_name': item.get('object_name') or item.get('name') or 'UNKNOWN',
                'norad_cat_id': norad_cat_id,
                'metadata_source': 'celestrak',
                'orbit_source': 'celestrak',
                'metadata_fetched_at': fetched_at,
                'tle_fetched_at': fetched_at,
                # 位置由前端 satellite.js 实时推算，后端不做多源融合
                'position_computed_at': None,
                'latitude': None,
                'longitude': None,
                'height_km': None,
                'velocity_kms': None,
                'tle': {
                    'line1': (item.get('tle') or {}).get('line1') or '',
                    'line2': (item.get('tle') or {}).get('line2') or '',
                },
            }
        )

    items.sort(key=lambda x: (x.get('norad_cat_id') is None, x.get('norad_cat_id') or 0, x.get('name') or ''))
    return items


def _is_cache_fresh() -> bool:
    updated_at = _cache_data.get('updated_at')
    if not updated_at:
        return False
    ttl = _env_int('STARLINK_CACHE_TTL_SECONDS', 7200, minimum=600)
    now_ts = datetime.now(timezone.utc).timestamp()
    return (now_ts - updated_at) <= ttl


def _can_attempt_network_refresh(has_cache: bool) -> Tuple[bool, Optional[str]]:
    now_ts = datetime.now(timezone.utc).timestamp()
    min_refresh = _env_int('STARLINK_MIN_NETWORK_REFRESH_SECONDS', 7200, minimum=600)
    failure_cooldown = _env_int('STARLINK_FAILURE_COOLDOWN_SECONDS', 7200, minimum=60)

    last_fetch = _cache_data.get('last_network_fetch_at')
    if last_fetch:
        elapsed = now_ts - float(last_fetch)
        if elapsed < min_refresh:
            wait_seconds = int(max(min_refresh - elapsed, 1))
            return False, f'网络刷新限频中，请 {wait_seconds}s 后再试'

    # 有缓存可用时，失败后进入冷却窗口，避免被上游持续封禁。
    last_failure = _cache_data.get('last_failure_at')
    if has_cache and last_failure:
        elapsed = now_ts - float(last_failure)
        if elapsed < failure_cooldown:
            wait_seconds = int(max(failure_cooldown - elapsed, 1))
            return False, f'上游源失败冷却中，请 {wait_seconds}s 后再试'

    return True, None


def _refresh_cache() -> Tuple[List[dict], dict]:
    timeout = _env_int('STARLINK_HTTP_TIMEOUT_SECONDS', 20, minimum=3)
    max_items = _env_int('STARLINK_MAX_ITEMS', 3000, minimum=100)
    urls = _env_urls()

    tle_text = None
    source_url = ''
    request_errors: List[str] = []
    for url in urls:
        try:
            tle_text = _request_text(url, timeout=timeout)
            source_url = url
            break
        except Exception as e:
            request_errors.append(str(e))

    source = 'network'
    if not tle_text:
        cached = _read_disk_cache()
        if cached:
            tle_text = cached
            source_url = 'disk-cache'
            source = 'disk-cache'
        else:
            raise StarlinkServiceError(' ; '.join(request_errors) if request_errors else 'Starlink 数据源请求失败')

    fetched_at = _now_iso_z()
    parsed = _parse_tle_text(tle_text)

    if not parsed:
        raise StarlinkServiceError('CelesTrak TLE 返回为空或解析失败')

    if source == 'network':
        _write_disk_cache(tle_text)

    items = _to_visualization_items(parsed[:max_items], fetched_at=fetched_at)
    meta = {
        'source': source,
        'sourceUrl': source_url,
        'tleCount': len(parsed),
        'mergedCount': len(items),
        'tleFetchedAt': fetched_at,
        'metadataFetchedAt': fetched_at,
        'requestErrors': request_errors,
    }
    return items, meta


def get_starlink_visualization(force_refresh: bool = False) -> dict:
    global _refresh_in_progress

    with _cache_lock:
        has_cache = bool(_cache_data.get('items'))
        if not force_refresh and _is_cache_fresh() and _cache_data.get('items'):
            return {
                'items': _cache_data['items'],
                'meta': {**_cache_data.get('meta', {}), 'cacheHit': True, 'stale': False},
            }

        can_refresh, block_reason = _can_attempt_network_refresh(has_cache=has_cache)
        if not can_refresh and has_cache:
            return {
                'items': _cache_data['items'],
                'meta': {
                    **_cache_data.get('meta', {}),
                    'cacheHit': True,
                    'stale': not _is_cache_fresh(),
                    'networkRefreshBlocked': True,
                    'networkRefreshBlockReason': block_reason,
                },
            }

        if _refresh_in_progress and has_cache:
            # 已有线程正在刷新：直接返回旧缓存，不再被网络 IO 串行阻塞
            return {
                'items': _cache_data['items'],
                'meta': {
                    **_cache_data.get('meta', {}),
                    'cacheHit': True,
                    'stale': not _is_cache_fresh(),
                    'refreshInProgress': True,
                },
            }

        # 无缓存且已有刷新在进行时（仅冷启动并发），允许各自请求，避免无数据可返回
        is_refresh_owner = not _refresh_in_progress
        if is_refresh_owner:
            _refresh_in_progress = True

    # 网络请求移出锁外执行，其他线程在刷新期间返回旧缓存
    try:
        items, meta = _refresh_cache()
    except Exception as e:
        with _cache_lock:
            if is_refresh_owner:
                _refresh_in_progress = False
            _cache_data['last_failure_at'] = datetime.now(timezone.utc).timestamp()
            _cache_data['last_error'] = str(e)
            if _cache_data.get('items'):
                logger.warning('Starlink 刷新失败，回退到缓存数据: %s', e)
                return {
                    'items': _cache_data['items'],
                    'meta': {**_cache_data.get('meta', {}), 'cacheHit': True, 'stale': True, 'fallbackReason': str(e)},
                }
        raise

    with _cache_lock:
        if is_refresh_owner:
            _refresh_in_progress = False
        by_id = {item['id']: item for item in items}
        if meta.get('source') == 'network':
            _cache_data['last_network_fetch_at'] = datetime.now(timezone.utc).timestamp()
        _cache_data['last_error'] = None
        _cache_data['updated_at'] = datetime.now(timezone.utc).timestamp()
        _cache_data['items'] = items
        _cache_data['by_id'] = by_id
        _cache_data['meta'] = meta
        return {'items': items, 'meta': {**meta, 'cacheHit': False, 'stale': False}}


def get_starlink_satellite_detail(satellite_id: str, force_refresh: bool = False) -> dict:
    payload = get_starlink_visualization(force_refresh=force_refresh)
    by_id = {item['id']: item for item in payload['items']}

    sat = by_id.get(satellite_id)
    if sat:
        return sat

    sat_id = (satellite_id or '').strip().lower()
    for item in payload['items']:
        if str(item.get('norad_cat_id') or '').lower() == sat_id:
            return item
        if (item.get('name') or '').strip().lower() == sat_id:
            return item
        if (item.get('object_name') or '').strip().lower() == sat_id:
            return item

    raise StarlinkServiceError('未找到该卫星')
