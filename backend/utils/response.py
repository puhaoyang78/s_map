#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一响应格式工具
所有 API 接口均通过此模块返回结构统一的 JSON 响应
"""

from flask import jsonify
from flask import g
from utils import error_codes


def _inject_request_id(payload: dict) -> dict:
    request_id = getattr(g, 'request_id', None)
    if request_id:
        payload['requestId'] = request_id
    return payload


def success(data=None, message='操作成功', **kwargs):
    """成功响应"""
    payload = {'success': True, 'message': message, 'code': error_codes.OK}
    if data is not None:
        payload['data'] = data
    payload.update(kwargs)
    return jsonify(_inject_request_id(payload))


def error(message='操作失败', http_status=400, biz_code=error_codes.COMMON_INTERNAL_ERROR, **kwargs):
    """错误响应"""
    payload = {'success': False, 'message': message, 'code': biz_code}
    payload.update(kwargs)
    return jsonify(_inject_request_id(payload)), http_status


def paginated(items, total, page, page_size, **kwargs):
    """分页响应（兼容旧结构 + 新统一结构）"""
    total_pages = (total + page_size - 1) // page_size if page_size else 1
    data = {
        'items': items,
        'pagination': {
            'total': total,
            'page': page,
            'pageSize': page_size,
            'totalPages': total_pages,
        }
    }
    payload = {
        'success': True,
        'message': '查询成功',
        'code': error_codes.OK,
        'data': data,

        # backward compatibility (legacy clients)
        'items': items,
        'total': total,
        'page': page,
        'pageSize': page_size,
        'totalPages': total_pages,
    }
    payload.update(kwargs)
    return jsonify(_inject_request_id(payload))
