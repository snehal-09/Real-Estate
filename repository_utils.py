"""
repository_utils.py

Shared helpers used by every concrete PropertyRepository implementation:
- normalize_property(): coerce a raw record (dict-like) into the
  standard normalized shape used across the whole app.
- matches_filters(): in-memory filter matching, used by the Excel
  repository and as a fallback / post-filter for other sources.
"""

from property_repository import NORMALIZED_FIELDS


def _to_number(value, default=None):
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def normalize_property(raw: dict, field_map: dict = None) -> dict:
    """
    Convert a raw record into the normalized property dict.

    field_map lets a client's differently-named fields map onto the
    normalized field names, e.g.:
        {"bhk": "bedrooms", "propertyPrice": "price_inr"}
    """
    field_map = field_map or {}
    source = dict(raw)

    # Apply field_map: rename source keys to normalized names first.
    for source_key, normalized_key in field_map.items():
        if source_key in source:
            source[normalized_key] = source.pop(source_key)

    normalized = {}
    for field in NORMALIZED_FIELDS:
        value = source.get(field)
        normalized[field] = value

    # Type coercion for numeric / count fields.
    normalized["price_inr"] = _to_number(normalized.get("price_inr"), 0)
    normalized["bedrooms"] = int(_to_number(normalized.get("bedrooms"), 0) or 0)
    normalized["bathrooms"] = int(_to_number(normalized.get("bathrooms"), 0) or 0)
    normalized["area_sqft"] = _to_number(normalized.get("area_sqft"), 0)

    # Strings - ensure no NaN / None leaks to the frontend.
    for field in [
        "property_id", "title", "property_type", "listing_type",
        "location", "city", "furnishing", "parking", "amenities",
        "possession", "agent_name", "agent_phone",
    ]:
        if normalized.get(field) is None:
            normalized[field] = ""
        else:
            normalized[field] = str(normalized[field]).strip()

    return normalized


def matches_filters(prop: dict, filters: dict) -> bool:
    """In-memory filter matching against a single normalized property dict."""
    if not filters:
        return True

    def norm_str(v):
        return str(v).strip().lower() if v is not None else ""

    if filters.get("city") and norm_str(filters["city"]) not in norm_str(prop.get("city")):
        return False

    if filters.get("location") and norm_str(filters["location"]) not in norm_str(prop.get("location")):
        return False

    if filters.get("listing_type") and norm_str(filters["listing_type"]) != norm_str(prop.get("listing_type")):
        return False

    if filters.get("property_type") and norm_str(filters["property_type"]) != norm_str(prop.get("property_type")):
        return False

    if filters.get("bedrooms") not in (None, ""):
        try:
            if int(prop.get("bedrooms", 0)) != int(filters["bedrooms"]):
                return False
        except (TypeError, ValueError):
            pass

    if filters.get("bathrooms") not in (None, ""):
        try:
            if int(prop.get("bathrooms", 0)) != int(filters["bathrooms"]):
                return False
        except (TypeError, ValueError):
            pass

    if filters.get("min_price") not in (None, ""):
        try:
            if float(prop.get("price_inr", 0)) < float(filters["min_price"]):
                return False
        except (TypeError, ValueError):
            pass

    if filters.get("max_price") not in (None, ""):
        try:
            if float(prop.get("price_inr", 0)) > float(filters["max_price"]):
                return False
        except (TypeError, ValueError):
            pass

    if filters.get("min_area_sqft") not in (None, ""):
        try:
            if float(prop.get("area_sqft", 0)) < float(filters["min_area_sqft"]):
                return False
        except (TypeError, ValueError):
            pass

    if filters.get("max_area_sqft") not in (None, ""):
        try:
            if float(prop.get("area_sqft", 0)) > float(filters["max_area_sqft"]):
                return False
        except (TypeError, ValueError):
            pass

    if filters.get("furnishing") and norm_str(filters["furnishing"]) != norm_str(prop.get("furnishing")):
        return False

    if filters.get("parking"):
        if not norm_str(prop.get("parking")):
            return False

    if filters.get("possession") and norm_str(filters["possession"]) not in norm_str(prop.get("possession")):
        return False

    amenities_filter = filters.get("amenities")
    if amenities_filter:
        prop_amenities = norm_str(prop.get("amenities"))
        for amenity in amenities_filter:
            if norm_str(amenity) not in prop_amenities:
                return False

    return True
