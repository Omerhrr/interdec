# Interdec Platform

A full-stack CRM-style platform for managing projects, shipments, vendors and shippers, built to mirror the workflows of the Interdec operations team.

## Tech Stack

| Layer    | Technology                                             |
|----------|--------------------------------------------------------|
| Frontend | Nuxt 3 (Vue 3, TypeScript)                             |
| Backend  | FastAPI (Python)                                       |
| ORM      | SQLAlchemy                                             |
| Database | SQLite (`backend/interdec.db`, auto-seeded on startup) |
| Auth     | JWT bearer tokens (stored in a browser cookie, sent as an `Authorization` header) |

## Project Structure

```
interdec-platform/
├── backend/                  # FastAPI application
│   ├── app/
│   │   ├── main.py           # App entrypoint & CORS
│   │   ├── database.py       # SQLAlchemy engine & session
│   │   ├── models.py         # ORM models
│   │   ├── schemas.py        # Pydantic schemas
│   │   ├── auth.py           # Password hashing & session tokens
│   │   ├── seed.py           # Demo data seeder (runs on startup)
│   │   ├── files.py          # Upload validation + safe file downloads
│   │   └── routers/          # API routes (auth, projects, shipments, vendors, shippers, users, quotes, activity)
│   └── static/               # Static assets served by the backend
├── requirements.txt          # Python dependencies
├── frontend/                 # Nuxt 3 application
│   ├── components/if/        # Feature modules (Dashboard, Projects, Shipments, Vendors, Shippers, Reports, UsersAdmin)
│   ├── components/ui/        # Reusable UI primitives (modal, chips, selects, upload, status tracker)
│   ├── composables/          # useAuth, useApi, useData, useConstants
│   ├── pages/                # index (login) + platform (main app shell)
│   └── assets/css/           # Global stylesheet
└── start.sh                  # Convenience script to run both servers
```

## Getting Started

### 1. Backend (FastAPI)

```bash
pip install -r requirements.txt
cd backend
uvicorn app.main:app --reload --port 8100
```

The API is served at `http://localhost:8100`. On first run the SQLite database is created and seeded with demo data. Swagger docs: `http://localhost:8100/docs`.

### 2. Frontend (Nuxt)

```bash
cd frontend
npm install
npm run dev
```

The app is served at `http://localhost:3000` and proxies `/api/*` requests to the backend on port 8100.

### One-shot startup

```bash
bash start.sh
```

### Configuration (optional environment variables)

| Variable | Default | Purpose |
|---|---|---|
| `INTERDEC_SECRET_KEY` | random key saved to `backend/.secret_key` on first start | Signs login tokens. Set it explicitly in production. |
| `INTERDEC_DATABASE_URL` | `sqlite:///backend/interdec.db` (resolved from the backend folder) | Database location. |
| `INTERDEC_CORS_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000` | Extra browser origins allowed to call the API directly. |
| `NUXT_API_TARGET` | `http://127.0.0.1:8100` | Where the Nuxt `/api` proxy forwards requests. |

## Roles & permissions (enforced by the API)

- **Platform admin**: everything, including user management, the Rate Card and deleting quotes.
- **ImportFlow admin / user**: create and edit projects, shipments, vendors and shippers. Admins can also override a shipment's status.
- **ImportFlow reports viewer**: read-only (Reports only in the UI).
- **Quotations**: platform admins, plus anyone with Quotations *or* Facade access.
- Shipment workflow order is enforced: vendor invoice, then packing list + shipper, then shipped, then shipper invoice, then completed.

## Demo Accounts

Seeded on first startup:

| Role          | Email                    | Password   |
|---------------|--------------------------|------------|
| Admin         | joshua.n@interdecng.com  | 123456     |
| Sales Staff   | sales@interdecng.com     | sales123   |
| Reports Viewer| viewer@interdecng.com    | viewer123  |

> These are public demo passwords. Signing in with one forces you to choose a new password first.

## Features

- **Dashboard**: KPI cards, shipment status breakdown, recent activity
- **Projects**: create/track projects with milestones and document uploads
- **Shipments**: full lifecycle tracking with status tracker, vendor/shipper assignment
- **Vendors**: supplier directory with catalogues and contact details
- **Shippers**: logistics partners with freight categories
- **Reports**: status and performance reporting
- **Users Admin**: role-based user management (admin only)
- **Quotations** (native app): server-side pricing engine ported from the legacy
  facade build - per-item BOM (profile, glass, gaskets, hardware, fabrication,
  installation, mosquito nets, sub-frames, sealant), composite items, DGU colour
  premiums, sliding-net half-area rule, markup with enforced 70% floor, 7.5% VAT,
  14-day validity, IDF-YYYY-NNN numbering (per-year max+1), revision history with
  draft/sent/won/lost lifecycle, printable quote document, admin Rate Card for
  live rate changes without deployment
- **Excel export**: one-click .xlsx from the server (openpyxl) - the quotes list
  exports a pipeline summary workbook (Quotes + Revisions sheets), and each quote
  revision exports a client-ready workbook (Work Breakdown item cards + summary +
  payment terms/T&Cs + BOM Details sheet), mirroring the legacy facade deliverable
  (with the legacy unit-price double-count fixed: unit = line selling / qty)
