# Credit Card Optimizer

A Python FastAPI application that replicates the credit card wallet optimizer spreadsheet, backed by PostgreSQL (Supabase), with Google Sheets integration and a roadmap scenario planner.

## Features

- **Wallet calculator** — replicates all spreadsheet formulas: Annual EV, 2nd-Year EV, SUB opportunity cost, points earned by currency group
- **Google Sheets sync** — reads inputs (card selection, spend, years) from your sheet; writes computed results back
- **Roadmap scenarios** — model future wallet states by assigning cards to date windows (e.g. "add Chase Sapphire Reserve on 2025-07-01, cancel Amex Gold on 2026-01-01")
- **REST API** — full CRUD for cards, spend categories, and scenarios; direct `/calculate` endpoint with no Sheets dependency

---

## Quick start

```bash
# 1. Configure environment (first time only)
cp credit_cards/.env.example credit_cards/.env
#    → fill in DATABASE_URL and GOOGLE_CREDENTIALS_PATH

# 2. Start the server (creates venv + installs deps automatically)
./start.sh

# 3. First-time only: seed the database from Financial.xlsx
./start.sh --seed
```

The server starts at **http://localhost:8000** — open [/docs](http://localhost:8000/docs) for the interactive Swagger UI.

```bash
# Other options
./start.sh --port 8080          # custom port
./start.sh --seed --port 8080   # seed + custom port
```

---

## Manual setup

### 1. Supabase (PostgreSQL)

