"""
api_database.py

Production property data source backed by a client's REST API. Enable by
setting:

    DATA_SOURCE=api
    PROPERTY_API_URL=...
    PROPERTY_API_KEY=...

Assumes the API returns JSON - either a bare list of property records, or
an object with a "properties" / "data" / "results" key holding the list.
Adjust _extract_records() and FIELD_MAP if the client's API shape differs.
"""

import os

import requests

from property_repository import PropertyRepository
from repository_utils import normalize_property, matches_filters

FIELD_MAP = {}


class APIPropertyRepository(PropertyRepository):
    def __init__(self):
        self.base_url = os.getenv("PROPERTY_API_URL")
        self.api_key = os.getenv("PROPERTY_API_KEY")

    def _headers(self):
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _extract_records(self, payload):
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            for key in ("properties", "data", "results", "items"):
                if key in payload and isinstance(payload[key], list):
                    return payload[key]
        return []

    def _fetch_all(self):
        if not self.base_url:
            raise RuntimeError("PROPERTY_API_URL is not configured.")
        response = requests.get(self.base_url, headers=self._headers(), timeout=10)
        response.raise_for_status()
        payload = response.json()
        records = self._extract_records(payload)
        return [normalize_property(r, FIELD_MAP) for r in records]

    def get_all_properties(self):
        try:
            return self._fetch_all()
        except requests.RequestException as exc:
            print(f"[APIPropertyRepository] get_all_properties failed: {exc}")
            return []

    def get_property_by_id(self, property_id):
        properties = self.get_all_properties()
        for p in properties:
            if str(p.get("property_id")).strip().lower() == str(property_id).strip().lower():
                return p
        return None

    def search_properties(self, filters: dict):
        properties = self.get_all_properties()
        return [p for p in properties if matches_filters(p, filters or {})]

    def count_properties(self):
        return len(self.get_all_properties())

    def health_check(self):
        try:
            if not self.base_url:
                return False
            response = requests.get(self.base_url, headers=self._headers(), timeout=5)
            return response.status_code < 500
        except requests.RequestException as exc:
            print(f"[APIPropertyRepository] health_check failed: {exc}")
            return False
