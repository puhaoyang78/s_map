#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import secrets
import logging
import base64
import hashlib
import hmac
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from functools import wraps
from flask import request, g
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from repositories import user_repository
from utils.response import error
from utils import error_codes
from utils.password_policy import validate_password_strength

ROLES = {'admin', 'user'}
STATUSES = {'active', 'disabled'}
_RUNTIME_SECRET = None
_logger = logging.getLogger('app.auth')


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat()


def _secret_key() -> str:
    env_secret = (os.environ.get('AUTH_SECRET') or '').strip()
    if len(env_secret) >= 32:
        return env_secret

    global _RUNTIME_SECRET
    if _RUNTIME_SECRET is None:
        _RUNTIME_SECRET = secrets.token_urlsafe(48)
        _logger.warning('AUTH_SECRET 未配置或长度不足，已使用进程内临时密钥（重启后旧 token 将失效）')
    return _RUNTIME_SECRET


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(_secret_key(), salt='my-map-app-auth')


def hash_password(password: str, salt: bytes = None) -> str:
    if salt is None:
        salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 120000)
    return f"{base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_b64, hash_b64 = stored.split('$', 1)
        salt = base64.b64decode(salt_b64.encode())
        expected = base64.b64decode(hash_b64.encode())
        actual = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 120000)
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def issue_token(user_row, issued_at: int = None) -> str:
    if issued_at is None:
        issued_at = int(time.time())
    payload = {
        'uid': user_row['id'],
        'username': user_row['username'],
        'role': user_row['role'],
        'iat': issued_at,
        'sv': int(user_row['session_version']) if 'session_version' in user_row.keys() else 1,
    }
    return _serializer().dumps(payload)


def decode_token(token: str, max_age: int = 60 * 60 * 24 * 7):
    return _serializer().loads(token, max_age=max_age)


def auth_cookie_name() -> str:
    return (os.environ.get('AUTH_COOKIE_NAME') or 'auth_token').strip() or 'auth_token'


def auth_cookie_max_age() -> int:
    raw = (os.environ.get('AUTH_COOKIE_MAX_AGE') or '').strip()
    if raw.isdigit():
        return int(raw)
    return 60 * 60 * 24 * 7


def auth_cookie_secure() -> bool:
    return (os.environ.get('AUTH_COOKIE_SECURE', 'false').strip().lower() == 'true')


def auth_cookie_samesite() -> str:
    value = (os.environ.get('AUTH_COOKIE_SAMESITE') or 'Lax').strip().capitalize()
    return value if value in {'Lax', 'Strict', 'None'} else 'Lax'


def csrf_cookie_name() -> str:
    return (os.environ.get('CSRF_COOKIE_NAME') or 'csrf_token').strip() or 'csrf_token'


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(24)


def ensure_csrf_cookie(resp):
    # Double-submit cookie: readable by JS so client can echo via X-CSRF-Token.
    current_token = request.cookies.get(csrf_cookie_name()) if request else None
    token = (current_token or '').strip() or generate_csrf_token()
    resp.set_cookie(
        csrf_cookie_name(),
        token,
        max_age=auth_cookie_max_age(),
        httponly=False,
        secure=auth_cookie_secure(),
        samesite=auth_cookie_samesite(),
        path='/',
    )


def set_auth_cookie(resp, token: str):
    resp.set_cookie(
        auth_cookie_name(),
        token,
        max_age=auth_cookie_max_age(),
        httponly=True,
        secure=auth_cookie_secure(),
        samesite=auth_cookie_samesite(),
        path='/',
    )
    ensure_csrf_cookie(resp)


def clear_auth_cookie(resp):
    resp.delete_cookie(
        auth_cookie_name(),
        path='/',
        samesite=auth_cookie_samesite(),
        secure=auth_cookie_secure(),
    )
    resp.delete_cookie(
        csrf_cookie_name(),
        path='/',
        samesite=auth_cookie_samesite(),
        secure=auth_cookie_secure(),
    )


def ensure_user_db_initialized():
    user_repository.init_db()
    username = os.environ.get('DEFAULT_ADMIN_USERNAME', 'admin')

    exists = user_repository.find_by_username(username)
    if exists:
        # 避免误操作把默认管理员禁用或降权，导致无法进入系统。
        if exists['status'] != 'active' or exists['role'] != 'admin':
            user_repository.update_user_meta(exists['id'], role='admin', status='active', now_iso=_now_iso())
        return

    password = (os.environ.get('DEFAULT_ADMIN_PASSWORD') or '').strip()
    if not password:
        raise RuntimeError('首次初始化管理员必须设置 DEFAULT_ADMIN_PASSWORD')
    else:
        ok, msg = validate_password_strength(password)
        if not ok:
            raise RuntimeError(f'DEFAULT_ADMIN_PASSWORD 不符合安全策略: {msg}')

    now = _now_iso()
    user_repository.create_user(
        username=username,
        password_hash=hash_password(password),
        role='admin',
        status='active',
        now_iso=now,
    )


