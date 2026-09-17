# """
# chatbot.py

# Orchestrates the two-stage Gemini flow described in the spec:

#     User -> Gemini (extract structured filters) -> Python -> Property
#     Repository -> actual matching properties -> Gemini (natural language
#     response) -> User

# Gemini NEVER searches/invents property data or does EMI math - it only
# does NLU (stage 1) and phrasing the final reply from real data (stage 2).
# Python owns all filtering, session memory, and calculations.
# """

# import os
# import json
# import re

# from emi_calculator import calculate_emi
# from prompts import SYSTEM_PROMPT, EXTRACTION_PROMPT_TEMPLATE, RESPONSE_PROMPT_TEMPLATE

# # ---------------------------------------------------------------------------
# # In-memory session store.
# # sessions[session_id] = {
# #     "conversation_history": [{"role": "user"/"assistant", "text": "..."}],
# #     "user_information": {"name": "", "phone": "", "email": ""},
# #     "current_requirements": {...},
# #     "last_results": [...],       # last property search results shown
# # }
# # ---------------------------------------------------------------------------
# sessions = {}

# EMPTY_REQUIREMENTS = {
#     "intent": None,
#     "city": None,
#     "location": None,
#     "listing_type": None,
#     "property_type": None,
#     "bedrooms": None,
#     "bathrooms": None,
#     "min_price": None,
#     "max_price": None,
#     "budget_period": None,
#     "min_area_sqft": None,
#     "max_area_sqft": None,
#     "furnishing": None,
#     "parking": None,
#     "amenities": [],
#     "possession": None,
# }

# MAX_HISTORY_TURNS = 12  # keep prompts reasonably small


# def _get_session(session_id):
#     if session_id not in sessions:
#         sessions[session_id] = {
#             "conversation_history": [],
#             "user_information": {"name": "", "phone": "", "email": ""},
#             "current_requirements": dict(EMPTY_REQUIREMENTS),
#             "last_results": [],
#         }
#     return sessions[session_id]


# def _history_text(session):
#     turns = session["conversation_history"][-MAX_HISTORY_TURNS:]
#     lines = []
#     for turn in turns:
#         speaker = "User" if turn["role"] == "user" else "Assistant"
#         lines.append(f"{speaker}: {turn['text']}")
#     return "\n".join(lines) if lines else "(no previous messages)"


# def _strip_json_fences(text: str) -> str:
#     text = text.strip()
#     text = re.sub(r"^```(json)?", "", text.strip(), flags=re.IGNORECASE).strip()
#     text = re.sub(r"```$", "", text.strip()).strip()
#     return text


# class GeminiClient:
#     """Thin wrapper around the Gemini API so chatbot.py stays testable."""

#     def __init__(self):
#         self.api_key = os.getenv("GEMINI_API_KEY")
#         self._client = None

#     def is_configured(self):
#         return bool(self.api_key)

#     def _get_client(self):
#         if self._client is None:
#             from google import genai
#             self._client = genai.Client(api_key=self.api_key)
#         return self._client

#     def generate(self, prompt: str, system_instruction: str = None) -> str:
#         client = self._get_client()
#         model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

#         from google.genai import types
#         config = types.GenerateContentConfig(
#             system_instruction=system_instruction or SYSTEM_PROMPT,
#             temperature=0.3,
#         )
#         response = client.models.generate_content(
#             model=model,
#             contents=prompt,
#             config=config,
#         )
#         return (response.text or "").strip()


# gemini_client = GeminiClient()


# def _extract_requirements(session, user_message):
#     """Stage 1: ask Gemini to extract structured filters as JSON."""
#     prompt = EXTRACTION_PROMPT_TEMPLATE.format(
#         current_requirements=json.dumps(session["current_requirements"]),
#         conversation_history=_history_text(session),
#         user_message=user_message,
#     )

#     if not gemini_client.is_configured():
#         # Safe fallback so the app still runs without an API key configured.
#         return {"intent": "unknown"}