1. Create a free project at [supabase.com](https://supabase.com)
2. In **Project Settings → Database**, find your connection string
3. Use the **Session mode** URI (port `5432`) for asyncpg:
   ```
   postgresql+asyncpg://postgres:[YOUR-PASSWORD]@db.[REF].supabase.co:5432/postgres
   ```

### 2. Environment variables

```bash
cp credit_cards/.env.example credit_cards/.env
# Edit .env and fill in DATABASE_URL and GOOGLE_CREDENTIALS_PATH
```

### 3. Google Sheets credentials

The app defaults to **OAuth 2.0** — no service account key file required.

1. Go to [Google Cloud Console](https://console.cloud.google.com) → **APIs & Services → Credentials**
2. Click **Create Credentials → OAuth client ID**, choose **Desktop app**, give it any name
3. Copy the **Client ID** and **Client Secret** into `credit_cards/.env`:
   ```
   GOOGLE_CLIENT_ID=YOUR_CLIENT_ID.apps.googleusercontent.com
   GOOGLE_CLIENT_SECRET=YOUR_CLIENT_SECRET
   ```
4. Enable the **Google Sheets API** and **Google Drive API** for your project
5. Share your Google Sheet with **your Google account** (the one you'll log in with)

On the first call to `/sync/read` or `/sync/write`, a browser window will open asking you to authorize access. After that, the token is cached in `.oauth_token.json` and reused automatically (never committed — it's in `.gitignore`).

> **Service account alternative:** If you have a key file, set `GOOGLE_AUTH_METHOD=service_account` and `GOOGLE_CREDENTIALS_PATH=credentials.json` in `.env` instead.

### 4. Python environment

```bash
cd "Credit Cards"
python3 -m venv .venv
source .venv/bin/activate
pip install -r credit_cards/requirements.txt
```

### 5. Seed the database

```bash
python -m credit_cards.seed_data
```

### 6. Run the API

```bash
uvicorn credit_cards.main:app --reload
```

---

## API Reference

### Cards

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/cards` | List all 26 cards with multipliers and credits |
| `GET` | `/cards/{id}` | Get a single card |
| `PATCH` | `/cards/{id}` | Update annual fee, CPP, SUB offer, etc. |

### Spend categories

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/spend` | List all 17 spend categories |
| `PUT` | `/spend/{category}` | Update annual spend for a category |

### Direct calculation

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/calculate` | Run wallet calculator without Google Sheets |

**Example request body:**
```json
{
  "years_counted": 2,
  "selected_card_ids": [2, 9],
  "spend_overrides": {
    "Dining": 9000,
    "Groceries": 6000
  }
}
```

### Google Sheets sync

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/sync/read` | Pull inputs from sheet → update DB spend categories |
| `POST` | `/sync/write` | Read sheet inputs, compute, and write results back |

**Example body for both sync endpoints:**
```json
{
  "spreadsheet_id": "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms",
  "sheet_name": "Credit Card Tool"
}
```

### Roadmap scenarios

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/scenarios` | List all scenarios |
| `POST` | `/scenarios` | Create a new scenario |
| `GET` | `/scenarios/{id}` | Get a scenario |
| `PATCH` | `/scenarios/{id}` | Update scenario metadata |
| `DELETE` | `/scenarios/{id}` | Delete a scenario |
| `POST` | `/scenarios/{id}/cards` | Add a card to a scenario |
| `DELETE` | `/scenarios/{id}/cards/{card_id}` | Remove a card from a scenario |
| `GET` | `/scenarios/{id}/results` | Compute wallet EV for the scenario |

**Example: create a 2-year roadmap scenario**
```json
POST /scenarios
{
  "name": "Add CSR July 2025",
  "description": "Upgrade wallet by adding Chase Sapphire Reserve mid-year",
  "as_of_date": "2025-07-01",
  "cards": [
    { "card_id": 7, "start_date": null, "end_date": null, "years_counted": 2 },
    { "card_id": 5, "start_date": "2025-07-01", "end_date": null, "years_counted": 2 }
  ]
}
```

**Get scenario results at a specific date:**
```
GET /scenarios/1/results?reference_date=2025-07-01
```

---

## Project structure

```
Credit Cards/
├── Financial.xlsx                  # Original spreadsheet (used for seeding)
└── credit_cards/
    ├── __init__.py
    ├── main.py                     # FastAPI app + all endpoints
    ├── calculator.py               # Pure Python formula engine
    ├── sheets.py                   # Google Sheets read/write adapter
    ├── models.py                   # SQLAlchemy ORM models
    ├── schemas.py                  # Pydantic v2 request/response schemas
    ├── database.py                 # Async PostgreSQL session factory
    ├── db_helpers.py               # DB → calculator dataclass converters
    ├── seed_data.py                # One-time data seeder from Financial.xlsx
    ├── requirements.txt
    └── .env.example
```

---

## Calculation logic

The engine in `calculator.py` mirrors all spreadsheet formulas:

| Spreadsheet row | Function |
|----------------|----------|
| Row 2: Annual EV | `calc_annual_ev` — SUB-amortized EV over `years_counted` |
| Row 3: Points Earned | `calc_total_points` — cumulative over `years_counted` |
| Row 4: Annual Point Earn | `calc_annual_point_earn` — category spend × multiplier + annual bonus |
| Row 5: 2nd Year+ EV | `calc_2nd_year_ev` — steady-state (no SUB) |
| Row 6: Credit Valuation | `calc_credit_valuation` — sum of all benefit credits |
| Row 13: SUB Extra Spend | `calc_sub_extra_spend` — gap to hit SUB threshold |
| Row 15: SUB Opp. Cost | `calc_sub_opportunity_cost` — points foregone on redirected spend |
| Row 16: Opp. Cost Abs. | `calc_opp_cost_abs` — absolute cross-card opportunity cost |
| Row 17: Avg. Multiplier | `calc_avg_spend_multiplier` — weighted average earn rate |

Special rules preserved from the spreadsheet:
- **Chase Freedom Unlimited / Flex**: earn rates are boosted (cpp = 2.0) when a Chase Sapphire Reserve, Preferred, or Ink Preferred is also selected
- **Delta cobrand cards**: points adjusted by `1/0.85` factor to normalize SkyMiles vs transferable currency
