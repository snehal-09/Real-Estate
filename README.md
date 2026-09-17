# EstateEase AI — Chat Widget

A standalone, embeddable floating chat button (bottom-right) that gives
any real-estate website a Gemini-powered AI assistant — property search,
EMI calculator, lead capture, and visit scheduling — without needing a
full marketing site around it. Built as a reusable freelance product:
swap in a client's brand, property database, and Google Sheet, and it's
ready to demo or deploy.

`templates/index.html` in this project is just a blank demo page that
loads the widget so you can see it working. To add the widget to an
existing client website, copy the widget markup from that file (the
`<button class="ee-chat-fab">` through the three `<div class="ee-modal">`
blocks), plus `static/widget.css` and `static/widget.js`, onto their
existing pages — all widget classes are prefixed `ee-` so they won't
collide with the host site's own styles.

## Features

- Natural-language property search chatbot that understands Indian
  real-estate terms (BHK, lakh, crore, rent vs. sale, furnishing, etc.)
- Property search, filtering, and recommendations
- EMI calculator (loan amount, interest rate, tenure → monthly EMI, total
  interest, total payment)
- Lead capture ("talk to an agent") and visit scheduling, saved to Google
  Sheets
- Multi-turn conversation memory per chat session
- Zero-hallucination guarantee: the AI only ever describes properties that
  exist in the connected database — it never invents prices, locations,
  or amenities
- Pluggable property data source: Excel (demo), MongoDB, MySQL,
  PostgreSQL, or a REST API — switchable via one environment variable,
  with no changes to the chatbot or website code
- Responsive, professional dark-navy/gold design — desktop, tablet, and
  mobile

## Tech Stack

Python · Flask · Google Gemini · Pandas · MongoDB / MySQL / PostgreSQL
(optional) · Google Sheets (gspread) · HTML · CSS · JavaScript

No React, no Node, no Docker, no separate frontend server — a single
Flask app serves both the website and the API.

## Installation

```bash
python -m venv venv
```

Activate it:

Windows:
```bash
venv\Scripts\activate
```

macOS / Linux:
```bash
source venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Configure your environment:

```bash
cp .env.example .env
```

Then edit `.env` and add at minimum your `GEMINI_API_KEY` (the app will
still run and serve properties without it, but the chatbot's natural
language understanding needs it).

If you want leads / chat history / visit requests saved to Google Sheets,
add your service-account `credentials.json` to the project root and set
`GOOGLE_SHEET_ID` in `.env`. Share the target spreadsheet with the
service account's email address.

Run the app:

```bash
python app.py
```

Open:

```
http://127.0.0.1:5000
```

## Project Structure

```
real-estate-chatbot/
│
├── app.py                   Flask app + all API routes
├── chatbot.py                Two-stage Gemini flow + session memory
├── property_repository.py    Common repository interface + factory
├── repository_utils.py       Shared normalization / filter-matching helpers
├── excel_database.py         Demo data source (Excel via pandas)
├── mongo_database.py         MongoDB connector
├── mysql_database.py         MySQL connector
├── postgres_database.py      PostgreSQL connector
├── api_database.py           REST API connector
├── google_sheets.py          Leads / chat history / visit requests
├── prompts.py                Gemini system + extraction + response prompts
├── emi_calculator.py         EMI math (pure Python, never delegated to AI)
│
├── real_estate_properties.xlsx   Demo property database (15 sample listings)
│
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
│
├── templates/
│   └── index.html         Blank demo page hosting just the widget
│
└── static/
    ├── widget.css         Embeddable widget styles (all classes prefixed "ee-")
    └── widget.js          Embeddable widget logic (chat, lead form, visit form)
```

## Data Source Configuration

The chatbot's business logic never talks to Excel, MongoDB, MySQL,
PostgreSQL, or an API directly — it only calls `property_repository`,
which is chosen at startup by the `DATA_SOURCE` environment variable.
Switching data sources never requires touching `chatbot.py`, `app.py`,
or the frontend.

### Excel (demo default)

```env
DATA_SOURCE=excel
PROPERTY_EXCEL_FILE=real_estate_properties.xlsx
```

### MongoDB

```env
DATA_SOURCE=mongodb
MONGODB_URI=mongodb+srv://username:password@cluster.mongodb.net/
MONGODB_DATABASE=real_estate
MONGODB_COLLECTION=properties
```

### MySQL

```env
DATA_SOURCE=mysql
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=username
MYSQL_PASSWORD=password
MYSQL_DATABASE=real_estate
MYSQL_PROPERTIES_TABLE=properties
```

### PostgreSQL

```env
DATA_SOURCE=postgresql
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=username
POSTGRES_PASSWORD=password
POSTGRES_DATABASE=real_estate
POSTGRES_PROPERTIES_TABLE=properties
```

### REST API

```env
DATA_SOURCE=api
PROPERTY_API_URL=https://example.com/api/properties
PROPERTY_API_KEY=your_api_key
```

If a client's database uses different field names than EstateEase AI's
normalized schema (`property_id`, `title`, `bedrooms`, `price_inr`,
`city`, etc.), add a mapping in the `FIELD_MAP` dictionary at the top of
the relevant connector file (e.g. `mongo_database.py`) rather than asking
the client to rename their columns.

## Selling to a New Client

To reuse this product for a new real-estate company:

1. Ask where their property data lives (Excel, MongoDB, MySQL,
   PostgreSQL, CRM, REST API) and configure the matching `DATA_SOURCE`.
2. Point `GOOGLE_SHEET_ID` at their own spreadsheet for leads/visits.
3. Set their `GEMINI_API_KEY`.
4. Update branding — colors, logo text, and copy — in `static/style.css`
   and `templates/index.html`.

No changes to the chatbot or repository logic are required.

## Security Notes

- Database credentials, API keys, and Google service-account credentials
  are read only from environment variables / `credentials.json` on the
  server — never sent to the frontend or to Gemini.
- `/api/health` reports connection status only (`connected` /
  `unavailable` / `configured` / `not configured`) — never raw
  credentials or connection strings.
- All form input (leads, visit requests, EMI inputs) is validated
  server-side.

## Testing Checklist

- `2 BHK in Pune under 80 lakh` → property search with extracted filters
- `2 BHK for rent under 30k in Pune` → correctly interpreted as a rental
  budget, not a sale price
- `Show me 2 BHK in Pune` → then `Under 80 lakh` → filters should
  combine across turns
- `Calculate EMI for 50 lakh at 8.5% for 20 years` → EMI figures
- `I want an agent to call me` → lead saved to the **Leads** tab in
  Google Sheets
- `I want to visit the first property` → visit request saved to the
  **VisitRequests** tab
- Switch `DATA_SOURCE` from `excel` to another source and confirm
  `/api/search` and the chatbot keep working unmodified