#     try:
#         raw = gemini_client.generate(prompt)
#         raw = _strip_json_fences(raw)
#         data = json.loads(raw)
#         return data
#     except Exception as exc:
#         print(f"[chatbot] extraction failed, falling back to unknown intent: {exc}")
#         return {"intent": "unknown"}


# def _merge_requirements(current, extracted):
#     merged = dict(current)
#     for key, value in extracted.items():
#         if key not in merged:
#             continue
#         if value is None:
#             continue
#         if key == "amenities" and not value:
#             continue
#         merged[key] = value
#     return merged


# def _requirements_to_filters(requirements: dict) -> dict:
#     filters = {}
#     for key in [
#         "city", "location", "listing_type", "property_type", "bedrooms",
#         "bathrooms", "min_price", "max_price", "min_area_sqft",
#         "max_area_sqft", "furnishing", "parking", "amenities", "possession",
#     ]:
#         value = requirements.get(key)
#         if value not in (None, "", []):
#             filters[key] = value
#     return filters


# def _generate_reply(session, user_message, intent, data_context):
#     prompt = RESPONSE_PROMPT_TEMPLATE.format(
#         conversation_history=_history_text(session),
#         user_message=user_message,
#         intent=intent,
#         data_context=json.dumps(data_context, default=str),
#     )

#     if not gemini_client.is_configured():
#         return _fallback_reply(intent, data_context)

#     try:
#         return gemini_client.generate(prompt)
#     except Exception as exc:
#         print(f"[chatbot] response generation failed, using fallback: {exc}")
#         return _fallback_reply(intent, data_context)


# def _fallback_reply(intent, data_context):
#     """Used only if Gemini is unavailable/misconfigured, so the app degrades gracefully."""
#     if intent == "property_search" or intent == "property_recommendation":
#         count = data_context.get("count", 0)
#         if count:
#             return f"I found {count} propert{'y' if count == 1 else 'ies'} matching your requirements. Take a look below."
#         return "I couldn't find a property matching all of those requirements. Would you like to increase your budget, change the location, or reduce the BHK requirement?"
#     if intent == "emi_calculation":
#         emi = data_context.get("emi")
#         if emi:
#             return (
#                 f"Your estimated monthly EMI is Rs. {emi['monthly_emi']:,}, "
#                 f"with total interest of Rs. {emi['total_interest']:,} "
#                 f"and total payment of Rs. {emi['total_payment']:,}."
#             )
#         return "Please share the loan amount, interest rate, and tenure so I can calculate your EMI."
#     if intent == "greeting":
#         return "Hello! I'm EstateEase AI. Tell me what kind of property you're looking for, and I'll help you find it."
#     if intent == "goodbye":
#         return "Thanks for chatting with EstateEase AI. Feel free to come back anytime you need help finding a property."
#     return "I can help you search properties, calculate EMI, schedule a visit, or connect you with an agent. What would you like to do?"


# def _parse_emi_fields_from_requirements(requirements, user_message):
#     """
#     Best-effort extraction of loan amount / rate / tenure for EMI intent.
#     Gemini's structured extraction focuses on property filters, so for EMI
#     we do a light regex pass over the raw message as a Python-side safety net.
#     """
#     text = user_message.lower()

#     loan_amount = None
#     rate = None
#     tenure = None

#     amount_match = re.search(r"(\d+(?:\.\d+)?)\s*(lakh|lakhs|lac|l\b|crore|cr\b)", text)
#     if amount_match:
#         value = float(amount_match.group(1))
#         unit = amount_match.group(2)
#         if unit.startswith("crore") or unit.startswith("cr"):
#             loan_amount = value * 10_000_000
#         else:
#             loan_amount = value * 100_000

#     rate_match = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
#     if rate_match:
#         rate = float(rate_match.group(1))

#     tenure_match = re.search(r"(\d+)\s*(year|years|yr|yrs)", text)
#     if tenure_match:
#         tenure = float(tenure_match.group(1))

#     return loan_amount, rate, tenure


# def handle_message(session_id, user_message, user_info, property_repository):
#     """
#     Main entry point called by app.py's /api/chat route.

