#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from dataclasses import dataclass
from typing import Optional

from utils import error_codes


@dataclass
class AppError(Exception):
    message: str
    http_status: int = 400
    biz_code: str = error_codes.COMMON_INVALID_PARAM
    details: Optional[dict] = None


class ValidationError(AppError):
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message=message, http_status=400, biz_code=error_codes.COMMON_INVALID_PARAM, details=details)


class AuthenticationError(AppError):
    def __init__(self, message: str = '未认证', details: Optional[dict] = None):
        super().__init__(message=message, http_status=401, biz_code=error_codes.AUTH_UNAUTHORIZED, details=details)


class AuthorizationError(AppError):
    def __init__(self, message: str = '无权限访问', details: Optional[dict] = None):
        super().__init__(message=message, http_status=403, biz_code=error_codes.AUTH_FORBIDDEN, details=details)


class NotFoundError(AppError):
    def __init__(self, message: str = '资源不存在', details: Optional[dict] = None):
        super().__init__(message=message, http_status=404, biz_code=error_codes.COMMON_NOT_FOUND, details=details)


class ConflictError(AppError):
    def __init__(self, message: str = '资源冲突', details: Optional[dict] = None):
        super().__init__(message=message, http_status=409, biz_code=error_codes.COMMON_CONFLICT, details=details)


class ExternalServiceError(AppError):
    def __init__(self, message: str = '外部服务调用失败', details: Optional[dict] = None):
        super().__init__(message=message, http_status=502, biz_code=error_codes.COMMON_INTERNAL_ERROR, details=details)


class InternalServiceError(AppError):
    def __init__(self, message: str = '服务内部错误', details: Optional[dict] = None):
        super().__init__(message=message, http_status=500, biz_code=error_codes.COMMON_INTERNAL_ERROR, details=details)
