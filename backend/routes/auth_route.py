#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import secrets
from datetime import datetime, timezone
from flask import Blueprint, request, g

from repositories import user_repository
from utils.auth import (
    require_auth, login, hash_password, ROLES, STATUSES,
    set_auth_cookie, clear_auth_cookie, issue_password_reset_token, use_password_reset_token,
)
from utils.password_policy import validate_password_strength
from utils.response import success, error
from utils import error_codes
from utils.logger import logger
from repositories import runtime_state_repository as runtime_state_repo

auth_bp = Blueprint('auth', __name__, url_prefix='/api')


def _int_env(name: str, default: int, min_value: int) -> int:
    raw = (os.environ.get(name) or '').strip()
    try:
        value = int(raw)
        return value if value >= min_value else default
    except Exception:
        return default


def _login_policy() -> dict:
    return {
        'window': _int_env('AUTH_LOGIN_WINDOW_SECONDS', 300, 1),
        'max_attempts': _int_env('AUTH_LOGIN_MAX_ATTEMPTS', 5, 1),
        'lock_seconds': _int_env('AUTH_LOGIN_LOCK_SECONDS', 600, 1),
    }


def _login_limit_key(username: str, ip: str) -> str:
    return f'{(ip or "unknown").strip()}::{(username or "").strip().lower()}'


def _client_ip() -> str:
    # Only trust REMOTE_ADDR by default; X-Forwarded-For is spoofable without proxy trust.
    return (request.remote_addr or '').strip() or 'unknown'


def _login_allowed(username: str, ip: str):
    key = _login_limit_key(username, ip)
    policy = _login_policy()
    return runtime_state_repo.check_login_allowed(key, policy['window'])


def _record_login_failure(username: str, ip: str):
    key = _login_limit_key(username, ip)
    policy = _login_policy()
    return runtime_state_repo.record_login_failure(
        key,
        policy['window'],
        policy['max_attempts'],
        policy['lock_seconds'],
    )


def _clear_login_failures(username: str, ip: str):
    key = _login_limit_key(username, ip)
    runtime_state_repo.clear_login_failures(key)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat()


def _should_expose_reset_token() -> bool:
    return (os.environ.get('AUTH_EXPOSE_RESET_TOKEN') or 'false').strip().lower() in ('1', 'true', 'yes', 'on')


def _build_reset_token_delivery(user_id: int, reset_token: str, expires_at: str) -> dict:
    data = {
        'expiresAt': expires_at,
        'userId': user_id,
    }
    if _should_expose_reset_token():
        data['resetToken'] = reset_token
        return data

    delivery_id = secrets.token_urlsafe(18)
    runtime_state_repo.save_password_reset_delivery(
        delivery_id=delivery_id,
        issuer_user_id=int(g.current_user['id']),
        target_user_id=int(user_id),
        reset_token=reset_token,
        reset_token_expires_at=expires_at,
    )
    data['deliveryId'] = delivery_id
    logger.info(
        '重置令牌投递单已生成',
        extra={
            'issuer_user_id': int(g.current_user['id']),
            'target_user_id': int(user_id),
            'delivery_id': delivery_id,
        },
    )
    return data


@auth_bp.route('/auth/login', methods=['POST'])
def auth_login():
    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''
    client_ip = _client_ip()

    if not username or not password:
        return error('用户名和密码不能为空', 400, error_codes.AUTH_LOGIN_INVALID_INPUT)

    allowed, retry_after = _login_allowed(username, client_ip)
    if not allowed:
        logger.warning(
            '登录限流命中',
            extra={'error_code': error_codes.AUTH_LOGIN_RATE_LIMITED},
        )
        return error(
            '登录失败次数过多，请稍后重试',
            429,
            error_codes.AUTH_LOGIN_RATE_LIMITED,
            retryAfterSeconds=retry_after,
        )

    token, err = login(username, password)
    if err:
        locked, lock_seconds = _record_login_failure(username, client_ip)
        logger.warning(
            '登录失败',
            extra={'error_code': error_codes.AUTH_LOGIN_FAILED},
        )
        if locked:
            return error(
                '登录失败次数过多，请稍后重试',
                429,
                error_codes.AUTH_LOGIN_RATE_LIMITED,
                retryAfterSeconds=lock_seconds,
            )
        return error(err, 401, error_codes.AUTH_LOGIN_FAILED)

    _clear_login_failures(username, client_ip)
    logger.info('登录成功')

    user = user_repository.find_by_username(username)
    resp = success(data={
        'token': token,
        'user': {
            'id': user['id'],
            'username': user['username'],
            'role': user['role'],
            'status': user['status'],
            'forcePasswordChange': bool(int(user['force_password_change'])) if 'force_password_change' in user.keys() else False,
        }
    }, message='登录成功')
    set_auth_cookie(resp, token)
    return resp


