#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re

PASSWORD_MIN_LENGTH = 12
_COMMON_WEAK_PASSWORDS = {
    '123456',
    '12345678',
    'password',
    'qwerty',
    'admin',
    'admin123',
    'admin123!',
    'letmein',
}


def validate_password_strength(password: str) -> tuple[bool, str]:
    """生产级密码强度校验，返回 (是否通过, 错误信息)。"""
    pwd = (password or '').strip()
    if len(pwd) < PASSWORD_MIN_LENGTH:
        return False, f'密码至少 {PASSWORD_MIN_LENGTH} 位'
    if pwd.lower() in _COMMON_WEAK_PASSWORDS:
        return False, '密码过于常见，请使用更复杂的密码'
    if not re.search(r'[A-Z]', pwd):
        return False, '密码必须包含大写字母'
    if not re.search(r'[a-z]', pwd):
        return False, '密码必须包含小写字母'
    if not re.search(r'\d', pwd):
        return False, '密码必须包含数字'
    if not re.search(r'[^A-Za-z0-9]', pwd):
        return False, '密码必须包含特殊字符'
    return True, ''