- **Legacy migration**: the facade app shows a migration banner; one click hands
  its localStorage dataset to `POST /api/quotes/migrate`, which imports quotes and
  revisions into the server database (numbers preserved, totals recomputed with
  the facade's own rate snapshot, transport & logistics retained per revision,
  idempotent by quote number). The facade then flips to a read-only reference
- **Facade Pricing** (legacy): the original single-file app embedded for reference;
  read-only after migration to the native Quotations app

### Tests

```bash
cd backend && python -m pytest tests -v
```

The suite runs against a throwaway database (never `interdec.db`). `test_api.py`
(21 tests) exercises the HTTP API end to end: permissions, the shipment workflow,
catalogue upload/download, safe file serving, quotes access, mosquito-net pricing
and revision locking. 12 pricing tests validate the ported engine against the audited pricing spec, including
the golden reference case (EUROTEC Single Casement 1200x1500 x10, Tempered 8mm
Clear = N1,666,000 cost -> N3,581,900 with 100% markup + 7.5% VAT). A further
5 tests cover the legacy-facade migration (figure preservation, logistics
add-on, idempotency by quote number) and the Excel exports (sheet structure,
grand totals, per-unit pricing).

## Deploy to Render

The app ships as one Docker service: the Nuxt app is built to static files and
FastAPI serves them alongside `/api`, so there is no CORS or proxy to configure.

1. Push this folder to a GitHub repository (`.gitignore` already keeps out
   `node_modules`, the local database and the secret key).
2. In Render: **New → Blueprint**, pick the repository. Render reads `render.yaml`.
3. Click **Apply**. The first build takes ~5 minutes. Open the `.onrender.com` URL.

`render.yaml` uses the Starter plan with a 1 GB disk at `/var/data`, so the
database survives restarts and redeploys. On the Free plan (remove `plan` and
`disk`, and set `INTERDEC_DATABASE_URL=sqlite:////tmp/interdec.db`) it works, but
the app sleeps after 15 idle minutes and every restart wipes back to demo data.

Demo accounts are created on first start (see the table above). Each one must
set a new password on first login.

## Quotation PDFs (WeasyPrint)

Quote PDFs are generated on the server with WeasyPrint and styled from
**Quotations → PDF Design** (logo, colours, font, header style, which sections
show). The Docker image already includes what it needs. For local development
(Linux / WSL) install the system libraries once:

```bash
sudo apt install libpango-1.0-0 libpangoft2-1.0-0 fonts-dejavu-core fonts-liberation
pip install -r requirements.txt
```

Without them the rest of the app works; the PDF button explains what's missing.

## ETA email alerts

On any shipment page, **ETA email alerts** sends reminders to a list of
addresses: 30/14/7/5/3/2/1 days before arrival, on arrival day, if overdue, and
when the ETA changes. Each reminder goes out once per ETA; a background job
checks every 30 minutes (`INTERDEC_ALERT_INTERVAL_MIN`). Every email is logged.

Email is sent over SMTP. Set these environment variables (on Render: the
service's **Environment** tab):

| Variable | Example |
|---|---|
| `INTERDEC_SMTP_HOST` | `smtp.gmail.com`, `smtp.zoho.com`, `smtp.office365.com`, `smtp.sendgrid.net` |
| `INTERDEC_SMTP_PORT` | `587` (STARTTLS) or `465` (SSL) |
| `INTERDEC_SMTP_USER` | the mailbox login (`apikey` for SendGrid) |
| `INTERDEC_SMTP_PASSWORD` | its password; for Gmail/Google Workspace an **App Password** |
| `INTERDEC_SMTP_FROM` | `Interdec <alerts@yourdomain.com>` |
| `INTERDEC_APP_URL` | `https://your-app.onrender.com` (for the "Open shipment" button) |
| `INTERDEC_TZ` | `Africa/Lagos` (which day counts as "today") |

Until they're set, alert settings still save and the page says email isn't set up.

## Business features

- **Won quote → project:** marking a quote Won can create the ImportFlow project (or link an existing one).
- **Budget vs actual:** each project compares its contract value (won quotes, excl. VAT) with what its
  imports actually cost (goods + shipping + clearing). Also a report and in project exports.
- **Vendor payments:** record deposits and balances per shipment; balances past their payment terms
  show as due. The **Payables** report lists everything owed.
- **Email notifications** (sidebar ✉ / portal ✉): shipment status changes, quotes won/lost, and a
  Monday 08:00 payables summary (`INTERDEC_DIGEST_WEEKDAY`, 0 = Monday). Uses the SMTP settings above.
- **Products and types** (Rate Card): add systems and window/door types with aluminium kg/m², hardware
  kit and net/sub-frame rules; a new brand gets its own profile rate.
- **Import from Excel/CSV:** ImportFlow → Import data (vendors, shippers, clearing agents, projects,
  shipments) and Rate Card → Import prices (glass, ACP, hardware). Template, preview, then import.
