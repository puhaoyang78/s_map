#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
设备相关路由
GET  /api/devices        - 分页查询设备列表
POST /api/devices/export - 导出设备数据 CSV
"""

import time
from flask import Blueprint, request, send_file
from utils.response import success, error, paginated
from utils.validators import sanitize_string, safe_int, is_valid_snapshot
from utils.logger import logger
from utils import error_codes
from utils.auth import require_auth
from services.device_service import ExportLimitExceededError

devices_bp = Blueprint('devices', __name__, url_prefix='/api')


@devices_bp.route('/devices', methods=['GET'])
@require_auth()
def get_devices():
    try:
        page      = safe_int(request.args.get('page', 1), 1, min_val=1)
        page_size = safe_int(request.args.get('pageSize', 10), 10, min_val=1, max_val=500)
        country   = sanitize_string(request.args.get('country', ''))
        city      = sanitize_string(request.args.get('city', ''))
        keyword   = sanitize_string(request.args.get('keyword', ''), max_len=200)
        raw_snap  = request.args.get('snapshot', '').strip()
        snapshot  = raw_snap if is_valid_snapshot(raw_snap) else None

        from services.device_service import get_devices
        result = get_devices(
            page=page, page_size=page_size,
            country=country, city=city,
            keyword=keyword, snapshot=snapshot
        )

        return paginated(
            items=result['items'],
            total=result['total'],
            page=page,
            page_size=page_size,
            stats=result['stats'],
            dbTimestamp=result.get('dbTimestamp', ''),
            countryStats=result.get('countryStats'),
            cityStats=result.get('cityStats'),
        ), 200, {'Cache-Control': 'no-cache, no-store, must-revalidate'}

    except FileNotFoundError as e:
        return error(str(e), 404, error_codes.COMMON_NOT_FOUND)
    except Exception as e:
        logger.exception('查询设备列表失败')
        return error('查询失败，请稍后重试', 500, error_codes.COMMON_INTERNAL_ERROR)


@devices_bp.route('/devices/export', methods=['POST'])
@require_auth()
def export_devices():
    try:
        data     = request.get_json(silent=True) or {}
        keyword  = sanitize_string(data.get('keyword', ''), max_len=200)
        raw_snap = (data.get('snapshot') or '').strip()
        snapshot = raw_snap if is_valid_snapshot(raw_snap) else None

        from services.device_service import export_devices_csv
        mem = export_devices_csv(keyword, snapshot)

        filename = f'终端设备数据_{time.strftime("%Y%m%d")}.csv'
        return send_file(
            mem,
            mimetype='text/csv',
            as_attachment=True,
            download_name=filename
        )

    except FileNotFoundError as e:
        return error(str(e), 404, error_codes.COMMON_NOT_FOUND)
    except ExportLimitExceededError as e:
        return error(str(e), 413, error_codes.COMMON_EXPORT_LIMIT_EXCEEDED)
    except Exception as e:
        logger.exception('导出设备数据失败')
        return error('导出失败，请稍后重试', 500, error_codes.COMMON_INTERNAL_ERROR)