@auth_bp.route('/auth/logout', methods=['POST'])
def auth_logout():
    resp = success(message='已退出登录')
    clear_auth_cookie(resp)
    return resp


@auth_bp.route('/auth/me', methods=['GET'])
@require_auth()
def auth_me():
    return success(data={'user': g.current_user}, message='获取当前用户成功')


@auth_bp.route('/auth/change-password', methods=['POST'])
@require_auth()
def change_password():
    data = request.get_json(silent=True) or {}
    old_password = data.get('oldPassword') or ''
    new_password = data.get('newPassword') or ''

    if not old_password or not new_password:
        return error('旧密码和新密码不能为空', 400, error_codes.AUTH_CHANGE_PASSWORD_INVALID_INPUT)
    ok, msg = validate_password_strength(new_password)
    if not ok:
        return error(msg, 400, error_codes.AUTH_CHANGE_PASSWORD_INVALID_INPUT)

    row = user_repository.find_by_id(g.current_user['id'])
    from utils.auth import verify_password
    if not verify_password(old_password, row['password_hash']):
        return error('旧密码错误', 400, error_codes.AUTH_CHANGE_PASSWORD_INVALID_OLD)

    user_repository.update_password(g.current_user['id'], hash_password(new_password), _now_iso())
    resp = success(message='密码修改成功，请重新登录')
    clear_auth_cookie(resp)
    return resp


@auth_bp.route('/users', methods=['GET'])
@require_auth({'admin'})
def list_users_api():
    keyword = (request.args.get('q') or '').strip()
    role = (request.args.get('role') or '').strip()

    try:
        page = max(1, int(request.args.get('page', 1)))
    except (TypeError, ValueError):
        page = 1

    try:
        page_size = max(1, min(100, int(request.args.get('pageSize', 20))))
    except (TypeError, ValueError):
        page_size = 20

    if role and role not in ROLES:
        return error('角色无效', 400, error_codes.AUTH_USER_INVALID_ROLE)

    rows, total = user_repository.list_users_paginated(
        keyword=keyword,
        role=role,
        page=page,
        page_size=page_size,
    )
    users = []
    for r in rows:
        d = dict(r)
        d['forcePasswordChange'] = bool(int(d.get('force_password_change') or 0))
        users.append(d)
    return success(
        data={
            'users': users,
            'pagination': {
                'page': page,
                'pageSize': page_size,
                'total': total,
            },
            'filters': {
                'q': keyword,
                'role': role or 'all',
            },
        },
        message='获取用户列表成功',
    )

@auth_bp.route('/users', methods=['POST'])
@require_auth({'admin'})
def create_user_api():
    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''
    role = (data.get('role') or 'user').strip()
    status = (data.get('status') or 'active').strip()

    if not username or not password:
        return error('用户名和密码不能为空', 400, error_codes.AUTH_USER_CREATE_INVALID_INPUT)
    ok, msg = validate_password_strength(password)
    if not ok:
        return error(msg, 400, error_codes.AUTH_USER_CREATE_INVALID_INPUT)
    if role not in ROLES:
        return error('角色无效', 400, error_codes.AUTH_USER_INVALID_ROLE)
    if status not in STATUSES:
        return error('状态无效', 400, error_codes.AUTH_USER_INVALID_STATUS)
    if user_repository.find_by_username(username):
        return error('用户名已存在', 409, error_codes.AUTH_USER_ALREADY_EXISTS)

    user_id = user_repository.create_user(
        username=username,
        password_hash=hash_password(password),
        role=role,
        status=status,
        now_iso=_now_iso(),
    )

    return success(data={'id': user_id}, message='用户创建成功')


@auth_bp.route('/users/<int:user_id>', methods=['PATCH'])
@require_auth({'admin'})
def update_user_api(user_id: int):
    data = request.get_json(silent=True) or {}
    role = data.get('role')
    status = data.get('status')

    row = user_repository.find_by_id(user_id)
    if not row:
        return error('用户不存在', 404, error_codes.AUTH_USER_NOT_FOUND)

    if user_id == g.current_user['id']:
        if status == 'disabled' or role == 'user':
            return error('不能将当前登录管理员降权或禁用', 400, error_codes.AUTH_UPDATE_SELF_FORBIDDEN)

    if role is not None and role not in ROLES:
        return error('角色无效', 400, error_codes.AUTH_USER_INVALID_ROLE)
    if status is not None and status not in STATUSES:
        return error('状态无效', 400, error_codes.AUTH_USER_INVALID_STATUS)

    # 防止系统失去最后一个管理员
    if row['role'] == 'admin':
        active_admin_count = user_repository.count_active_admin_users()
        row_is_active_admin = row['status'] == 'active'
        will_remove_active_admin = row_is_active_admin and (role == 'user' or status == 'disabled')
        if active_admin_count <= 1 and will_remove_active_admin:
            return error('系统至少需要保留一个可用管理员', 400, error_codes.AUTH_LAST_ADMIN_FORBIDDEN)

    user_repository.update_user_meta(user_id, role=role, status=status, now_iso=_now_iso())
    return success(message='用户更新成功')