#     Returns: dict with success, message, intent, properties, session_id
#     """
#     session = _get_session(session_id)

#     if user_info:
#         for field in ("name", "phone", "email"):
#             if user_info.get(field):
#                 session["user_information"][field] = user_info[field]

#     session["conversation_history"].append({"role": "user", "text": user_message})

#     extracted = _extract_requirements(session, user_message)
#     intent = extracted.get("intent") or "unknown"
#     session["current_requirements"] = _merge_requirements(
#         session["current_requirements"], extracted
#     )

#     properties = []
#     data_context = {}

#     if intent in ("property_search", "property_recommendation"):
#         filters = _requirements_to_filters(session["current_requirements"])
#         properties = property_repository.search_properties(filters)
#         session["last_results"] = properties
#         data_context = {"count": len(properties), "properties": properties[:10]}

#     elif intent == "property_details":
#         # Try to resolve which property the user means from context.
#         target = None
#         text = user_message.lower()
#         ordinal_map = {"first": 0, "1st": 0, "second": 1, "2nd": 1, "third": 2, "3rd": 2}
#         for word, idx in ordinal_map.items():
#             if word in text and idx < len(session["last_results"]):
#                 target = session["last_results"][idx]
#                 break
#         if target is None and session["last_results"]:
#             target = session["last_results"][0]
#         properties = [target] if target else []
#         data_context = {"count": len(properties), "properties": properties}

#     elif intent == "emi_calculation":
#         loan_amount, rate, tenure = _parse_emi_fields_from_requirements(
#             session["current_requirements"], user_message
#         )
#         if loan_amount and rate and tenure:
#             try:
#                 emi_result = calculate_emi(loan_amount, rate, tenure)
#                 data_context = {"emi": emi_result, "loan_amount": loan_amount, "rate": rate, "tenure": tenure}
#             except ValueError as exc:
#                 data_context = {"error": str(exc)}
#         else:
#             data_context = {"missing_fields": True}

#     elif intent in ("schedule_visit", "lead_generation", "contact_agent"):
#         data_context = {
#             "note": "User wants to proceed with this action; the frontend will show the appropriate form.",
#             "last_results_count": len(session["last_results"]),
#         }

#     else:
#         data_context = {}

#     reply_text = _generate_reply(session, user_message, intent, data_context)
#     session["conversation_history"].append({"role": "assistant", "text": reply_text})

#     return {
#         "success": True,
#         "message": reply_text,
#         "intent": intent,
#         "properties": properties,
#         "session_id": session_id,
#     }





"""
chatbot.py

Orchestrates the two-stage Gemini flow described in the spec:

    User -> Gemini (extract structured filters) -> Python -> Property
    Repository -> actual matching properties -> Gemini (natural language
    response) -> User

Gemini NEVER searches/invents property data or does EMI math - it only
does NLU (stage 1) and phrasing the final reply from real data (stage 2).
Python owns all filtering, session memory, and calculations.
"""

import os
import json
import re

from emi_calculator import calculate_emi
from prompts import SYSTEM_PROMPT, EXTRACTION_PROMPT_TEMPLATE, RESPONSE_PROMPT_TEMPLATE

# ---------------------------------------------------------------------------
# In-memory session store.
# sessions[session_id] = {
#     "conversation_history": [{"role": "user"/"assistant", "text": "..."}],
#     "user_information": {"name": "", "phone": "", "email": ""},
#     "current_requirements": {...},
#     "last_results": [...],       # last property search results shown
# }
# ---------------------------------------------------------------------------
sessions = {}

EMPTY_REQUIREMENTS = {
    "intent": None,
    "city": None,
    "location": None,
    "listing_type": None,
    "property_type": None,
    "bedrooms": None,
    "bathrooms": None,
    "min_price": None,
    "max_price": None,
    "budget_period": None,
    "min_area_sqft": None,
    "max_area_sqft": None,
    "furnishing": None,
    "parking": None,
    "amenities": [],
    "possession": None,
}

MAX_HISTORY_TURNS = 12  # keep prompts reasonably small


