# CardSolver

A personal finance tool for evaluating credit card wallet combinations. Configure your spending profile and a set of cards, then calculate expected annual value — across points/miles earned, statement credits, and sign-up bonuses — projected over a 1-5 year horizon.

## Features

- **Wallet management** — create wallets, add cards with open/close dates, and configure SUB overrides
- **Multi-year EV projection** — simple or date-segmented calculation paths with optional reference date ranges
- **Category allocation** — spend categories awarded to highest-earning card(s) with tie-splitting
- **Currency upgrades** — automatic conversion when a wallet contains both base and target currencies (e.g. UR Cash + Chase UR)
- **SUB tracking** — projected earn dates, opportunity cost modeling, and manual earned toggles
- **Roadmap** — 5/24 status, issuer rule violation alerts (Chase 5/24, Amex 1/90, Citi 1/8, Citi 2/65)
- **Per-wallet overrides** — CPP, statement credit valuations, and multiplier overrides per card/category
- **Point balance tracking** — portfolio value estimates across all tracked currencies

## Tech Stack

- **Backend**: Python, FastAPI, SQLAlchemy (async), PostgreSQL
- **Frontend**: React 18, TypeScript, Tailwind CSS, React Query

---

## Local Development

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL

### Environment Variables

```bash
cp .env.example .env
```

Edit `.env` and set:

```ini
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/creditcards
VITE_GOOGLE_CLIENT_ID=your-google-oauth-client-id
```

### Set Up PostgreSQL (one-time)

```bash
brew install postgresql@14
brew services start postgresql@14
createuser -s postgres
createdb creditcards
```

### Start Both Servers

```bash
./scripts/dev.sh
```

This starts:
- **FastAPI** at `http://localhost:8000` (Swagger UI at `/docs`)
- **Vite dev server** at `http://localhost:5173` (proxies `/api` to FastAPI)

Tables are created automatically on startup. Reference data (cards, issuers, currencies, multipliers, credits) is managed via admin endpoints (`/admin/*`).

---

## Azure Deployment

### Resources

| Resource | Tier | Notes |
|---|---|---|
| Azure App Service Plan | B1 (Linux) | Python 3.12 |
| Azure App Service | -- | Hosts FastAPI + built React app |
| Azure Database for PostgreSQL | Burstable B1ms | Flexible Server |

### Deploy

```bash
# Build frontend
cd frontend && npm install && npm run build && cd ..

# Set Azure app settings
az webapp config appsettings set \
  --name cardsolver \
  --resource-group credit-card-rg \
  --settings \
    DATABASE_URL="postgresql+asyncpg://..." \
    ALLOWED_ORIGINS="https://cardsolver.azurewebsites.net"

# Set startup command
az webapp config set \
  --name cardsolver \
  --resource-group credit-card-rg \
  --startup-file "bash scripts/azure_startup.sh"

# Zip deploy
zip -r deploy.zip . \
  --exclude ".git/*" ".venv/*" "frontend/node_modules/*" "*.pyc" "__pycache__/*"
az webapp deploy \
  --name cardsolver \
  --resource-group credit-card-rg \
  --src-path deploy.zip --type zip
rm deploy.zip
```

---

## Project Structure

```
backend/
  app/
    main.py              # App creation, lifespan, middleware, SPA serving
    calculator/          # Pure calculation engine (no DB dependency)
      types.py           #   dataclasses (CardData, WalletResult, …)
      multipliers.py     #   category multiplier + % bonus factors
      currency.py        #   CPP, transfer enablement
      allocation.py      #   simple-path winner-takes-category
      credits.py         #   credits, SUB opp cost, total points
      secondary.py       #   Bilt-style secondary + simple-path EV
      sub_planner.py     #   EDF SUB spend scheduler
      segments.py        #   segment builder + per-segment earn
      segment_lp.py      #   scipy LP + greedy fallback
      segmented_ev.py    #   time-weighted per-card net value
      compute.py         #   foreign split + compute_wallet orchestrator
    card_data_transforms.py # Pure CardData transforms (apply_* wallet overrides)
    models.py            # Re-export shim over the dal/ package
    dal/                 # SQLAlchemy ORM models organised by domain
    schemas/             # Pydantic v2 request/response schemas (by domain, mirrors dal/)
    database.py          # Engine setup, session factory, migrations
    date_utils.py        # Date utilities + SUB-window math
    services/            # Data access layer (CalculatorDataService, …)
    routers/             # FastAPI route modules (admin/, reference/, wallet/)
  migrations/            # Idempotent SQL migrations (run on startup)
  tests/                 # pytest snapshot tests against the calculator
  docs/                  # Backend design docs

frontend/src/
  App.tsx              # Router, Nav, SignInDropdown, AuthGate
  api/client.ts        # Typed API client
  auth/AuthContext.tsx  # Google OAuth provider, useAuth() hook
  utils/format.ts      # Shared formatting utilities
  pages/
    Home.tsx           # Public landing page
    Profile.tsx        # Profile settings (authenticated)
    WalletTool/        # Main application UI
      hooks/           # Shared React Query hooks
      lib/             # Query keys, form utilities
      components/      # Cards, spend, summary, wallet, roadmap panels
```

---

## Architecture Notes

- **Authentication** — Google OAuth sign-in via navbar dropdown; protected routes redirect to the landing page
- **Reference data** — cards, issuers, currencies, multipliers, and credits are managed via `/admin/*` endpoints; no seed files or xlsx import
- **Calculation engine** — `app.calculator` is a pure subpackage with no DB access; data is loaded by `CalculatorDataService` and then shaped by the pure `apply_*` transforms in `card_data_transforms.py` before being handed to the calculator. Public surface (`compute_wallet`, `CardData`, …) is re-exported from `calculator/__init__.py` so callers import it as `from app.calculator import X`. See `backend/docs/calculator-refactor.md` for the module boundaries.
- **Regression test** — `backend/tests/test_calculator_snapshot.py` pins `compute_wallet` output for simple-path and segmented-path fixtures (pure Python `CardData`, no DB dependency) against committed JSON snapshots in `backend/tests/fixtures/`; run with `cd backend && ../.venv/bin/python -m pytest tests/test_calculator_snapshot.py` before shipping any calculator change, and with `--snapshot-update` to intentionally refresh the fixtures.
- **SPA serving** — in production, FastAPI serves the built frontend from `frontend/dist/`