@auth_bp.route('/users/<int:user_id>/reset-password', methods=['POST'])
@require_auth({'admin'})
def reset_password_api(user_id: int):
    # 兼容旧接口语义：不再直接重置密码，而是签发一次性重置令牌。

    row = user_repository.find_by_id(user_id)
    if not row:
        return error('用户不存在', 404, error_codes.AUTH_USER_NOT_FOUND)

    reset_token, expires_at = issue_password_reset_token(user_id)
    data = _build_reset_token_delivery(user_id, reset_token, expires_at)
    return success(
        message='已生成一次性重置令牌' if _should_expose_reset_token() else '已生成一次性重置令牌，请在管理员界面一次性查看并安全转交',
        data=data,
    )


@auth_bp.route('/users/<int:user_id>/password-reset-token', methods=['POST'])
@require_auth({'admin'})
def issue_user_password_reset_token_api(user_id: int):
    row = user_repository.find_by_id(user_id)
    if not row:
        return error('用户不存在', 404, error_codes.AUTH_USER_NOT_FOUND)

    reset_token, expires_at = issue_password_reset_token(user_id)
    data = _build_reset_token_delivery(user_id, reset_token, expires_at)
    return success(
        message='重置令牌签发成功' if _should_expose_reset_token() else '重置令牌签发成功，请在管理员界面一次性查看并安全转交',
        data=data,
    )


@auth_bp.route('/users/password-reset-token-deliveries/<delivery_id>/reveal', methods=['POST'])
@require_auth({'admin'})
def reveal_password_reset_token_api(delivery_id: str):
    state, payload = runtime_state_repo.consume_password_reset_delivery(delivery_id, int(g.current_user['id']))
    if state == 'not_found':
        return error('令牌投递单不存在', 404, error_codes.AUTH_RESET_TOKEN_DELIVERY_NOT_FOUND)
    if state == 'forbidden':
        return error('无权查看该令牌投递单', 403, error_codes.AUTH_RESET_TOKEN_DELIVERY_FORBIDDEN)
    if state == 'expired':
        return error('令牌投递单已过期', 400, error_codes.AUTH_RESET_TOKEN_DELIVERY_EXPIRED)
    if state == 'used':
        return error('令牌投递单已被读取', 400, error_codes.AUTH_RESET_TOKEN_DELIVERY_USED)

    logger.info(
        '重置令牌投递单已读取',
        extra={
            'issuer_user_id': int(g.current_user['id']),
            'target_user_id': int(payload['target_user_id']),
            'delivery_id': delivery_id,
        },
    )
    return success(
        message='重置令牌读取成功（仅展示一次）',
        data={
            'resetToken': payload['reset_token'],
            'expiresAt': payload['reset_token_expires_at'],
            'userId': payload['target_user_id'],
        },
    )


@auth_bp.route('/auth/password-reset/confirm', methods=['POST'])
def confirm_password_reset_api():
    data = request.get_json(silent=True) or {}
    reset_token = (data.get('resetToken') or '').strip()
    new_password = data.get('newPassword') or ''

    ok, msg = use_password_reset_token(reset_token, new_password)
    if not ok:
        code = error_codes.AUTH_RESET_TOKEN_INVALID if '令牌' in msg else error_codes.AUTH_CHANGE_PASSWORD_INVALID_INPUT
        return error(msg, 400, code)

    return success(message='密码重置成功，请使用新密码登录')


@auth_bp.route('/users/<int:user_id>', methods=['DELETE'])
@require_auth({'admin'})
def delete_user_api(user_id: int):
    if user_id == g.current_user['id']:
        return error('不能删除当前登录用户', 400, error_codes.AUTH_DELETE_SELF_FORBIDDEN)

    row = user_repository.find_by_id(user_id)
    if not row:
        return error('用户不存在', 404, error_codes.AUTH_USER_NOT_FOUND)

    if row['role'] == 'admin' and row['status'] == 'active' and user_repository.count_active_admin_users() <= 1:
        return error('系统至少需要保留一个可用管理员', 400, error_codes.AUTH_LAST_ADMIN_FORBIDDEN)

    user_repository.delete_user(user_id)
    return success(message='用户删除成功')