def _get_session(session_id):
    if session_id not in sessions:
        sessions[session_id] = {
            "conversation_history": [],
            "user_information": {"name": "", "phone": "", "email": ""},
            "current_requirements": dict(EMPTY_REQUIREMENTS),
            "last_results": [],
        }
    return sessions[session_id]


def _history_text(session):
    turns = session["conversation_history"][-MAX_HISTORY_TURNS:]
    lines = []
    for turn in turns:
        speaker = "User" if turn["role"] == "user" else "Assistant"
        lines.append(f"{speaker}: {turn['text']}")
    return "\n".join(lines) if lines else "(no previous messages)"


def _strip_json_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(json)?", "", text.strip(), flags=re.IGNORECASE).strip()
    text = re.sub(r"```$", "", text.strip()).strip()
    return text


class GeminiClient:
    """Thin wrapper around the Gemini API so chatbot.py stays testable."""

    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        self._client = None

    def is_configured(self):
        return bool(self.api_key)

    def _get_client(self):
        if self._client is None:
            from google import genai
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def generate(self, prompt: str, system_instruction: str = None) -> str:
        client = self._get_client()
        model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

        from google.genai import types
        config = types.GenerateContentConfig(
            system_instruction=system_instruction or SYSTEM_PROMPT,
            temperature=0.3,
        )
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=config,
        )
        return (response.text or "").strip()


gemini_client = GeminiClient()

# ---------------------------------------------------------------------------
# Plain-Python fallback extraction, used whenever Gemini is unconfigured OR
# fails (quota exhausted, network error, etc.) so the chatbot keeps working
# in a degraded-but-useful mode instead of just replying "I can help you..."
# on every message. Covers the demo dataset's cities; extend KNOWN_CITIES
# for a real client's coverage area.
# ---------------------------------------------------------------------------
KNOWN_CITIES = ["pune", "mumbai", "bengaluru", "bangalore", "delhi", "hyderabad", "chennai"]

GREETING_WORDS = {"hi", "hello", "hey", "namaste", "good morning", "good evening", "good afternoon"}
GOODBYE_WORDS = {"bye", "goodbye", "thanks", "thank you", "see you"}


def _parse_budget_to_inr(text: str):
    match = re.search(r"(\d+(?:\.\d+)?)\s*(lakh|lakhs|lac|l\b|crore|cr\b)", text)
    if not match:
        return None
    value = float(match.group(1))
    unit = match.group(2)
    if unit.startswith("crore") or unit.startswith("cr"):
        return value * 10_000_000
    return value * 100_000


def _fallback_extract_requirements(current_requirements: dict, user_message: str) -> dict:
    text = user_message.lower().strip()
    extracted = {}

    if any(word in text for word in GREETING_WORDS) and len(text) < 25:
        extracted["intent"] = "greeting"
        return extracted
    if any(word in text for word in GOODBYE_WORDS) and len(text) < 25:
        extracted["intent"] = "goodbye"
        return extracted
    if "emi" in text or ("loan" in text and ("%" in text or "interest" in text)):
        extracted["intent"] = "emi_calculation"
        return extracted
    if "visit" in text or "schedule" in text:
        extracted["intent"] = "schedule_visit"
        return extracted
    if "agent" in text or "call me" in text or "callback" in text or "contact" in text:
        extracted["intent"] = "contact_agent"
        return extracted
    if any(word in text for word in ["what is", "how does", "how do i", "documents needed"]):
        extracted["intent"] = "faq"
        return extracted

    # Otherwise, treat it as a property search / requirement refinement.
    extracted["intent"] = "property_search"

    for city in KNOWN_CITIES:
        if city in text:
            extracted["city"] = "Bengaluru" if city == "bangalore" else city.capitalize()
            break

    bhk_match = re.search(r"(\d+)\s*(?:bhk|bed|bedroom)", text)
    if bhk_match:
        extracted["bedrooms"] = int(bhk_match.group(1))

    if "rent" in text or "rental" in text or "lease" in text:
        extracted["listing_type"] = "Rent"
        extracted["budget_period"] = "monthly"
    elif "sale" in text or "buy" in text or "purchase" in text:
        extracted["listing_type"] = "Sale"

    budget = _parse_budget_to_inr(text)
    if budget is not None:
        extracted["max_price"] = budget
    else:
        # Bare numbers like "under 30000" (monthly rent, no lakh/crore unit).
        plain_amount = re.search(r"under\s*\u20b9?\s*(\d{4,9})", text)
        if plain_amount:
            extracted["max_price"] = float(plain_amount.group(1))

    for furnishing in ["semi-furnished", "unfurnished", "furnished"]:
        if furnishing in text:
            extracted["furnishing"] = furnishing.capitalize()
            break

    if "parking" in text:
        extracted["parking"] = True

    if "ready to move" in text or "ready-to-move" in text:
        extracted["possession"] = "Ready to Move"

    for ptype in ["apartment", "villa", "house", "studio", "plot", "flat"]:
        if ptype in text:
            extracted["property_type"] = "Apartment" if ptype == "flat" else ptype.capitalize()
            break

    return extracted


