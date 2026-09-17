"""
mysql_database.py

Production property data source backed by MySQL. Enable by setting:

    DATA_SOURCE=mysql
    MYSQL_HOST=...
    MYSQL_PORT=3306
    MYSQL_USER=...
    MYSQL_PASSWORD=...
    MYSQL_DATABASE=...
    MYSQL_PROPERTIES_TABLE=properties

If the client's table uses different column names, adjust FIELD_MAP below.
"""

import os

from property_repository import PropertyRepository
from repository_utils import normalize_property, matches_filters

FIELD_MAP = {}


class MySQLPropertyRepository(PropertyRepository):
    def __init__(self):
        self.host = os.getenv("MYSQL_HOST", "localhost")
        self.port = int(os.getenv("MYSQL_PORT", "3306"))
        self.user = os.getenv("MYSQL_USER")
        self.password = os.getenv("MYSQL_PASSWORD")
        self.database = os.getenv("MYSQL_DATABASE")
        self.table = os.getenv("MYSQL_PROPERTIES_TABLE", "properties")

    def _get_connection(self):
        import mysql.connector

        return mysql.connector.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            database=self.database,
            connection_timeout=5,
        )

    def _fetch(self, where_clause="", params=None):
        conn = self._get_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            query = f"SELECT * FROM {self.table}"
            if where_clause:
                query += f" WHERE {where_clause}"
            cursor.execute(query, params or [])
            rows = cursor.fetchall()
            return [normalize_property(r, FIELD_MAP) for r in rows]
        finally:
            conn.close()

    def get_all_properties(self):
        return self._fetch()

    def get_property_by_id(self, property_id):
        results = self._fetch("property_id = %s", [property_id])
        return results[0] if results else None

    def search_properties(self, filters: dict):
        filters = filters or {}
        clauses = []
        params = []

        if filters.get("city"):
            clauses.append("city LIKE %s")
            params.append(f"%{filters['city']}%")
        if filters.get("listing_type"):
            clauses.append("listing_type = %s")
            params.append(filters["listing_type"])
        if filters.get("bedrooms") not in (None, ""):
            clauses.append("bedrooms = %s")
            params.append(filters["bedrooms"])
        if filters.get("min_price") not in (None, ""):
            clauses.append("price_inr >= %s")
            params.append(filters["min_price"])
        if filters.get("max_price") not in (None, ""):
            clauses.append("price_inr <= %s")
            params.append(filters["max_price"])

        where_clause = " AND ".join(clauses)
        properties = self._fetch(where_clause, params)
        return [p for p in properties if matches_filters(p, filters)]

    def count_properties(self):
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM {self.table}")
            (count,) = cursor.fetchone()
            return count
        finally:
            conn.close()

    def health_check(self):
        try:
            conn = self._get_connection()
            conn.close()
            return True
        except Exception as exc:
            print(f"[MySQLPropertyRepository] health_check failed: {exc}")
            return False
