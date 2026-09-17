"""
mongo_database.py

Production property data source backed by MongoDB. Enable by setting:

    DATA_SOURCE=mongodb
    MONGODB_URI=...
    MONGODB_DATABASE=...
    MONGODB_COLLECTION=properties

If the client's documents use different field names than our normalized
schema, adjust FIELD_MAP below (source_field -> normalized_field) instead
of asking the client to rename their database fields.
"""

import os

from property_repository import PropertyRepository
from repository_utils import normalize_property, matches_filters

# Example: {"bhk": "bedrooms", "propertyPrice": "price_inr", "propertyCity": "city"}
FIELD_MAP = {}


class MongoPropertyRepository(PropertyRepository):
    def __init__(self):
        self.uri = os.getenv("MONGODB_URI")
        self.database_name = os.getenv("MONGODB_DATABASE")
        self.collection_name = os.getenv("MONGODB_COLLECTION", "properties")
        self._client = None

    def _get_collection(self):
        import pymongo

        if self._client is None:
            if not self.uri:
                raise RuntimeError("MONGODB_URI is not configured.")
            self._client = pymongo.MongoClient(self.uri, serverSelectionTimeoutMS=5000)
        db = self._client[self.database_name]
        return db[self.collection_name]

    def get_all_properties(self):
        collection = self._get_collection()
        docs = collection.find({})
        return [normalize_property(d, FIELD_MAP) for d in docs]

    def get_property_by_id(self, property_id):
        collection = self._get_collection()
        doc = collection.find_one({"property_id": property_id})
        if not doc:
            return None
        return normalize_property(doc, FIELD_MAP)

    def search_properties(self, filters: dict):
        # Build a Mongo-side query for the fields that map cleanly,
        # then apply any remaining in-memory filtering for safety.
        collection = self._get_collection()
        query = {}
        filters = filters or {}

        if filters.get("city"):
            query["city"] = {"$regex": filters["city"], "$options": "i"}
        if filters.get("listing_type"):
            query["listing_type"] = {"$regex": f"^{filters['listing_type']}$", "$options": "i"}
        if filters.get("bedrooms") not in (None, ""):
            query["bedrooms"] = filters["bedrooms"]

        price_query = {}
        if filters.get("min_price") not in (None, ""):
            price_query["$gte"] = filters["min_price"]
        if filters.get("max_price") not in (None, ""):
            price_query["$lte"] = filters["max_price"]
        if price_query:
            query["price_inr"] = price_query

        docs = collection.find(query)
        properties = [normalize_property(d, FIELD_MAP) for d in docs]
        return [p for p in properties if matches_filters(p, filters)]

    def count_properties(self):
        collection = self._get_collection()
        return collection.count_documents({})

    def health_check(self):
        try:
            collection = self._get_collection()
            collection.database.client.admin.command("ping")
            return True
        except Exception as exc:
            print(f"[MongoPropertyRepository] health_check failed: {exc}")
            return False
