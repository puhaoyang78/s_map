#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置管理模块。

负责管理数据库路径、快照列表和运行期配置。
"""

import json
import os
import re
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

from utils.logger import logger


class Config:
    """配置管理类。"""

    SNAPSHOT_PATTERN = re.compile(r'global_device_(\d{8})\.db$')

    def __init__(self, config_file='db_config.json'):
        self.base_dir = Path(__file__).resolve().parent.parent
        self.config_dir = self.base_dir / 'config'
        self.data_dir = self.base_dir / 'data'
        self.backup_dir = self.base_dir / 'db_backups'
        self.config_file = self.config_dir / config_file
        self.legacy_config_file = self.base_dir / config_file

        self.CONFIG_DIR = self.config_dir
        self.DATA_DIR = self.data_dir
        self.BACKUP_DIR = self.backup_dir

        self.config_dir.mkdir(exist_ok=True)
        self.data_dir.mkdir(exist_ok=True)
        self.backup_dir.mkdir(exist_ok=True)

        self.default_config = {
            'database_path': str(self.data_dir / 'global_device_20250409.db'),
            'updated_at': datetime.now().isoformat(),
            'version': '1.0.0',
        }
        self._config = self.load_config()

    @classmethod
    def _extract_snapshot_key(cls, filename: str) -> str:
        match = cls.SNAPSHOT_PATTERN.search(filename or '')
        return match.group(1) if match else ''

    @staticmethod
    def _parse_snapshot_key_date(snapshot_key: str):
        try:
            return datetime.strptime(snapshot_key, '%Y%m%d')
        except ValueError:
            return None

    @classmethod
    def _is_valid_snapshot_key(cls, snapshot_key: str) -> bool:
        return bool(cls._parse_snapshot_key_date(snapshot_key))

    def load_config(self):
        """加载配置文件。"""
        try:
            if (not self.config_file.exists()) and self.legacy_config_file.exists():
                shutil.move(str(self.legacy_config_file), str(self.config_file))

            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)

                if 'database_path' in config:
                    db_path_str = config['database_path']
                    if '/' not in db_path_str.replace('\\', '/'):
                        config['database_path'] = str(Path('data') / db_path_str)

                return {**self.default_config, **config}

            self.save_config(self.default_config)
            return self.default_config
        except Exception as e:
            logger.warning('加载配置文件失败，已回退到默认配置: %s', e)
            return self.default_config

    def save_config(self, config=None):
        """保存配置文件。"""
        tmp_path = None
        try:
            if config is None:
                config = self._config

            config['updated_at'] = datetime.now().isoformat()

            # 先写临时文件再原子替换，避免中途崩溃留下写了一半的配置
            fd, tmp_path = tempfile.mkstemp(prefix='.db_config_', suffix='.tmp', dir=str(self.config_dir))
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, self.config_file)
            tmp_path = None

            self._config = config
            return True
        except Exception as e:
            logger.warning('保存配置文件失败: %s', e)
            return False
        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    def get_database_path(self):
        """获取当前数据库绝对路径。"""
        db_path_str = self._config.get('database_path', self.default_config['database_path'])
        db_path = Path(db_path_str)

        if not db_path.is_absolute():
            db_path = self.base_dir / db_path

        if not db_path.exists():
            fallback = self._resolve_fallback_database_path()
            if fallback:
                self.set_database_path(str(fallback))
                return str(fallback)
            return str(db_path)

        snapshot_key = self._extract_snapshot_key(db_path.name)
        if snapshot_key and not self._is_valid_snapshot_key(snapshot_key):
            fallback = self._resolve_fallback_database_path(exclude_paths={db_path.resolve()})
            if fallback:
                self.set_database_path(str(fallback))
                return str(fallback)

        return str(db_path)

    def _resolve_fallback_database_path(self, exclude_paths=None):
        """回退到最新的有效快照数据库。"""
        excluded = {Path(item).resolve() for item in (exclude_paths or set())}

        latest = None
        latest_key = ''
        for db_file in self.data_dir.glob('global_device_*.db'):
            if db_file.resolve() in excluded:
                continue

            key = self._extract_snapshot_key(db_file.name)
            if not key or not self._is_valid_snapshot_key(key):
                continue

            if key > latest_key:
                latest_key = key
                latest = db_file

        if latest and latest.exists():
            return latest

        default_path = Path(self.default_config['database_path'])
        if not default_path.is_absolute():
            default_path = self.base_dir / default_path
        if default_path.exists() and default_path.resolve() not in excluded:
            return default_path

        return None

    def set_database_path(self, path):
        """设置数据库路径。"""
        path_obj = Path(path)

        try:
            if path_obj.is_absolute():
                if self.base_dir in path_obj.parents or path_obj.parent == self.base_dir:
                    path = str(path_obj.relative_to(self.base_dir))
        except Exception:
            pass

        self._config['database_path'] = path
        self._config['version'] = datetime.now().strftime("%Y%m%d")
        return self.save_config()

    def get_config(self, key, default=None):
        return self._config.get(key, default)

    def set_config(self, key, value):
        self._config[key] = value
        return self.save_config()

    def list_snapshots(self):
        snapshots = []
        for db_file in sorted(self.data_dir.glob('global_device_*.db'), reverse=True):
            snapshot_key = self._extract_snapshot_key(db_file.name)
            if not snapshot_key:
                continue

            parsed_date = self._parse_snapshot_key_date(snapshot_key)
            snapshots.append({
                'key': snapshot_key,
                'filename': db_file.name,
                'path': str(db_file),
                'date': parsed_date.strftime('%Y-%m-%d') if parsed_date else f'异常快照 {snapshot_key}',
                'is_valid_date': bool(parsed_date),
                'size_bytes': db_file.stat().st_size,
            })
        return snapshots

    def delete_snapshot(self, snapshot_key: str):
        key = (snapshot_key or '').strip()
        if not re.match(r'^\d{8}$', key):
            raise ValueError('invalid snapshot key')

        candidate = self.data_dir / f'global_device_{key}.db'
        if not candidate.exists():
            raise FileNotFoundError(f'snapshot {key} not found')

        current_db = Path(self.get_database_path()).resolve()
        switched_to = None
        if candidate.resolve() == current_db:
            fallback = self._resolve_fallback_database_path(exclude_paths={candidate.resolve()})
            if not fallback:
                raise ValueError('cannot delete the active snapshot without another valid fallback')
            self.set_database_path(str(fallback))
            switched_to = str(fallback)

        size_bytes = candidate.stat().st_size
        candidate.unlink()
        return {
            'key': key,
            'filename': candidate.name,
            'path': str(candidate),
            'size_bytes': size_bytes,
            'switched_to': switched_to,
        }

    def get_all_config(self):
        return self._config.copy()


config = Config()


def get_database_path():
    return config.get_database_path()


def set_database_path(path):
    return config.set_database_path(path)


def list_snapshots():
    return config.list_snapshots()


def delete_snapshot(snapshot_key):
    return config.delete_snapshot(snapshot_key)


def get_config_value(key, default=None):
    return config.get_config(key, default)


def set_config_value(key, value):
    return config.set_config(key, value)


def get_db_path_for_snapshot(snapshot: str = None) -> str:
    """根据快照 key 获取对应的数据库绝对路径。"""
    if snapshot and re.match(r'^\d{8}$', snapshot):
        candidate = config.DATA_DIR / f'global_device_{snapshot}.db'
        if candidate.exists():
            return str(candidate)
    return get_database_path()