def _extract_requirements(session, user_message):
    """Stage 1: ask Gemini to extract structured filters as JSON."""
    if not gemini_client.is_configured():
        return _fallback_extract_requirements(session["current_requirements"], user_message)

    prompt = EXTRACTION_PROMPT_TEMPLATE.format(
        current_requirements=json.dumps(session["current_requirements"]),
        conversation_history=_history_text(session),
        user_message=user_message,
    )

    try:
        raw = gemini_client.generate(prompt)
        raw = _strip_json_fences(raw)
        data = json.loads(raw)
        return data
    except Exception as exc:
        print(f"[chatbot] Gemini extraction failed ({exc}); using local keyword-based fallback")
        return _fallback_extract_requirements(session["current_requirements"], user_message)


def _merge_requirements(current, extracted):
    merged = dict(current)
    for key, value in extracted.items():
        if key not in merged:
            continue
        if value is None:
            continue
        if key == "amenities" and not value:
            continue
        merged[key] = value
    return merged


def _requirements_to_filters(requirements: dict) -> dict:
    filters = {}
    for key in [
        "city", "location", "listing_type", "property_type", "bedrooms",
        "bathrooms", "min_price", "max_price", "min_area_sqft",
        "max_area_sqft", "furnishing", "parking", "amenities", "possession",
    ]:
        value = requirements.get(key)
        if value not in (None, "", []):
            filters[key] = value
    return filters


def _generate_reply(session, user_message, intent, data_context):
    if not gemini_client.is_configured():
        return _fallback_reply(intent, data_context)

    prompt = RESPONSE_PROMPT_TEMPLATE.format(
        conversation_history=_history_text(session),
        user_message=user_message,
        intent=intent,
        data_context=json.dumps(data_context, default=str),
    )

    try:
        return gemini_client.generate(prompt)
    except Exception as exc:
        print(f"[chatbot] response generation failed, using fallback: {exc}")
        return _fallback_reply(intent, data_context)


def _fallback_reply(intent, data_context):
    """Used whenever Gemini is unavailable/misconfigured/quota-exhausted, so the app degrades gracefully."""
    if intent == "property_search" or intent == "property_recommendation":
        count = data_context.get("count", 0)
        if count:
            return f"I found {count} propert{'y' if count == 1 else 'ies'} matching your requirements. Take a look below."
        return "I couldn't find a property matching all of those requirements. Would you like to increase your budget, change the location, or reduce the BHK requirement?"
    if intent == "emi_calculation":
        emi = data_context.get("emi")
        if emi:
            return (
                f"Your estimated monthly EMI is Rs. {emi['monthly_emi']:,}, "
                f"with total interest of Rs. {emi['total_interest']:,} "
                f"and total payment of Rs. {emi['total_payment']:,}."
            )
        return "Please share the loan amount, interest rate, and tenure so I can calculate your EMI."
    if intent == "greeting":
        return "Hello! I'm EstateEase AI. Tell me what kind of property you're looking for, and I'll help you find it."
    if intent == "goodbye":
        return "Thanks for chatting with EstateEase AI. Feel free to come back anytime you need help finding a property."
    if intent == "schedule_visit":
        return "Sure — let's get your visit scheduled. Please fill in your details in the form."
    if intent == "contact_agent" or intent == "lead_generation":
        return "Sure — share your details and an agent will reach out to you shortly."
    if intent == "faq":
        return "I can help with general questions like BHK, carpet area, or how EMI works — could you tell me more specifically what you'd like to know?"
    return "I can help you search properties, calculate EMI, schedule a visit, or connect you with an agent. What would you like to do?"


