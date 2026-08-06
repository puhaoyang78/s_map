#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""回归测试：CSV 导出行数上限（修复项 5）。"""

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from repositories.device_repository import DeviceRepository
from services import device_service


def _row(i):
    return {
        'id': i,
        'ip': f'10.0.0.{i}',
        'country': '中国',
        'region': '北京',
        'city': '北京',
        'lat': 39.9,
        'lng': 116.4,
    }


class ExportAllLimitTests(unittest.TestCase):
    def setUp(self):
        self._tmp_dir = tempfile.TemporaryDirectory()
        self._db_path = Path(self._tmp_dir.name) / 'global_device_20260101.db'
        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute(
                """CREATE TABLE global_device (
                    id INTEGER PRIMARY KEY,
                    ip TEXT,
                    country TEXT,
                    region TEXT,
                    city TEXT,
                    lat REAL,
                    lng REAL
                )"""
            )
            conn.executemany(
                """INSERT INTO global_device
                    (id, ip, country, region, city, lat, lng)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                [
                    (1, '203.0.113.10', '美国', 'Alaska', 'Anchorage', 61.2, -149.9),
                    (2, '198.51.100.23', '加拿大', 'Ontario', 'Toronto', 43.6, -79.3),
                    (3, '192.0.2.8', '中国', '北京', '北京', 39.9, 116.4),
                ],
            )
            conn.commit()
        finally:
            conn.close()

        self.repo = DeviceRepository.__new__(DeviceRepository)
        self.repo._db_path = str(self._db_path)

    def tearDown(self):
        self._tmp_dir.cleanup()

    def test_export_all_respects_max_rows(self):
        rows = self.repo.export_all(max_rows=2)

        self.assertEqual(len(rows), 2)

    def test_export_all_without_limit_returns_all_rows(self):
        rows = self.repo.export_all()

        self.assertEqual(len(rows), 3)


class ExportCsvLimitTests(unittest.TestCase):
    def setUp(self):
        self._env_backup = dict(os.environ)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env_backup)

    @staticmethod
    def _stub_repo(rows):
        class _Stub:
            def export_all(self, keyword='', max_rows=None):
                return rows[:max_rows] if max_rows is not None else list(rows)

        return _Stub()

    def test_over_limit_raises_clear_error(self):
        os.environ['DEVICE_EXPORT_MAX_ROWS'] = '2'
        rows = [_row(1), _row(2), _row(3)]

        with patch.object(device_service, 'DeviceRepository', return_value=self._stub_repo(rows)):
            with self.assertRaises(device_service.ExportLimitExceededError) as ctx:
                device_service.export_devices_csv('', None)

        self.assertIn('超过上限', str(ctx.exception))

    def test_under_limit_returns_csv(self):
        os.environ['DEVICE_EXPORT_MAX_ROWS'] = '10'
        rows = [_row(1)]

        with patch.object(device_service, 'DeviceRepository', return_value=self._stub_repo(rows)):
            mem = device_service.export_devices_csv('', None)

        content = mem.getvalue()
        self.assertTrue(content.startswith(b'\xef\xbb\xbf'))
        self.assertIn('10.0.0.1'.encode('utf-8'), content)


if __name__ == '__main__':
    unittest.main()
