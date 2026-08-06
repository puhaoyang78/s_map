#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日志配置模块
统一管理应用日志，替代散落的 print() 语句
"""

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

try:
    from flask import has_request_context, g, request
except Exception:  # pragma: no cover
    has_request_context = lambda: False
    g = None
    request = None


class RequestContextFilter(logging.Filter):
    """Inject common observability fields into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, 'request_id'):
            record.request_id = '-'
        if not hasattr(record, 'trace_id'):
            record.trace_id = '-'
        if not hasattr(record, 'user_id'):
            record.user_id = '-'
        if not hasattr(record, 'job_id'):
            record.job_id = '-'
        if not hasattr(record, 'path'):
            record.path = '-'
        if not hasattr(record, 'error_code'):
            record.error_code = '-'

        if has_request_context():
            record.request_id = getattr(g, 'request_id', record.request_id)
            record.trace_id = getattr(g, 'trace_id', record.trace_id)
            current_user = getattr(g, 'current_user', None) or {}
            record.user_id = current_user.get('id', record.user_id)
            record.path = getattr(request, 'path', record.path)

        return True


def setup_logging(app=None):
    """配置应用日志

    日志同时输出到控制台和文件（文件按大小轮转，最多保留 5 个备份）。
    日志级别通过环境变量 LOG_LEVEL 控制，默认 INFO。
    """
    log_level = os.environ.get('LOG_LEVEL', 'INFO').upper()
    numeric_level = getattr(logging, log_level, logging.INFO)

    fmt = logging.Formatter(
        '[%(asctime)s] %(levelname)s %(name)s '
        '[request_id=%(request_id)s trace_id=%(trace_id)s user_id=%(user_id)s '
        'job_id=%(job_id)s path=%(path)s error_code=%(error_code)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    ctx_filter = RequestContextFilter()

    # 根 logger
    root = logging.getLogger()
    root.setLevel(numeric_level)

    # 控制台 handler
    if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        ch = logging.StreamHandler()
        ch.setLevel(numeric_level)
        ch.setFormatter(fmt)
        ch.addFilter(ctx_filter)
        root.addHandler(ch)

    # 文件 handler（写到 backend/logs/app.log）
    try:
        log_dir = Path(__file__).resolve().parent.parent / 'logs'
        log_dir.mkdir(exist_ok=True)
        fh = RotatingFileHandler(
            log_dir / 'app.log',
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding='utf-8'
        )
        fh.setLevel(numeric_level)
        fh.setFormatter(fmt)
        fh.addFilter(ctx_filter)
        root.addHandler(fh)
    except Exception as e:
        logging.warning('无法初始化文件日志: %s', e)

    if app:
        app.logger.setLevel(numeric_level)

    return root


logger = logging.getLogger('app')


def log_with_context(level: int, message: str, **kwargs):
    """Log with explicit structured fields (job_id/error_code/etc.)."""
    logger.log(level, message, extra=kwargs)
