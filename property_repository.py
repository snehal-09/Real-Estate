"""
property_repository.py

Defines the common PropertyRepository interface that the rest of the
application (chatbot, Flask routes) talks to. Concrete implementations
(Excel, MongoDB, MySQL, PostgreSQL, REST API) live in their own modules
and all return the SAME normalized property dictionary shape.

The rest of the app should NEVER import excel_database / mongo_database /
etc. directly - always go through get_property_repository().
"""

import os
from abc import ABC, abstractmethod


# ---------------------------------------------------------------------------
# Normalized property fields (documented for every implementation to follow)
# ---------------------------------------------------------------------------
NORMALIZED_FIELDS = [
    "property_id",
    "title",
    "property_type",
    "listing_type",
    "location",
    "city",
    "price_inr",
    "bedrooms",
    "bathrooms",
    "area_sqft",
    "furnishing",
    "parking",
    "amenities",
    "possession",
    "agent_name",
    "agent_phone",
]


class PropertyRepository(ABC):
    """Common interface every property data source must implement."""

    @abstractmethod
    def get_all_properties(self):
        """Return a list of normalized property dicts."""
        raise NotImplementedError

    @abstractmethod
    def get_property_by_id(self, property_id):
        """Return a single normalized property dict, or None."""
        raise NotImplementedError

    @abstractmethod
    def search_properties(self, filters: dict):
        """
        filters may include any of:
            city, location, listing_type, property_type,
            bedrooms, bathrooms, min_price, max_price,
            min_area_sqft, max_area_sqft, furnishing,
            parking, amenities (list), possession

        Returns a list of normalized property dicts.
        """
        raise NotImplementedError

    @abstractmethod
    def count_properties(self):
        raise NotImplementedError

    @abstractmethod
    def health_check(self):
        """Return True/False (or raise) - used by /api/health."""
        raise NotImplementedError

    # ---- Optional convenience methods (default implementations) ----
    def get_properties_by_city(self, city):
        return self.search_properties({"city": city})

    def get_properties_by_listing_type(self, listing_type):
        return self.search_properties({"listing_type": listing_type})

    def get_properties_by_price_range(self, min_price, max_price):
        return self.search_properties({"min_price": min_price, "max_price": max_price})


def get_property_repository():
    """
    Factory that reads DATA_SOURCE from the environment and returns the
    correct PropertyRepository implementation. This is the ONLY place
    that should decide which concrete class gets instantiated.
    """
    data_source = os.getenv("DATA_SOURCE", "excel").strip().lower()

    if data_source == "excel":
        from excel_database import ExcelPropertyRepository
        return ExcelPropertyRepository()

    if data_source == "mongodb":
        from mongo_database import MongoPropertyRepository
        return MongoPropertyRepository()

    if data_source == "mysql":
        from mysql_database import MySQLPropertyRepository
        return MySQLPropertyRepository()

    if data_source == "postgresql":
        from postgres_database import PostgreSQLPropertyRepository
        return PostgreSQLPropertyRepository()

    if data_source == "api":
        from api_database import APIPropertyRepository
        return APIPropertyRepository()

    raise ValueError(
        f"Unsupported DATA_SOURCE: {data_source}. "
        f"Supported values: excel, mongodb, mysql, postgresql, api"
    )