def _parse_emi_fields_from_requirements(requirements, user_message):
    """
    Best-effort extraction of loan amount / rate / tenure for EMI intent.
    Gemini's structured extraction focuses on property filters, so for EMI
    we do a light regex pass over the raw message as a Python-side safety net.
    """
    text = user_message.lower()

    loan_amount = None
    rate = None
    tenure = None

    amount_match = re.search(r"(\d+(?:\.\d+)?)\s*(lakh|lakhs|lac|l\b|crore|cr\b)", text)
    if amount_match:
        value = float(amount_match.group(1))
        unit = amount_match.group(2)
        if unit.startswith("crore") or unit.startswith("cr"):
            loan_amount = value * 10_000_000
        else:
            loan_amount = value * 100_000

    rate_match = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
    if rate_match:
        rate = float(rate_match.group(1))

    tenure_match = re.search(r"(\d+)\s*(year|years|yr|yrs)", text)
    if tenure_match:
        tenure = float(tenure_match.group(1))

    return loan_amount, rate, tenure


def handle_message(session_id, user_message, user_info, property_repository):
    """
    Main entry point called by app.py's /api/chat route.

    Returns: dict with success, message, intent, properties, session_id
    """
    session = _get_session(session_id)

    if user_info:
        for field in ("name", "phone", "email"):
            if user_info.get(field):
                session["user_information"][field] = user_info[field]

    session["conversation_history"].append({"role": "user", "text": user_message})

    extracted = _extract_requirements(session, user_message)
    intent = extracted.get("intent") or "unknown"
    session["current_requirements"] = _merge_requirements(
        session["current_requirements"], extracted
    )

    properties = []
    data_context = {}

    if intent in ("property_search", "property_recommendation"):
        filters = _requirements_to_filters(session["current_requirements"])
        properties = property_repository.search_properties(filters)
        session["last_results"] = properties
        data_context = {"count": len(properties), "properties": properties[:10]}

    elif intent == "property_details":
        # Try to resolve which property the user means from context.
        target = None
        text = user_message.lower()
        ordinal_map = {"first": 0, "1st": 0, "second": 1, "2nd": 1, "third": 2, "3rd": 2}
        for word, idx in ordinal_map.items():
            if word in text and idx < len(session["last_results"]):
                target = session["last_results"][idx]
                break
        if target is None and session["last_results"]:
            target = session["last_results"][0]
        properties = [target] if target else []
        data_context = {"count": len(properties), "properties": properties}

    elif intent == "emi_calculation":
        loan_amount, rate, tenure = _parse_emi_fields_from_requirements(
            session["current_requirements"], user_message
        )
        if loan_amount and rate and tenure:
            try:
                emi_result = calculate_emi(loan_amount, rate, tenure)
                data_context = {"emi": emi_result, "loan_amount": loan_amount, "rate": rate, "tenure": tenure}
            except ValueError as exc:
                data_context = {"error": str(exc)}
        else:
            data_context = {"missing_fields": True}

    elif intent in ("schedule_visit", "lead_generation", "contact_agent"):
        data_context = {
            "note": "User wants to proceed with this action; the frontend will show the appropriate form.",
            "last_results_count": len(session["last_results"]),
        }

    else:
        data_context = {}

    reply_text = _generate_reply(session, user_message, intent, data_context)
    session["conversation_history"].append({"role": "assistant", "text": reply_text})

    return {
        "success": True,
        "message": reply_text,
        "intent": intent,
        "properties": properties,
        "session_id": session_id,
    }