#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快照管理路由
GET /api/snapshots - 列出所有可用历史快照
"""

import os
from flask import Blueprint
from utils.response import success, error
from utils.logger import logger
from utils import error_codes
from utils.auth import require_auth

snapshots_bp = Blueprint('snapshots', __name__, url_prefix='/api')


@snapshots_bp.route('/snapshots', methods=['GET'])
@require_auth()
def get_snapshots():
    try:
        from config import list_snapshots, get_database_path
        snapshots = list_snapshots()
        current_filename = os.path.basename(get_database_path())

        current_key = None
        for snap in snapshots:
            snap['isCurrent'] = (snap['filename'] == current_filename)
            if snap['isCurrent']:
                current_key = snap['key']

        return success(data={'snapshots': snapshots, 'current': current_key})

    except Exception as e:
        logger.exception('获取快照列表失败')
        return error(f'获取快照列表失败: {str(e)}', 500, error_codes.COMMON_INTERNAL_ERROR)


@snapshots_bp.route('/snapshots/<snapshot_key>', methods=['DELETE'])
@require_auth(['admin'])
def delete_snapshot_route(snapshot_key):
    try:
        from config import delete_snapshot
        removed = delete_snapshot(snapshot_key)
        logger.info('snapshot deleted: key=%s', snapshot_key)
        return success(data={'snapshot': removed}, message='快照已删除')
    except FileNotFoundError:
        return error('快照不存在或已被删除', 404, error_codes.COMMON_NOT_FOUND)
    except ValueError as exc:
        return error(str(exc), 400, error_codes.COMMON_INVALID_PARAM)
    except Exception as e:
        logger.exception('删除快照失败: key=%s', snapshot_key)
        return error(f'删除快照失败: {str(e)}', 500, error_codes.COMMON_INTERNAL_ERROR)
