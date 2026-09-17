"""
google_sheets.py

Stores customer data (leads, chat history, visit requests) in Google
Sheets - kept completely separate from property data.

Two ways to connect to Sheets are supported, tried in this order:

1. GOOGLE_SHEETS_WEBHOOK_URL
   A Google Apps Script "Web app" deployment URL. This needs NO Google
   Cloud project, no service account, and no credentials.json - you
   write a small script directly inside the Sheet (Extensions > Apps
   Script), deploy it as a web app, and paste the resulting URL here.
   This is the simplest option and is tried first if set.

2. GOOGLE_SHEET_ID + GOOGLE_CREDENTIALS_FILE (gspread / service account)
   The original method, needs a Google Cloud project with the Sheets +
   Drive APIs enabled and a service-account credentials.json. More
   setup, but doesn't require deploying anything inside the sheet.

Creates/uses three tabs (worksheets) inside the same spreadsheet:
    Leads
    ChatHistory
    VisitRequests

LOCAL FALLBACK:
If neither method is configured, or a write to either fails, every
append_* method automatically falls back to writing the same rows into
local CSV files under ./local_data/, so leads and visit requests are
never silently lost during local development or a demo.
"""

import os
import csv
import json
import datetime

import requests

LOCAL_DATA_DIR = os.getenv("LOCAL_DATA_DIR", "local_data")

LEADS_HEADERS = [
    "Timestamp", "Name", "Phone", "Email", "User Query", "Requirement",
    "Property ID", "Property Name", "City", "Location", "Budget",
    "Listing Type", "Bedrooms", "Lead Status",
]

CHAT_HISTORY_HEADERS = [
    "Timestamp", "Session ID", "User Name", "User Phone", "User Email",
    "User Query", "AI Response", "Intent",
]

VISIT_REQUESTS_HEADERS = [
    "Timestamp", "Name", "Phone", "Email", "Property ID", "Property Name",
    "Preferred Date", "Preferred Time", "Customer Query", "Requirement", "Status",
]


class GoogleSheetsClient:
    """
    Lazily connects to Google Sheets on first use, so the app can start
    even if Sheets isn't configured yet (e.g. local Excel-only testing).
    """

    def __init__(self):
        self.webhook_url = os.getenv("GOOGLE_SHEETS_WEBHOOK_URL")

        self.sheet_id = os.getenv("GOOGLE_SHEET_ID")
        self.credentials_file = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")
        self._spreadsheet = None

        self._webhook_enabled = bool(self.webhook_url)
        self._gspread_enabled = bool(self.sheet_id) and os.path.exists(self.credentials_file)

    def is_configured(self):
        return self._webhook_enabled or self._gspread_enabled

    # ------------------------------------------------------------------
    # Method 1: Apps Script webhook (no Cloud project needed)
    # ------------------------------------------------------------------
    def _append_via_webhook(self, sheet_name, headers, row):
        response = requests.post(
            self.webhook_url,
            data=json.dumps({"sheet": sheet_name, "headers": headers, "row": row}),
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        response.raise_for_status()

    # ------------------------------------------------------------------
    # Method 2: gspread + service account
    # ------------------------------------------------------------------
    def _connect(self):
        if self._spreadsheet is not None:
            return self._spreadsheet

        if not self._gspread_enabled:
            raise RuntimeError("Google Sheets (gspread) is not configured.")

        import gspread
        from google.oauth2.service_account import Credentials

        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = Credentials.from_service_account_file(self.credentials_file, scopes=scopes)
        client = gspread.authorize(creds)
        self._spreadsheet = client.open_by_key(self.sheet_id)
        return self._spreadsheet

    def _get_or_create_worksheet(self, title, headers):
        spreadsheet = self._connect()
        try:
            worksheet = spreadsheet.worksheet(title)
        except Exception:
            worksheet = spreadsheet.add_worksheet(title=title, rows=1000, cols=len(headers))
            worksheet.append_row(headers)
        return worksheet

    def _append_via_gspread(self, sheet_name, headers, row):
        worksheet = self._get_or_create_worksheet(sheet_name, headers)
        worksheet.append_row(row)

    def _timestamp(self):
        return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    # ------------------------------------------------------------------
    # Local CSV fallback (used whenever nothing above is configured)
    # ------------------------------------------------------------------
    def _append_local_csv(self, filename, headers, row):
        os.makedirs(LOCAL_DATA_DIR, exist_ok=True)
        path = os.path.join(LOCAL_DATA_DIR, filename)
        file_exists = os.path.exists(path)
        with open(path, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(headers)
            writer.writerow(row)

    # ------------------------------------------------------------------
    # Shared dispatch: webhook -> gspread -> local CSV
    # ------------------------------------------------------------------
    def _append_row(self, sheet_name, headers, row, local_filename):
        if self._webhook_enabled:
            try:
                self._append_via_webhook(sheet_name, headers, row)
                return
            except Exception as exc:
                print(f"[GoogleSheetsClient] webhook append to '{sheet_name}' failed, trying next method: {exc}")

        if self._gspread_enabled:
            try:
                self._append_via_gspread(sheet_name, headers, row)
                return
            except Exception as exc:
                print(f"[GoogleSheetsClient] gspread append to '{sheet_name}' failed, falling back to local CSV: {exc}")

        self._append_local_csv(local_filename, headers, row)

    # ------------------------------------------------------------------
    # Public methods used by app.py / chatbot.py
    # ------------------------------------------------------------------
    def append_lead(self, lead: dict):
        row = [
            self._timestamp(),
            lead.get("name", ""),
            lead.get("phone", ""),
            lead.get("email", ""),
            lead.get("user_query", ""),
            lead.get("requirement", ""),
            lead.get("property_id", ""),
            lead.get("property_name", ""),
            lead.get("city", ""),
            lead.get("location", ""),
            lead.get("budget", ""),
            lead.get("listing_type", ""),
            lead.get("bedrooms", ""),
            lead.get("lead_status", "New"),
        ]
        self._append_row("Leads", LEADS_HEADERS, row, "leads.csv")

    def append_chat_history(self, entry: dict):
        row = [
            self._timestamp(),
            entry.get("session_id", ""),
            entry.get("user_name", ""),
            entry.get("user_phone", ""),
            entry.get("user_email", ""),
            entry.get("user_query", ""),
            entry.get("ai_response", ""),
            entry.get("intent", ""),
        ]
        self._append_row("ChatHistory", CHAT_HISTORY_HEADERS, row, "chat_history.csv")

    def append_visit_request(self, visit: dict):
        row = [
            self._timestamp(),
            visit.get("name", ""),
            visit.get("phone", ""),
            visit.get("email", ""),
            visit.get("property_id", ""),
            visit.get("property_name", ""),
            visit.get("preferred_date", ""),
            visit.get("preferred_time", ""),
            visit.get("customer_query", ""),
            visit.get("requirement", ""),
            visit.get("status", "Pending"),
        ]
        self._append_row("VisitRequests", VISIT_REQUESTS_HEADERS, row, "visit_requests.csv")