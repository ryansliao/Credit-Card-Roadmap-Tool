# Credit Card Optimizer

A full-stack web application for modeling the expected value (EV) of any combination of credit cards across multiple issuers. Built with FastAPI, React, and deployed on Azure.

## Features

- **Wallet Tool** — single tab to manage wallets tied to a user. Each wallet has cards added at a specific date with optional sign-up bonus (SUB) and minimum-spend overrides. Set a projection time frame (years and months), adjust annual spend, and calculate EV and **expected opportunity cost** of spending toward each card’s SUB (taking away from points earned on other cards in that wallet).
- **Issuer ecosystem modeling** — cards automatically upgrade from cashback to transferable-point earning when a premium anchor card (e.g. Sapphire Reserve, Citi Strata Elite) is present in the wallet; generalizes across all supported issuers
- **Opportunity cost in the UI** — per-card SUB opportunity cost (dollar value foregone on the rest of the wallet) is shown in the results
- **Card library** — browse all cards with their multipliers, credits, and SUB details
- **REST API** — full CRUD for cards, currencies, spend categories, wallets, and wallet cards; interactive docs at `/docs`

---

## Local development

### 1. Prerequisites

- Python 3.11+
- Node.js 18+

### 2. Environment variables

```bash
cp .env.example .env
```

Edit `.env` and fill in `DATABASE_URL`. For local dev, any PostgreSQL database works:

```ini
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/creditcards
```

### 3. Set up PostgreSQL (one-time)

Install and start PostgreSQL if you haven't already:

```bash
brew install postgresql@14
brew services start postgresql@14
createuser -s postgres   # create the default role
createdb creditcards     # create the database
```

### 4. Seed the database (one-time)

```bash
python3 -m venv .venv && source .venv/bin/activate
python3 -m pip install -r backend/requirements.txt
cd backend && python3 -m app.seed_data && cd ..
```

This populates the default user (id=1), issuers, currencies, ecosystem boosts, all cards, multipliers, credits, and default spend categories from the DataFrames in `backend/app/seed_data.py` (edit those or load from CSV/Excel via pandas).

### 5. Start both servers

```bash
./scripts/dev.sh
```

This starts:
- **FastAPI** at `http://localhost:8000` (Swagger UI at `/docs`)
- **Vite dev server** at `http://localhost:5173` (proxies `/api` → FastAPI)

Open **http://localhost:5173** in your browser.

---

## Azure deployment

### Resources needed

| Resource | Tier | Notes |
|---|---|---|
| Azure App Service Plan | B1 (Linux) | Python 3.12 |
| Azure App Service | — | Hosts FastAPI + built React app |
| Azure Database for PostgreSQL Flexible Server | Burstable B1ms | Sufficient for personal use |

### Step 1 — Provision Azure PostgreSQL

1. In the Azure Portal, create an **Azure Database for PostgreSQL Flexible Server**
2. Note the server name, username, and password
3. Under **Networking**, allow connections from Azure services and your local IP
4. Connection string format:
   ```
   postgresql+asyncpg://[user]@[server]:[password]@[server].postgres.database.azure.com:5432/postgres?ssl=require
   ```

### Step 2 — Seed the database from local machine

Set `DATABASE_URL` in your local `.env` to the Azure connection string, then:

```bash
source .venv/bin/activate
cd backend && python3 -m app.seed_data && cd ..
```

### Step 3 — Build the React frontend

```bash
cd frontend
npm install
npm run build
```

The built output lands in `frontend/dist/`, which FastAPI serves automatically.

### Step 4 — Deploy to Azure App Service

Using Azure CLI:

```bash
# Create resource group (if needed)
az group create --name credit-card-rg --location eastus

# Create App Service Plan
az appservice plan create \
  --name credit-card-plan \
  --resource-group credit-card-rg \
  --sku B1 \
  --is-linux

# Create Web App (Python 3.12)
az webapp create \
  --name credit-card-optimizer \
  --resource-group credit-card-rg \
  --plan credit-card-plan \
  --runtime "PYTHON:3.12"

# Set environment variables
az webapp config appsettings set \
  --name credit-card-optimizer \
  --resource-group credit-card-rg \
  --settings \
    DATABASE_URL="postgresql+asyncpg://..." \
    ALLOWED_ORIGINS="https://credit-card-optimizer.azurewebsites.net" \
    APP_ENV="production"

# Set startup command
az webapp config set \
  --name credit-card-optimizer \
  --resource-group credit-card-rg \
  --startup-file "bash scripts/azure_startup.sh"

# Deploy (zip deploy from repo root)
zip -r deploy.zip . \
  --exclude ".git/*" \
  --exclude ".venv/*" \
  --exclude "frontend/node_modules/*" \
  --exclude "secrets/*" \
  --exclude "*.pyc" \
  --exclude "__pycache__/*"

az webapp deploy \
  --name credit-card-optimizer \
  --resource-group credit-card-rg \
  --src-path deploy.zip \
  --type zip

rm deploy.zip
```

The app will be live at `https://credit-card-optimizer.azurewebsites.net`.

---

## Project structure

```
Credit Card Tool/
├── .env.example                    # Template — copy to .env and fill in
├── .gitignore
├── README.md
│
├── backend/                        # Python backend
│   ├── README.md                   # Backend architecture + API reference
│   ├── app/
│   │   ├── main.py                 # FastAPI app, all endpoints, SPA serving
│   │   ├── calculator.py           # Pure-Python EV engine (no DB dependency)
│   │   ├── models.py               # SQLAlchemy ORM: Issuer, Currency, EcosystemBoost, Card, …
│   │   ├── schemas.py              # Pydantic v2 request/response schemas
│   │   ├── database.py             # Async PostgreSQL session factory + Azure Identity
│   │   ├── db_helpers.py           # DB → calculator dataclass converters
│   │   └── seed_data.py            # One-time seeder (pandas DataFrames)
│   └── requirements.txt
│
├── frontend/                       # React app (Vite + TypeScript + Tailwind)
│   ├── src/
│   │   ├── api/client.ts           # Typed API client
│   │   ├── pages/
│   │   │   ├── Calculator.tsx      # Wallet calculator
│   │   │   ├── Scenarios.tsx       # Scenario manager
│   │   │   └── Cards.tsx           # Card library browser
│   │   └── components/
│   │       ├── CardGrid.tsx        # Toggleable card selector
│   │       ├── SpendTable.tsx      # Editable spend categories
│   │       └── WalletSummary.tsx   # EV results display
│   └── dist/                       # Built output (served by FastAPI in production)
│
├── data/                           # Reference data (generated)
│   └── reference.xlsx              # One tab per seed class; edit and seed loads from it
│
├── scripts/
│   ├── dev.sh                      # Local dev launcher (API + React)
│   ├── azure_startup.sh            # Azure App Service startup command
│
└── docs/
    └── (optional) CSV/Excel        # Can be loaded in seed_data.py via pd.read_csv etc.
```

---

See [`backend/README.md`](backend/README.md) for the full API reference, data model, and calculation engine documentation.
