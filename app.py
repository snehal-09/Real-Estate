"""
app.py

EstateEase AI - single Flask application serving both the website
(templates/static) and the JSON API. Run with:

    python app.py

Then open http://127.0.0.1:5000
"""

import os
import re

from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

load_dotenv()

from property_repository import get_property_repository
from google_sheets import GoogleSheetsClient
from emi_calculator import calculate_emi
import chatbot as chatbot_module

app = Flask(__name__)

# Repository + Sheets client are created once at startup (cheap, no network
# calls for Excel; lazy-connect for Sheets / DB sources).
property_repository = get_property_repository()
sheets_client = GoogleSheetsClient()


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------
PHONE_RE = re.compile(r"^\+?[0-9]{7,15}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def is_valid_phone(phone):
    return bool(phone) and bool(PHONE_RE.match(str(phone).strip()))


def is_valid_email(email):
    return bool(email) and bool(EMAIL_RE.match(str(email).strip()))


def error_response(message, status=400):
    return jsonify({"success": False, "error": message}), status


# ---------------------------------------------------------------------------
# Frontend
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
@app.route("/api/health")
def health():
    data_source = os.getenv("DATA_SOURCE", "excel")

    try:
        db_ok = property_repository.health_check()
    except Exception as exc:
        print(f"[health] property repository check failed: {exc}")
        db_ok = False

    return jsonify({
        "status": "ok",
        "app": "EstateEase AI",
        "data_source": data_source,
        "property_database": "connected" if db_ok else "unavailable",
        "google_sheets": "configured" if sheets_client.is_configured() else "not configured (using local CSV fallback)",
        "gemini": "configured" if chatbot_module.gemini_client.is_configured() else "not configured",
    })


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------
@app.route("/api/properties")
def get_properties():
    try:
        properties = property_repository.get_all_properties()
        return jsonify({"success": True, "properties": properties})
    except FileNotFoundError:
        return error_response("Property database file not found.", 503)
    except Exception as exc:
        print(f"[api/properties] error: {exc}")
        return error_response("Property database temporarily unavailable.", 503)


@app.route("/api/properties/<property_id>")
def get_property(property_id):
    try:
        prop = property_repository.get_property_by_id(property_id)
    except FileNotFoundError:
        return error_response("Property database file not found.", 503)
    except Exception as exc:
        print(f"[api/properties/<id>] error: {exc}")
        return error_response("Property database temporarily unavailable.", 503)

    if not prop:
        return error_response("Property not found.", 404)
    return jsonify({"success": True, "property": prop})


@app.route("/api/search", methods=["POST"])
def search_properties():
    filters = request.get_json(silent=True) or {}
    try:
        properties = property_repository.search_properties(filters)
        return jsonify({"success": True, "properties": properties, "count": len(properties)})
    except FileNotFoundError:
        return error_response("Property database file not found.", 503)
    except Exception as exc:
        print(f"[api/search] error: {exc}")
        return error_response("Property database temporarily unavailable.", 503)


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------
@app.route("/api/chat", methods=["POST"])
def chat():
    body = request.get_json(silent=True) or {}
    session_id = body.get("session_id")
    message = (body.get("message") or "").strip()
    user_info = body.get("user") or {}

    if not session_id:
        return error_response("session_id is required.")
    if not message:
        return error_response("message is required.")

    try:
        result = chatbot_module.handle_message(
            session_id=session_id,
            user_message=message,
            user_info=user_info,
            property_repository=property_repository,
        )
    except Exception as exc:
        print(f"[api/chat] error: {exc}")
        return error_response("The assistant is temporarily unavailable. Please try again.", 503)

    # Best-effort chat history logging - never break the chat if this fails.
    # append_chat_history writes to Google Sheets when configured, otherwise
    # falls back to a local CSV automatically (see google_sheets.py).
    try:
        sheets_client.append_chat_history({
            "session_id": session_id,
            "user_name": user_info.get("name", ""),
            "user_phone": user_info.get("phone", ""),
            "user_email": user_info.get("email", ""),
            "user_query": message,
            "ai_response": result.get("message", ""),
            "intent": result.get("intent", ""),
        })
    except Exception as exc:
        print(f"[api/chat] chat history logging failed: {exc}")

    return jsonify(result)


# ---------------------------------------------------------------------------
# Lead generation
# ---------------------------------------------------------------------------
@app.route("/api/lead", methods=["POST"])
def create_lead():
    body = request.get_json(silent=True) or {}

    name = (body.get("name") or "").strip()
    phone = (body.get("phone") or "").strip()
    email = (body.get("email") or "").strip()

    if not name:
        return error_response("Name is required.")
    if not is_valid_phone(phone):
        return error_response("A valid phone number is required.")
    if email and not is_valid_email(email):
        return error_response("Email address is invalid.")

    lead = {
        "name": name,
        "phone": phone,
        "email": email,
        "user_query": body.get("user_query", ""),
        "requirement": body.get("requirement", ""),
        "property_id": body.get("property_id", ""),
        "property_name": body.get("property_name", ""),
        "city": body.get("city", ""),
        "location": body.get("location", ""),
        "budget": body.get("budget", ""),
        "listing_type": body.get("listing_type", ""),
        "bedrooms": body.get("bedrooms", ""),
        "lead_status": "New",
    }

    # Saves to Google Sheets when configured; otherwise append_lead falls
    # back to a local CSV automatically (see google_sheets.py), so this
    # only fails on a genuine write error, never just because Sheets isn't
    # set up yet.
    try:
        sheets_client.append_lead(lead)
    except Exception as exc:
        print(f"[api/lead] failed to save lead: {exc}")
        return error_response("Could not submit your request right now. Please try again in a moment.", 503)

    return jsonify({"success": True})


# ---------------------------------------------------------------------------
# Visit scheduling
# ---------------------------------------------------------------------------
@app.route("/api/schedule-visit", methods=["POST"])
def schedule_visit():
    body = request.get_json(silent=True) or {}

    name = (body.get("name") or "").strip()
    phone = (body.get("phone") or "").strip()
    email = (body.get("email") or "").strip()
    property_id = (body.get("property_id") or "").strip()
    date = (body.get("preferred_date") or "").strip()
    time = (body.get("preferred_time") or "").strip()

    if not name:
        return error_response("Name is required.")
    if not is_valid_phone(phone):
        return error_response("A valid phone number is required.")
    if email and not is_valid_email(email):
        return error_response("Email address is invalid.")
    if not property_id:
        return error_response("property_id is required.")
    if not date:
        return error_response("Preferred date is required.")
    if not time:
        return error_response("Preferred time is required.")

    visit = {
        "name": name,
        "phone": phone,
        "email": email,
        "property_id": property_id,
        "property_name": body.get("property_name", ""),
        "preferred_date": date,
        "preferred_time": time,
        "customer_query": body.get("customer_query", ""),
        "requirement": body.get("requirement", ""),
        "status": "Pending",
    }

    # Saves to Google Sheets when configured; otherwise append_visit_request
    # falls back to a local CSV automatically (see google_sheets.py), so
    # this only fails on a genuine write error, never just because Sheets
    # isn't set up yet.
    try:
        sheets_client.append_visit_request(visit)
    except Exception as exc:
        print(f"[api/schedule-visit] failed to save visit request: {exc}")
        return error_response("Could not submit your request right now. Please try again in a moment.", 503)

    return jsonify({"success": True})


# ---------------------------------------------------------------------------
# EMI calculator
# ---------------------------------------------------------------------------
@app.route("/api/emi", methods=["POST"])
def emi():
    body = request.get_json(silent=True) or {}

    try:
        result = calculate_emi(
            loan_amount=body.get("loan_amount"),
            interest_rate=body.get("interest_rate"),
            tenure_years=body.get("tenure_years"),
        )
    except (ValueError, TypeError) as exc:
        return error_response(str(exc))

    return jsonify(result)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "true").lower() == "true"
    app.run(host="127.0.0.1", port=port, debug=debug)