#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from flask import Blueprint, request

from services.starlink_service import (
    StarlinkServiceError,
    get_starlink_satellite_detail,
    get_starlink_visualization,
)
from utils import error_codes
from utils.auth import require_auth
from utils.logger import logger
from utils.response import error, success


starlink_bp = Blueprint('starlink', __name__, url_prefix='/api')

@starlink_bp.route('/starlink/visualization', methods=['GET'])
@require_auth()
def get_starlink_visualization_api():
    q = (request.args.get('q') or '').strip().lower()
    force_refresh = (request.args.get('forceRefresh') or '').strip().lower() in {'1', 'true', 'yes'}

    try:
        payload = get_starlink_visualization(force_refresh=force_refresh)
        items = payload.get('items') or []

        if q:
            def _matches(item):
                haystack = [
                    item.get('id') or '',
                    item.get('name') or '',
                    item.get('object_name') or '',
                    str(item.get('norad_cat_id') or ''),
                ]
                return q in ' '.join(haystack).lower()

            items = [item for item in items if _matches(item)]

        return success(
            data={'items': items},
            message='Starlink 可视化数据获取成功',
            total=len(items),
            sourceMeta=payload.get('meta') or {},
        )
    except StarlinkServiceError as e:
        logger.warning('获取 Starlink 可视化数据失败: %s', e)
        return success(
            data={'items': []},
            message='Starlink 数据源暂不可用，已降级为空数据',
            total=0,
            sourceMeta={
                'source': 'degraded-empty',
                'cacheHit': False,
                'stale': True,
                'fallbackReason': str(e),
            },
        )
    except Exception as e:
        logger.exception('获取 Starlink 可视化数据异常')
        return error(f'获取 Starlink 数据失败: {e}', 500, error_codes.COMMON_INTERNAL_ERROR)


@starlink_bp.route('/starlink/visualization/<satellite_id>', methods=['GET'])
@require_auth()
def get_starlink_visualization_detail_api(satellite_id: str):
    force_refresh = (request.args.get('forceRefresh') or '').strip().lower() in {'1', 'true', 'yes'}
    try:
        detail = get_starlink_satellite_detail(satellite_id=satellite_id, force_refresh=force_refresh)
        return success(data={'item': detail}, message='Starlink 卫星详情获取成功')
    except StarlinkServiceError as e:
        msg = str(e)
        if '未找到' in msg:
            return error(msg, 404, error_codes.COMMON_NOT_FOUND)
        return error(msg, 503, error_codes.COMMON_INTERNAL_ERROR)
    except Exception as e:
        logger.exception('获取 Starlink 卫星详情异常')
        return error(f'获取卫星详情失败: {e}', 500, error_codes.COMMON_INTERNAL_ERROR)
