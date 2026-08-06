#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
输入校验工具
对公共入参进行统一校验，防止注入与异常输入
"""

import re
import ipaddress
from functools import wraps
from flask import request
from utils.response import error


# ---- 基础校验函数 ----

def is_valid_snapshot(value: str) -> bool:
    """快照 key 必须是 8 位数字日期，如 20250409"""
    return bool(value) and bool(re.match(r'^\d{8}$', value))


def safe_int(value, default: int, min_val: int = None, max_val: int = None) -> int:
    """安全转换整数，应用范围限制"""
    try:
        v = int(value)
        if min_val is not None:
            v = max(v, min_val)
        if max_val is not None:
            v = min(v, max_val)
        return v
    except (TypeError, ValueError):
        return default


def sanitize_string(value: str, max_len: int = 200) -> str:
    """截断超长字符串，去除首尾空白"""
    if not isinstance(value, str):
        return ''
    return value.strip()[:max_len]


def is_valid_ip_segment(value: str) -> bool:
    """简单验证 IP/CIDR 格式，如 14.1.72.0/23"""
    return bool(re.match(
        r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/\d{1,2}$',
        value or ''
    ))


def is_valid_host(value: str) -> bool:
    """验证主机名或 IPv4/IPv6 地址。"""
    v = (value or '').strip()
    if not v:
        return False

    # IP 地址
    try:
        ipaddress.ip_address(v)
        return True
    except ValueError:
        pass

    # DNS 主机名（兼容常见 hostname 规则）
    if len(v) > 253:
        return False
    if v.endswith('.'):
        v = v[:-1]
    labels = v.split('.')
    if not labels:
        return False
    label_re = re.compile(r'^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$')
    return all(label_re.match(label) for label in labels)


# ---- 请求体 JSON 字段校验 ----

def require_json_fields(*fields):
    """装饰器：要求请求 JSON 中必须包含指定字段"""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            data = request.get_json(silent=True) or {}
            missing = [field for field in fields if not data.get(field)]
            if missing:
                return error(f"缺少必要参数: {', '.join(missing)}", 400)
            return f(*args, **kwargs)
        return wrapper
    return decorator
