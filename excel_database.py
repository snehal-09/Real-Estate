"""
excel_database.py

Demo property data source. Reads properties from an Excel workbook using
pandas. This is ONLY the demo implementation - the rest of the app talks
to it exclusively through the PropertyRepository interface.
"""

import os
import pandas as pd

from property_repository import PropertyRepository
from repository_utils import normalize_property, matches_filters


class ExcelPropertyRepository(PropertyRepository):
    def __init__(self, file_path: str = None):
        self.file_path = file_path or os.getenv(
            "PROPERTY_EXCEL_FILE", "real_estate_properties.xlsx"
        )

    def _load_dataframe(self):
        if not os.path.exists(self.file_path):
            print(f"[ExcelPropertyRepository] File not found at: {self.file_path}")
            raise FileNotFoundError("Property database file not found.")
        return pd.read_excel(self.file_path, engine="openpyxl")

    def _load_properties(self):
        try:
            df = self._load_dataframe()
        except FileNotFoundError:
            return []

        df = df.where(pd.notnull(df), None)
        records = df.to_dict(orient="records")
        return [normalize_property(r) for r in records]

    def get_all_properties(self):
        return self._load_properties()

    def get_property_by_id(self, property_id):
        properties = self._load_properties()
        for p in properties:
            if str(p.get("property_id")).strip().lower() == str(property_id).strip().lower():
                return p
        return None

    def search_properties(self, filters: dict):
        properties = self._load_properties()
        return [p for p in properties if matches_filters(p, filters or {})]

    def count_properties(self):
        return len(self._load_properties())

    def health_check(self):
        try:
            self._load_dataframe()
            return True
        except Exception as exc:
            print(f"[ExcelPropertyRepository] health_check failed: {exc}")
            return False