# 固定假哈希（16 字节零盐 + 32 字节零摘要的 base64）：对不存在的用户执行一次
# 等额 PBKDF2 假校验并丢弃结果，消除“用户是否存在”的响应时序差异
_DUMMY_PASSWORD_HASH = 'AAAAAAAAAAAAAAAAAAAAAA==$AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA='


def login(username: str, password: str):
    row = user_repository.find_by_username(username)
    if not row:
        verify_password(password, _DUMMY_PASSWORD_HASH)
        return None, '用户名或密码错误'
    if not verify_password(password, row['password_hash']):
        return None, '用户名或密码错误'
    if row['status'] != 'active':
        return None, '用户名或密码错误'

    now_iso = _now_iso()
    issued_at = int(time.time())
    user_repository.update_login_time(row['id'], now_iso)
    token = issue_token(row, issued_at=issued_at)
    return token, None


def _token_hash(raw_token: str) -> str:
    # 带 secret 的摘要，避免数据库泄露后直接重放 token
    secret = _secret_key().encode('utf-8')
    data = (raw_token or '').encode('utf-8')
    return hmac.new(secret, data, hashlib.sha256).hexdigest()


def _reset_token_ttl_seconds() -> int:
    raw = (os.environ.get('AUTH_RESET_TOKEN_TTL_SECONDS') or '').strip()
    if raw.isdigit():
        return max(300, int(raw))
    return 600


def issue_password_reset_token(user_id: int) -> tuple[str, str]:
    token = secrets.token_urlsafe(32)
    token_hash = _token_hash(token)
    expires_at = (
        datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(seconds=_reset_token_ttl_seconds())
    ).isoformat()
    now_iso = _now_iso()
    user_repository.set_password_reset_token(user_id, token_hash, expires_at, now_iso)
    return token, expires_at


def use_password_reset_token(raw_token: str, new_password: str) -> tuple[bool, str]:
    ok, msg = validate_password_strength(new_password)
    if not ok:
        return False, msg

    token = (raw_token or '').strip()
    if not token:
        return False, '重置令牌不能为空'

    token_hash = _token_hash(token)
    row = user_repository.find_by_valid_reset_token(token_hash, _now_iso())
    if not row:
        return False, '重置令牌无效或已过期'

    user_repository.update_password(row['id'], hash_password(new_password), _now_iso())
    return True, ''


def _extract_token() -> str:
    auth = request.headers.get('Authorization', '')
    if auth.lower().startswith('bearer '):
        token = auth[7:].strip()
        if token:
            return token
    return (request.cookies.get(auth_cookie_name()) or '').strip()


def require_auth(roles=None):
    roles = set(roles or [])

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            token = _extract_token()
            if not token:
                return error('未登录或登录已过期', 401, error_codes.AUTH_UNAUTHORIZED)

            try:
                claims = decode_token(token)
            except SignatureExpired:
                return error('登录已过期，请重新登录', 401, error_codes.AUTH_TOKEN_EXPIRED)
            except BadSignature:
                return error('无效登录凭证', 401, error_codes.AUTH_INVALID_TOKEN)
            except Exception:
                return error('登录校验失败', 401, error_codes.AUTH_INVALID_TOKEN)

            user_row = user_repository.find_by_id(int(claims.get('uid', 0)))
            if not user_row:
                return error('用户不存在', 401, error_codes.AUTH_USER_NOT_FOUND)
            if user_row['status'] != 'active':
                return error('账号已禁用', 403, error_codes.AUTH_USER_DISABLED)

            token_sv = claims.get('sv')
            try:
                token_sv_num = int(token_sv) if token_sv is not None else None
            except Exception:
                token_sv_num = None

            current_sv = int(user_row['session_version']) if 'session_version' in user_row.keys() else 1
            if token_sv_num is None or token_sv_num != current_sv:
                return error('登录状态已失效，请重新登录', 401, error_codes.AUTH_TOKEN_REVOKED)

            g.current_user = {
                'id': user_row['id'],
                'username': user_row['username'],
                'role': user_row['role'],
                'status': user_row['status'],
                'forcePasswordChange': bool(int(user_row['force_password_change'])) if 'force_password_change' in user_row.keys() else False,
            }

            force_change_allowed_paths = {
                '/api/auth/change-password',
                '/api/auth/me',
                '/api/auth/logout',
            }
            if request.path not in force_change_allowed_paths and bool(g.current_user.get('forcePasswordChange')):
                return error('请先修改密码后再继续操作', 403, error_codes.AUTH_PASSWORD_CHANGE_REQUIRED)

            if roles and user_row['role'] not in roles:
                return error('权限不足', 403, error_codes.AUTH_FORBIDDEN)

            return func(*args, **kwargs)

        return wrapper

    return decorator
