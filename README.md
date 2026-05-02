# Finance Dashboard

Local finance dashboard that syncs a Google Sheet into PostgreSQL and serves a database-backed dashboard through FastAPI.

## What This Setup Does

1. Authenticates to Google Sheets with OAuth.
2. Reads each finance tab from the configured spreadsheet.
3. Upserts rows into PostgreSQL and soft-deletes database rows that were removed from the sheet.
4. Serves the dashboard HTML from FastAPI.
5. Exposes `/api/v1/dashboard-data` for all KPI, chart, table, and comparison values.
6. Lets the dashboard trigger a fresh Google Sheet sync through the `Refresh DB` button.

## Local Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Update `.env` with your local PostgreSQL URL and Google Sheet URL.

Run OAuth once:

```bash
source venv/bin/activate
python auth_google.py
```

Start the dashboard:

```bash
source venv/bin/activate
uvicorn main:app --host 127.0.0.1 --port 8000
```

Open [http://127.0.0.1:8000/](http://127.0.0.1:8000/).

## Core Commands

| Command | Purpose |
|---|---|
| `python auth_google.py` | Creates or refreshes the OAuth token used to read Google Sheets. |
| `uvicorn main:app --host 127.0.0.1 --port 8000` | Runs the local API and dashboard. |
| `POST /api/v1/sync` | Refreshes PostgreSQL from Google Sheets. |
| `GET /api/v1/dashboard-data` | Returns all dashboard values from PostgreSQL. |
| `GET /api/v1/dashboard-data/available-years` | Returns years present in database-backed finance data. |

## Database Structure

| Table | Purpose | Key Fields | Relationships |
|---|---|---|---|
| `revenue_streams` | Revenue stream reference data. | `revenue_stream_id`, `stream_name`, `stream_type`, `pricing_model` | One revenue stream has many projects. |
| `employees` | Employee reference data. | `employee_id`, `full_name`, `department`, `employment_type` | One employee can own projects, overhead rows, and salary rows. |
| `projects` | Client/project master data. | `project_id`, `project_name`, `client_name`, `contracted_budget` | Belongs to one revenue stream and optional responsible employee. Has many revenue and COGS rows. |
| `revenue_transactions` | Invoiced revenue. | `transaction_id`, `invoice_number`, `date`, `project_id`, `amount` | Belongs to one project. |
| `cogs_transactions` | Product/project-related costs. | `transaction_id`, `invoice_number`, `date`, `project_id`, `amount` | Belongs to one project. |
| `overhead_transactions` | Operational overhead costs. | `transaction_id`, `date`, `overhead_category`, `amount` | Optionally belongs to one employee. |
| `bank_cash_movements` | Bank balance and cash movements. | `movement_id`, `date`, `amount`, `balance_after`, `is_frozen` | Used for gross cash, frozen cash, and net cash calculations. |
| `salaries` | Salary cost records. | `salary_id`, `date`, `gross_salary`, `employee_id` | Belongs to one employee. |
| `sync_logs` | Sync audit history. | `sync_id`, `table_name`, `rows_inserted`, `rows_updated`, `rows_deleted` | Independent audit table. |

All user-facing dashboard queries filter out rows where `is_deleted = true`.

## Dashboard Definitions

| Dashboard Area | Metric / Chart | Database Fields Used | Calculation |
|---|---|---|---|
| Global filters | Year / Quarter / Month / Week | Date fields across revenue, COGS, overhead, bank movements, salaries | Filters all dashboard queries to the selected explicit period. |
| Comparison badges | Percent change | Same fields as each metric | `(current period value - previous comparable period value) / abs(previous comparable period value) * 100`. Year compares to previous year, quarter to previous quarter, month to previous month, week to previous ISO week. |
| Forecast Financial Position | Revenue line | `revenue_transactions.date`, `amount` | Sum revenue by dashboard bucket. |
| Forecast Financial Position | COGS line | `cogs_transactions.date`, `amount` | Sum COGS by dashboard bucket. |
| Forecast Financial Position | Overhead line | `overhead_transactions.date`, `amount` | Sum overhead by dashboard bucket. |
| Forecast Financial Position | Profit line | Revenue, COGS, overhead | `revenue - cogs - overhead` by bucket. |
| Net cash position | Gross cash position | Latest `bank_cash_movements.balance_after` | Latest non-deleted bank balance. |
| Net cash position | Temporary frozen cash | `bank_cash_movements.amount`, `is_frozen` | Sum frozen movements inside selected period, displayed as absolute value. |
| Net cash position | Net free cash | Gross cash and frozen cash | `gross_cash - abs(frozen_funds)`. |
| Product Related Costs | Gross revenue | `revenue_transactions.amount` | Sum revenue inside selected period. |
| Product Related Costs | Product related costs / COGS | `cogs_transactions.amount` | Sum COGS inside selected period. |
| Product Related Costs | Gross profit / gross margin | Revenue and COGS | `gross_profit = revenue - cogs`; `gross_margin = gross_profit / revenue * 100`. |
| Revenue stream chart | Revenue stream lines | `revenue_transactions.amount`, `projects.revenue_stream_id` | Sum revenue by revenue stream and dashboard bucket. |
| Operational Costs | Operational margin | Revenue, COGS, overhead | `(revenue - cogs - overhead) / revenue * 100`. |
| Operational Costs | EBITDA | Revenue, COGS, overhead | `revenue - cogs - overhead`. |
| Cost Ratio donut | Taxes | `overhead_transactions.overhead_category = 'Taxes'` | Sum taxes inside selected period. |
| Cost Ratio donut | Salary contracts | `salaries.gross_salary` | Sum salaries inside selected period. |
| Cost Ratio donut | Social costs | `overhead_transactions.overhead_category = 'Social Costs'` | Sum social costs inside selected period. |
| Cost Ratio donut | Project costs | `cogs_transactions.amount` | Sum COGS inside selected period. |
| Burnrate | Monthly burnrate | `overhead_transactions.amount` | `period overhead / normalized selected-period months`. |
| Runway months | Runway | Net cash and monthly burnrate | `net_cash / monthly_burnrate`. |
| Tables | Project financials | Projects, revenue transactions, COGS transactions | Per-project revenue, COGS, and net profit for selected period. |
| Tables | Overhead categories | `overhead_transactions.overhead_category`, `amount` | Sum overhead by category for selected period. |
| Tables | Forecast cash position | Revenue, COGS, overhead | Bucket-level revenue, costs, overhead, income, and cumulative cash position. |

## Database Credentials

| Environment | Host | Database | User | Notes |
|---|---|---|---|---|
| Local PostgreSQL | `localhost:5432` | `finance_dashboard` | Set in local `.env` | Local credentials are intentionally not committed. |
| Vercel Marketplace Postgres / Neon | TBD | TBD | TBD | Recommended for Vercel deployment. Update after the database is provisioned. |
| Supabase PostgreSQL | TBD | TBD | TBD | Valid alternative. Update after Supabase is connected. |

## Deploying On Vercel

This project is Vercel-ready through `index.py` and `vercel.json`.

Vercel can run the FastAPI app, but it does not provide first-party Vercel Postgres for new projects anymore. Use a Vercel Marketplace Postgres provider. Neon is the most Vercel-native option; Supabase is also available and works well.

### Recommended Database Option: Neon Through Vercel Marketplace

1. Push this repository to GitHub.
2. In Vercel, create a new project and import the GitHub repository.
3. In the Vercel project, open **Storage / Marketplace**.
4. Add the **Neon** Postgres integration.
5. Create a new Neon database in the same region as the Vercel function if Vercel asks for a region.
6. Let Vercel inject the Neon database environment variables.
7. Add these environment variables manually in Vercel if they are not injected with these exact names:

```bash
DATABASE_URL=postgresql://...
GOOGLE_SHEETS_URL=https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID/edit
GOOGLE_AUTH_METHOD=oauth
GOOGLE_OAUTH_CLIENT_SECRET_PATH=credentials/google_oauth_client_secret.json
GOOGLE_OAUTH_TOKEN_PATH=credentials/google_oauth_token.json
AUTO_SYNC_ON_STARTUP=False
LOG_LEVEL=INFO
```

8. Add Google OAuth credential files as Vercel environment variables or switch the app to load OAuth JSON from environment variables before production. Do not commit credential files.
9. Deploy.
10. Open `/health` to verify the API.
11. Open `/api/v1/dashboard-data/available-years` to verify the database connection.
12. Trigger `/api/v1/sync` once to populate the hosted database.

### Alternative: Supabase PostgreSQL

1. Create a Supabase project.
2. In Supabase, open **Project Settings > Database**.
3. Copy the transaction pooler connection string for serverless deployments.
4. In Vercel project environment variables, set:

```bash
DATABASE_URL=postgresql://postgres.PROJECT_REF:YOUR_PASSWORD@YOUR_SUPABASE_POOLER_HOST:6543/postgres
AUTO_SYNC_ON_STARTUP=False
```

5. Deploy the Vercel project.
6. Trigger a sync:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/sync
```

7. Verify the tables in Supabase Table Editor.
8. Verify the dashboard data endpoint.

## Hosting Feasibility

Vercel can host this app because it supports FastAPI through Python serverless functions.

Recommended deployment:

| Part | Recommended Host |
|---|---|
| PostgreSQL | Neon through Vercel Marketplace, or Supabase |
| FastAPI backend and Google Sheets sync | Vercel Python function |
| Dashboard frontend | Served by the same FastAPI app on Vercel |

GitHub Pages alone is not recommended because it cannot run FastAPI or safely handle Google OAuth and database credentials.
