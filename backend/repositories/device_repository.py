#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
设备数据仓库
所有对 global_device 表的 SQL 操作均在此封装，上层业务代码不直接操作数据库
"""

import sqlite3
from utils.logger import logger


class ClosingConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            return super().__exit__(exc_type, exc_val, exc_tb)
        finally:
            self.close()


class DeviceRepository:
    """封装全部设备数据库操作"""

    def __init__(self, snapshot: str = None):
        from config import get_db_path_for_snapshot
        self._db_path = get_db_path_for_snapshot(snapshot)

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        import os
        if not os.path.exists(self._db_path):
            raise FileNotFoundError(f'数据库文件不存在: {self._db_path}')
        conn = sqlite3.connect(self._db_path, factory=ClosingConnection)
        conn.row_factory = sqlite3.Row
        return conn

    # ------------------------------------------------------------------
    # 索引管理
    # ------------------------------------------------------------------

    def ensure_indices(self):
        """确保查询索引存在（幂等操作）"""
        indices = {
            'idx_country': 'CREATE INDEX IF NOT EXISTS idx_country ON global_device(country)',
            'idx_region':  'CREATE INDEX IF NOT EXISTS idx_region ON global_device(region)',
            'idx_city':    'CREATE INDEX IF NOT EXISTS idx_city ON global_device(city)',
            'idx_geo':          'CREATE INDEX IF NOT EXISTS idx_geo ON global_device(lat, lng)',
            'idx_city_country': 'CREATE INDEX IF NOT EXISTS idx_city_country ON global_device(country, region, city)',
            # 查询条件使用 TRIM(country)/TRIM(city)，表达式索引可避免全表扫描
            'idx_country_trim': 'CREATE INDEX IF NOT EXISTS idx_country_trim ON global_device(TRIM(country))',
            'idx_city_trim':    'CREATE INDEX IF NOT EXISTS idx_city_trim ON global_device(TRIM(city))',
        }
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='index' AND name IN ({})".format(
                        ','.join(f"'{k}'" for k in indices)
                    )
                )
                existing = {row[0] for row in cursor.fetchall()}
                created = []
                for name, ddl in indices.items():
                    if name not in existing:
                        cursor.execute(ddl)
                        created.append(name)
                if created:
                    conn.commit()
                    logger.info('[%s] 已创建索引: %s', self._db_path, created)
        except Exception as e:
            logger.error('创建索引失败: %s', e)

    # ------------------------------------------------------------------
    # 统计信息
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        conn = self._connect()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT COUNT(*) FROM global_device')
            total = cursor.fetchone()[0]

            cursor.execute(
                "SELECT COUNT(DISTINCT TRIM(country)) FROM global_device "
                "WHERE country != '-' AND country != '' AND TRIM(country) != ''"
            )
            country_count = cursor.fetchone()[0]

            cursor.execute(
                "SELECT COUNT(DISTINCT TRIM(city)) FROM global_device "
                "WHERE city != '-' AND city != '' AND TRIM(city) != ''"
            )
            city_count = cursor.fetchone()[0]

            cursor.execute(
                """SELECT TRIM(country) as country, COUNT(*) as count
                   FROM global_device
                   WHERE country != '-' AND country != '' AND TRIM(country) != ''
                   GROUP BY TRIM(country)
                   ORDER BY count DESC"""
            )
            country_stats = {r['country']: r['count'] for r in cursor.fetchall()}

            return {
                'totalDevices': total,
                'countryCount': country_count,
                'cityCount': city_count,
                'countryStats': country_stats,
            }
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # 设备列表查询（分页 + 筛选）
    # ------------------------------------------------------------------

    def query_devices(self, page: int, page_size: int,
                      country: str = '', city: str = '',
                      keyword: str = '') -> tuple:
        """返回 (total_count, items_list)"""
        offset = (page - 1) * page_size
        where_clauses = []
        params = []

        if country:
            where_clauses.append('TRIM(country) = ?')
            params.append(country)
        if city:
            where_clauses.append('TRIM(city) = ?')
            params.append(city)

        if keyword:
            kws = [k.strip() for k in keyword.replace(',', ' ').split() if k.strip()]
            for kw in kws:
                where_clauses.append('(ip LIKE ? OR country LIKE ? OR region LIKE ? OR city LIKE ?)')
                params.extend([f'%{kw}%', f'%{kw}%', f'%{kw}%', f'%{kw}%'])

        where_sql = ('WHERE ' + ' AND '.join(where_clauses)) if where_clauses else ''

        conn = self._connect()
        cursor = conn.cursor()
        try:
            cursor.execute(
                f'SELECT COUNT(*) AS cnt FROM global_device {where_sql}',
                params
            )
            total = cursor.fetchone()['cnt']

            cursor.execute(
                f"""SELECT id AS key, ip, country, region, city, lat, lng
                    FROM global_device {where_sql}
                    ORDER BY id
                    LIMIT ? OFFSET ?""",
                params + [page_size, offset]
            )
            items = [dict(r) for r in cursor.fetchall()]
            return total, items
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # 城市统计（按国家筛选）
    # ------------------------------------------------------------------

    def get_city_stats(self, country: str) -> dict:
        conn = self._connect()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """SELECT TRIM(city) as city, COUNT(*) AS cnt
                   FROM global_device
                   WHERE TRIM(country) = ?
                     AND city <> '' AND TRIM(city) <> ''
                   GROUP BY TRIM(city)""",
                (country,)
            )
            return {r['city']: r['cnt'] for r in cursor.fetchall()}
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # 全量导出
    # ------------------------------------------------------------------

    def export_all(self, keyword: str = '', max_rows: int = None) -> list:
        params = []
        where_sql = ''

        if keyword:
            kws = [k.strip() for k in keyword.replace(',', ' ').split() if k.strip()]
            clauses = []
            for kw in kws:
                clauses.append('(ip LIKE ? OR country LIKE ? OR region LIKE ? OR city LIKE ?)')
                params.extend([f'%{kw}%', f'%{kw}%', f'%{kw}%', f'%{kw}%'])
            if clauses:
                where_sql = 'WHERE ' + ' AND '.join(clauses)

        limit_sql = ''
        if max_rows is not None:
            try:
                safe_max_rows = max(1, int(max_rows))
            except (TypeError, ValueError):
                safe_max_rows = None
            if safe_max_rows:
                limit_sql = ' LIMIT ?'
                params = params + [safe_max_rows]

        conn = self._connect()
        cursor = conn.cursor()
        try:
            cursor.execute(
                f'SELECT id, ip, country, region, city, lat, lng FROM global_device {where_sql}{limit_sql}',
                params
            )
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # 热力图数据
    # ------------------------------------------------------------------

    def get_heatmap_data(self, min_count: int = 1,
                         bbox: tuple = None,
                         max_rows: int = None) -> dict:
        """返回按城市聚合的热力图数据字典"""
        safe_max_rows = None
        if max_rows is not None:
            try:
                safe_max_rows = max(1, int(max_rows))
            except Exception:
                safe_max_rows = None

        conn = self._connect()
        cursor = conn.cursor()
        try:
            if bbox:
                min_lat, max_lat, min_lng, max_lng = bbox
                limit_sql = 'LIMIT ?' if safe_max_rows else 'LIMIT 500'
                params = (min_lat, max_lat, min_lng, max_lng, min_count, safe_max_rows) if safe_max_rows else (min_lat, max_lat, min_lng, max_lng, min_count)
                cursor.execute(
                    """SELECT country, region, city,
                              AVG(lat) as lat, AVG(lng) as lng,
                              COUNT(*) as count
                       FROM global_device
                       WHERE country != '-' AND country != ''
                         AND city != '-' AND city != ''
                         AND lat BETWEEN ? AND ?
                         AND lng BETWEEN ? AND ?
                         AND lat != 0 AND lng != 0
                       GROUP BY country, region, city
                       HAVING count >= ?
                       ORDER BY count DESC
                       """ + limit_sql,
                    params
                )
            else:
                limit_sql = 'LIMIT ?' if safe_max_rows else ''
                params = (min_count, safe_max_rows) if safe_max_rows else (min_count,)
                cursor.execute(
                    """SELECT country, region, city,
                              AVG(lat) as lat, AVG(lng) as lng,
                              COUNT(*) as count
                       FROM global_device
                       WHERE country != '-' AND country != ''
                         AND city != '-' AND city != ''
                         AND lat != 0 AND lng != 0
                       GROUP BY country, region, city
                       HAVING count >= ?
                              ORDER BY count DESC
                              """ + limit_sql,
                          params
                )

            result = {}
            for row in cursor.fetchall():
                key = f"{row['country']}-{row['region']}-{row['city']}".strip()
                if key and key != '--':
                    result[key] = {
                        'country': row['country'],
                        'region':  row['region'],
                        'city':    row['city'],
                        'lat':     row['lat'],
                        'lng':     row['lng'],
                        'count':   row['count'],
                    }
            return result
        finally:
            conn.close()
