#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import shutil
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path

from config import get_database_path, set_database_path
from services.cache_service import bust_cache
from utils.logger import logger


class ImportPipelineError(Exception):
    pass


def validate_import_runtime_config():
    password = (os.environ.get('DETECTION_ARTIFACT_PASSWORD') or '').strip()
    if not password:
        raise ImportPipelineError('缺少环境变量 DETECTION_ARTIFACT_PASSWORD')


def _extract_7z(archive_path: str, password: str, output_dir: Path):
    try:
        import py7zr
    except Exception as e:
        raise ImportPipelineError('缺少依赖 py7zr，请在 backend/requirements.txt 安装') from e

    with py7zr.SevenZipFile(archive_path, mode='r', password=password) as zf:
        zf.extractall(path=str(output_dir))


def _find_db_file(root: Path):
    candidates = list(root.rglob('*.db'))
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


def _validate_db(db_path: Path):
    conn = None
    try:
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='global_device'")
        if not cur.fetchone():
            raise ImportPipelineError('导入失败：数据库中缺少 global_device 表')
        cur.execute('SELECT COUNT(*) FROM global_device')
        count = int(cur.fetchone()[0])
        if count <= 0:
            raise ImportPipelineError('导入失败：global_device 记录数为 0')
        return count
    except ImportPipelineError:
        raise
    except Exception as e:
        raise ImportPipelineError(f'数据库校验失败: {e}') from e
    finally:
        if conn is not None:
            conn.close()


def _valid_snapshot_date(token: str) -> str:
    try:
        return datetime.strptime(token, '%Y%m%d').strftime('%Y%m%d')
    except ValueError:
        return ''


def _date_from_name(name: str) -> str:
    # Preferred artifact formats:
    #   20250810_152354_enc.7z
    #   <job_id>_20260611-120541_enc.7z
    #   20260611-120541.db
    for pattern in (
        r'(?:^|[_-])(\d{8})[-_]\d{6}(?:_enc)?(?:\.[^.]+)?$',
        r'global_device_(\d{8})\.db$',
    ):
        m = re.search(pattern, name)
        if m:
            key = _valid_snapshot_date(m.group(1))
            if key:
                return key

    # Last-resort fallback: use a real calendar date token, not arbitrary
    # eight digits from a job id.
    candidates = []
    for m in re.finditer(r'(?<!\d)(\d{8})(?!\d)', name):
        key = _valid_snapshot_date(m.group(1))
        if key:
            candidates.append(key)
    return candidates[-1] if candidates else ''


def _resolve_snapshot_key(local_artifact_path: str, db_file: Path) -> str:
    artifact_name = Path(local_artifact_path).name

    snapshot_key = _date_from_name(artifact_name)
    if snapshot_key:
        return snapshot_key

    snapshot_key = _date_from_name(db_file.name)
    if snapshot_key:
        return snapshot_key

    return datetime.now().strftime('%Y%m%d')


def import_and_activate(local_artifact_path: str):
    password = (os.environ.get('DETECTION_ARTIFACT_PASSWORD') or '').strip()
    validate_import_runtime_config()

    with tempfile.TemporaryDirectory(prefix='detect_import_') as td:
        tmp_dir = Path(td)
        _extract_7z(local_artifact_path, password, tmp_dir)
        db_file = _find_db_file(tmp_dir)
        if not db_file:
            raise ImportPipelineError('压缩包中未找到 .db 文件')

        row_count = _validate_db(db_file)

        # 按源产物文件日期命名为 global_device_YYYYMMDD.db
        snapshot_key = _resolve_snapshot_key(local_artifact_path, db_file)

        target = Path(__file__).resolve().parent.parent / 'data' / f'global_device_{snapshot_key}.db'
        target.parent.mkdir(exist_ok=True)
        if target.exists():
            # 同日重复导入：先把现有快照（可能是当前服务库）改名备份，避免直接覆盖
            backup = target.with_name(target.name + '.bak')
            os.replace(str(target), str(backup))
            logger.warning('目标快照 %s 已存在，已备份为 %s', target.name, backup.name)
        shutil.move(str(db_file), str(target))

    # 激活快照并清缓存
    if not set_database_path(str(target)):
        raise ImportPipelineError('激活快照失败：写入数据库配置失败')

    active_db = Path(get_database_path())
    if active_db.name != target.name:
        raise ImportPipelineError(
            f'激活快照失败：当前生效数据库为 {active_db.name}，期望为 {target.name}'
        )

    cache_version = bust_cache()
    logger.info('探测产物导入并激活成功: %s', target)

    return {
        'snapshot_key': snapshot_key,
        'db_path': str(target),
        'row_count': row_count,
        'cache_version': cache_version,
    }
