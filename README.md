# Interdec Platform

A full-stack CRM-style platform for managing projects, shipments, vendors and shippers, built to mirror the workflows of the Interdec operations team.

## Tech Stack

| Layer    | Technology                                             |
|----------|--------------------------------------------------------|
| Frontend | Nuxt 3 (Vue 3, TypeScript)                             |
| Backend  | FastAPI (Python)                                       |
| ORM      | SQLAlchemy                                             |
| Database | SQLite (`backend/interdec.db`, auto-seeded on startup) |
| Auth     | Session cookies (JWT-style signed tokens, HttpOnly)    |

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
│   │   └── routers/          # API routes (auth, projects, shipments, vendors, shippers, users)
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

## Demo Accounts

Seeded on first startup:

| Role          | Email                    | Password   |
|---------------|--------------------------|------------|
| Admin         | joshua.n@interdecng.com  | 123456     |
| Sales Staff   | sales@interdecng.com     | sales123   |
| Reports Viewer| viewer@interdecng.com    | viewer123  |

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

### Pricing engine tests

```bash
cd backend && python3 -m pytest tests/test_pricing.py tests/test_quotes_export_migrate.py -v
```

12 tests validate the ported engine against the audited pricing spec, including
the golden reference case (EUROTEC Single Casement 1200x1500 x10, Tempered 8mm
Clear = N1,666,000 cost -> N3,581,900 with 100% markup + 7.5% VAT). A further
5 tests cover the legacy-facade migration (figure preservation, logistics
add-on, idempotency by quote number) and the Excel exports (sheet structure,
grand totals, per-unit pricing).
