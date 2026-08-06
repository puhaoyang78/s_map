#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import hashlib
import hmac
import time
from typing import Optional


def build_webhook_signature(secret: str, timestamp: str, payload_bytes: bytes) -> str:
    digest = hmac.new(
        secret.encode('utf-8'),
        timestamp.encode('utf-8') + b'.' + payload_bytes,
        hashlib.sha256,
    ).hexdigest()
    return f'sha256={digest}'


def verify_webhook_signature(
    payload_bytes: bytes,
    secret: str,
    timestamp: str,
    signature: str,
    ttl_seconds: int,
    now_ts: Optional[int] = None,
) -> tuple[bool, str]:
    ts = (timestamp or '').strip()
    supplied_signature = (signature or '').strip()
    if not ts or not supplied_signature:
        return False, 'missing_signature_headers'

    try:
        ts_int = int(ts)
    except ValueError:
        return False, 'invalid_signature_timestamp'

    current_ts = int(time.time()) if now_ts is None else int(now_ts)
    if abs(current_ts - ts_int) > max(1, int(ttl_seconds)):
        return False, 'signature_expired'

    expected = build_webhook_signature(secret, ts, payload_bytes)
    if not hmac.compare_digest(supplied_signature, expected):
        return False, 'signature_mismatch'

    return True, ''
