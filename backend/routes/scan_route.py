#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
漏洞扫描报告路由
POST /api/scan-report/find - 根据 IP 段查找对应的扫描报告文件
"""

import os
import re
from pathlib import Path
from flask import Blueprint, request
from utils.response import success, error
from utils.validators import is_valid_ip_segment
from utils.logger import logger
from utils import error_codes
from utils.auth import require_auth

scan_bp = Blueprint('scan', __name__, url_prefix='/api')

_SCAN_DIR = Path(__file__).resolve().parent.parent.parent / 'front' / 'public' / 'data' / 'vul_scan'


@scan_bp.route('/scan-report/find', methods=['POST'])
@require_auth()
def find_scan_report():
    data = request.get_json(silent=True) or {}
    ip_segment = (data.get('ipSegment') or '').strip()

    if not ip_segment:
        return error('缺少 IP 段参数', 400, error_codes.SCAN_MISSING_IP_SEGMENT)

    if not is_valid_ip_segment(ip_segment):
        return error('IP 段格式无效', 400, error_codes.SCAN_INVALID_IP_SEGMENT)

    if not _SCAN_DIR.exists():
        return error('扫描报告目录不存在', 404, error_codes.SCAN_REPORT_DIR_MISSING)

    # e.g. "14.1.72.0/23" -> "14_1_72_0_23"
    base = ip_segment.replace('.', '_').replace('/', '_')

    for filename in os.listdir(_SCAN_DIR):
        if not filename.endswith('.csv'):
            continue
        parts = filename[:-4].split('_')
        if len(parts) >= 5 and '_'.join(parts[:5]) == base:
            return success(data={
                'filename': filename,
                'path': f'/data/vul_scan/{filename}'
            })

    return error('未找到该网段的扫描报告', 404, error_codes.SCAN_REPORT_NOT_FOUND)
