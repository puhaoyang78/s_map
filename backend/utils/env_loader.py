#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from pathlib import Path


def load_backend_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return

    backend_root = Path(__file__).resolve().parent.parent
    load_dotenv(backend_root / '.env', override=False)
    # 进程环境（如 systemd EnvironmentFile 注入的值）优先级最高，.env.local 仅补充缺失项
    load_dotenv(backend_root / '.env.local', override=False)
