#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Flask 应用入口（工厂模式）

职责：
- 创建 Flask 实例并完成扩展初始化
- 注册所有蓝图路由
- 执行启动任务（索引创建、热力图预热、遗留文件清理）
- 启动开发服务器（仅 __main__ 模式）

不应在此模块放置任何业务逻辑。
"""

import os
import sys
import threading
import uuid
import time
import hmac
import atexit
import subprocess
import re
from pathlib import Path
from urllib.parse import urlparse

from utils.env_loader import load_backend_dotenv

load_backend_dotenv()

from flask import Flask, request, g
from flask_cors import CORS
from tasks.celery_app import init_celery

from config import config as app_config, list_snapshots, get_database_path
from utils.logger import setup_logging, logger
from utils.auth import ensure_user_db_initialized, auth_cookie_name, csrf_cookie_name, ensure_csrf_cookie
from utils.exceptions import AppError
from utils.startup_validation import validate_backend_startup_config
from utils.deployment_checks import build_backend_runtime_status
from repositories import runtime_state_repository as runtime_state_repo


_CELERY_WORKER_PROCESS = None


def _should_autostart_celery_worker() -> bool:
    raw = (os.environ.get('AUTO_START_CELERY_WORKER') or 'true').strip().lower()
    return raw in {'1', 'true', 'yes', 'on'}


def _stop_celery_worker():
    global _CELERY_WORKER_PROCESS
    proc = _CELERY_WORKER_PROCESS
    if not proc:
        return
    if proc.poll() is not None:
        _CELERY_WORKER_PROCESS = None
        return

    try:
        proc.terminate()
        proc.wait(timeout=8)
        logger.info('已停止 Celery Worker 进程 (pid=%s)', proc.pid)
    except Exception:
        try:
            proc.kill()
            logger.warning('Celery Worker 进程已强制终止 (pid=%s)', proc.pid)
        except Exception:
            logger.warning('停止 Celery Worker 进程失败 (pid=%s)', proc.pid)
    finally:
        _CELERY_WORKER_PROCESS = None


def _start_celery_worker_with_app() -> None:
    global _CELERY_WORKER_PROCESS
    if _CELERY_WORKER_PROCESS and _CELERY_WORKER_PROCESS.poll() is None:
        logger.info('Celery Worker 已在运行 (pid=%s)', _CELERY_WORKER_PROCESS.pid)
        return

    backend_dir = Path(__file__).resolve().parent
    worker_cmd = [
        sys.executable,
        '-m',
        'celery',
        '-A',
        'tasks.celery_app:celery_app',
        'worker',
        '-l',
        'info',
        '-P',
        'solo',
    ]

    try:
        _CELERY_WORKER_PROCESS = subprocess.Popen(worker_cmd, cwd=str(backend_dir))
        atexit.register(_stop_celery_worker)
        logger.info('已自动启动 Celery Worker (pid=%s)', _CELERY_WORKER_PROCESS.pid)
    except Exception as e:
        logger.error('自动启动 Celery Worker 失败: %s', e)


# ---------------------------------------------------------------------------
# 应用工厂
# ---------------------------------------------------------------------------

def create_app() -> Flask:
    """创建并配置 Flask 应用"""
    app = Flask(__name__)

    # --- 日志 ---
    setup_logging(app)
    startup_errors, startup_warnings = validate_backend_startup_config()
    for item in startup_warnings:
        logger.warning('startup config warning: %s', item)
    if startup_errors:
        raise RuntimeError('backend startup config validation failed:\n- ' + '\n- '.join(startup_errors))

    # --- CORS ---
    # 生产环境通过 CORS_ORIGINS 环境变量指定允许的来源（逗号分隔）。
    # 本地开发默认放行 localhost/127.0.0.1 的任意端口，避免 Vite 端口变化导致跨域失败。
    raw_origins = (os.environ.get('CORS_ORIGINS') or '').strip()
    if raw_origins:
        origins_list = [o.strip() for o in raw_origins.split(',') if o.strip()]
    else:
        origins_list = [r'http://(127\.0\.0\.1|localhost)(:\d+)?']

    # 若显式配置了 localhost 或 127.0.0.1，自动补全对应同端口的等价来源。
    expanded = set(origins_list)
    for origin in list(origins_list):
        parsed = urlparse(origin)
        host = parsed.hostname
        if host not in {'127.0.0.1', 'localhost'}:
            continue
        port = f":{parsed.port}" if parsed.port else ''
        scheme = parsed.scheme or 'http'
        twin = 'localhost' if host == '127.0.0.1' else '127.0.0.1'
        expanded.add(f'{scheme}://{twin}{port}')

    CORS(
        app,
        resources={r"/api/*": {"origins": list(expanded)}},
        supports_credentials=True,
        allow_headers=['Content-Type', 'Authorization', 'X-Requested-With', 'X-CSRF-Token'],
        methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'],
    )

    # --- 注册蓝图 ---
    from routes.devices_route   import devices_bp
    from routes.heatmap_route   import heatmap_bp
    from routes.snapshots_route import snapshots_bp
    from routes.scan_route      import scan_bp
    from routes.auth_route      import auth_bp
    from routes.detection_jobs_route import detection_jobs_bp
    from routes.starlink_route import starlink_bp

    ensure_user_db_initialized()
    runtime_state_repo.init_db()
    init_celery()

    for bp in (devices_bp, heatmap_bp, snapshots_bp, scan_bp, auth_bp, detection_jobs_bp, starlink_bp):
        app.register_blueprint(bp)

    # --- 请求链路追踪与安全响应头 ---
    @app.before_request
    def _before_request():
        g.request_id = request.headers.get('X-Request-ID') or uuid.uuid4().hex[:16]
        g.trace_id = request.headers.get('X-Trace-ID') or g.request_id
        g.request_start = time.time()

        # CSRF transition policy (double-submit cookie), compatible with Bearer flows.
        if request.path.startswith('/api/') and request.method in {'POST', 'PUT', 'PATCH', 'DELETE'}:
            csrf_exempt_paths = {
                '/api/auth/login',
                '/api/auth/password-reset/confirm',
            }
            if request.path not in csrf_exempt_paths:
                has_auth_cookie = bool((request.cookies.get(auth_cookie_name()) or '').strip())
                has_bearer = (request.headers.get('Authorization') or '').lower().startswith('bearer ')

                # Only enforce CSRF when cookie-session is used.
                if has_auth_cookie and not has_bearer:
                    csrf_cookie = (request.cookies.get(csrf_cookie_name()) or '').strip()
                    csrf_header = (request.headers.get('X-CSRF-Token') or '').strip()
                    if not csrf_cookie or not csrf_header or not hmac.compare_digest(csrf_cookie, csrf_header):
                        from utils.response import error as err_resp
                        from utils import error_codes
                        return err_resp('CSRF 校验失败，请刷新页面后重试', 403, error_codes.AUTH_FORBIDDEN)

    @app.after_request
    def _after_request(resp):
        request_id = getattr(g, 'request_id', '')
        if request_id:
            resp.headers['X-Request-ID'] = request_id
        trace_id = getattr(g, 'trace_id', '')
        if trace_id:
            resp.headers['X-Trace-ID'] = trace_id

        resp.headers['X-Content-Type-Options'] = 'nosniff'
        resp.headers['X-Frame-Options'] = 'DENY'
        resp.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'

        started = getattr(g, 'request_start', None)
        if started is not None:
            elapsed_ms = (time.time() - started) * 1000
            logger.info(
                'request completed: %s %s -> %s (%.1f ms)',
                request.method,
                request.path,
                resp.status_code,
                elapsed_ms,
                extra={
                    'request_id': request_id,
                    'trace_id': trace_id,
                    'path': request.path,
                },
            )

        # Backward-compatible CSRF bootstrap for cookie-auth clients.
        if (request.cookies.get(auth_cookie_name()) or '').strip() and not (request.cookies.get(csrf_cookie_name()) or '').strip():
            ensure_csrf_cookie(resp)
        return resp

    @app.get('/api/health')
    def health_check():
        from utils.response import success as ok
        runtime_status = build_backend_runtime_status()
        response = ok(data={
            'status': runtime_status['status'],
            'service': 'my-map-app-backend',
            'mode': runtime_status['mode'],
            'callbackConfigured': runtime_status['callbackConfigured'],
            'webhookSignatureRequired': runtime_status['webhookSignatureRequired'],
            'warnings': runtime_status['warnings'],
            'errors': runtime_status['errors'],
            'paths': runtime_status['paths'],
        }, message='服务健康')
        if runtime_status['status'] == 'error':
            response.status_code = 503
        return response

    # --- 全局错误处理 ---
    @app.errorhandler(AppError)
    def app_error(e: AppError):
        from utils.response import error as err_resp
        logger.warning(
            'app error: %s',
            e.message,
            extra={'error_code': e.biz_code},
        )
        return err_resp(e.message, e.http_status, e.biz_code, details=e.details or {})

    @app.errorhandler(404)
    def not_found(e):
        from utils.response import error as err_resp
        from utils import error_codes
        return err_resp('接口不存在', 404, error_codes.COMMON_NOT_FOUND)

    @app.errorhandler(405)
    def method_not_allowed(e):
        from utils.response import error as err_resp
        from utils import error_codes
        return err_resp('不支持该请求方法', 405, error_codes.COMMON_INVALID_PARAM)

    @app.errorhandler(Exception)
    def internal_error(e):
        from utils.response import error as err_resp
        from utils import error_codes
        from werkzeug.exceptions import HTTPException
        if isinstance(e, HTTPException):
            # 未单独注册处理器的 HTTP 异常（如 400/413/414）透传其状态码与描述，不要一律转成 500
            return err_resp(e.description or '请求错误', e.code or 500, error_codes.COMMON_INVALID_PARAM)
        logger.exception('未捕获的服务器内部错误', extra={'error_code': error_codes.COMMON_INTERNAL_ERROR})
        return err_resp('服务器内部错误', 500, error_codes.COMMON_INTERNAL_ERROR)

    logger.info('Flask 应用创建完成，已注册蓝图: %s',
                [bp.name for bp in (devices_bp, heatmap_bp,
                                     snapshots_bp, scan_bp)])
    return app


# ---------------------------------------------------------------------------
# 启动任务
# ---------------------------------------------------------------------------

def _startup_tasks():
    """在后台线程中执行耗时启动工作，避免阻塞服务器启动"""
    try:
        logger.info('后台启动任务开始...')
        _cleanup_legacy_files()

        from repositories.device_repository import DeviceRepository
        index_mode = (os.environ.get('STARTUP_INDEX_MODE') or 'active').strip().lower()
        if index_mode == 'none':
            logger.info('已跳过启动索引初始化（STARTUP_INDEX_MODE=none）')
        elif index_mode == 'all':
            snapshots = list_snapshots()
            logger.info('检测到 %d 个快照数据库，开始初始化索引（all）...', len(snapshots))
            for snap in snapshots:
                DeviceRepository(snap['key']).ensure_indices()
            logger.info('所有快照数据库索引创建完成')
        else:
            DeviceRepository(None).ensure_indices()
            logger.info('当前激活快照索引初始化完成（STARTUP_INDEX_MODE=active）')

        # 预热当前快照热力图缓存
        preload_enabled = (os.environ.get('STARTUP_PRELOAD_HEATMAP') or 'false').strip().lower() in {'1', 'true', 'yes', 'on'}
        if preload_enabled:
            try:
                from services.heatmap_service import get_cached_heatmap_full
                from services.cache_service import get_cache_version
                logger.info('开始预热热力图缓存...')
                get_cached_heatmap_full(None, get_cache_version())
                logger.info('热力图缓存预热完成')
            except Exception as e:
                logger.warning('热力图缓存预热失败: %s', e)
        else:
            logger.info('已跳过启动热力图预热（STARTUP_PRELOAD_HEATMAP=false）')

        logger.info('后台启动任务全部完成')

    except Exception as e:
        logger.error('启动任务失败: %s', e)


def _cleanup_legacy_files():
    """清理历史遗留的根目录数据库文件和临时 ZIP 文件"""
    backend_dir = Path(__file__).resolve().parent
    cleaned = 0
    freed   = 0

    for f in backend_dir.glob('global_device_*.db'):
        try:
            sz = f.stat().st_size
            f.unlink()
            logger.info('已清理遗留数据库文件: %s (%.1f MB)', f.name, sz / 1024 / 1024)
            cleaned += 1
            freed += sz
        except Exception as e:
            logger.warning('清理遗留文件失败: %s - %s', f.name, e)

    for f in app_config.DATA_DIR.glob('temp_*.zip'):
        try:
            f.unlink()
            logger.info('已清理临时 ZIP 文件: %s', f.name)
        except Exception as e:
            logger.warning('清理临时文件失败: %s - %s', f.name, e)

    # 迁移遗留根目录 JSON 数据文件到 data/ 目录
    import shutil
    _legacy_json = {
        'fetch_records.json': app_config.DATA_DIR / 'fetch_records.json',
        'update_result.json': app_config.DATA_DIR / 'update_result.json',
    }
    for legacy_name, new_path in _legacy_json.items():
        legacy_path = backend_dir / legacy_name
        if legacy_path.exists():
            try:
                if not new_path.exists():
                    shutil.move(str(legacy_path), str(new_path))
                    logger.info('已迁移遗留文件 %s → data/', legacy_name)
                else:
                    legacy_path.unlink()
                    logger.info('已删除根目录重复文件: %s', legacy_name)
            except Exception as e:
                logger.warning('迁移遗留文件失败: %s - %s', legacy_name, e)

    pending = app_config.DATA_DIR / 'pending_cleanup.json'
    if pending.exists():
        pending.unlink(missing_ok=True)

    if cleaned:
        logger.info('启动清理完成，释放 %.1f MB 空间', freed / 1024 / 1024)
    else:
        logger.info('启动清理完成，无需清理')


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

app = create_app()

if __name__ == '__main__':
    # 启动后台初始化线程
    threading.Thread(target=_startup_tasks, daemon=True).start()

    if _should_autostart_celery_worker():
        _start_celery_worker_with_app()
    else:
        logger.info('AUTO_START_CELERY_WORKER 已关闭，请手动启动 Celery Worker')

    host  = os.environ.get('FLASK_HOST', '0.0.0.0')
    port  = int(os.environ.get('FLASK_PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'

    logger.info('Flask 开发服务器启动中 -> http://%s:%d  (debug=%s)', host, port, debug)
    logger.info('提示：热力图数据将在后台加载，首次访问可能需要片刻')
    app.run(debug=debug, host=host, port=port, use_reloader=False)
