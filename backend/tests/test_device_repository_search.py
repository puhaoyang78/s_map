#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3
import tempfile
import unittest
from pathlib import Path

from repositories.device_repository import DeviceRepository


class DeviceRepositorySearchTests(unittest.TestCase):
    def setUp(self):
        self._tmp_dir = tempfile.TemporaryDirectory()
        self._db_path = Path(self._tmp_dir.name) / 'global_device_20260101.db'
        with sqlite3.connect(self._db_path) as conn:
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
                ],
            )

        self.repo = DeviceRepository.__new__(DeviceRepository)
        self.repo._db_path = str(self._db_path)

    def tearDown(self):
        self._tmp_dir.cleanup()

    def test_query_devices_keyword_matches_ip(self):
        total, items = self.repo.query_devices(page=1, page_size=10, keyword='203.0.113')

        self.assertEqual(total, 1)
        self.assertEqual(items[0]['ip'], '203.0.113.10')

    def test_export_all_keyword_matches_ip(self):
        rows = self.repo.export_all(keyword='198.51.100')

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['ip'], '198.51.100.23')


if __name__ == '__main__':
    unittest.main()
