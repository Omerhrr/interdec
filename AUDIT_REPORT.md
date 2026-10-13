# Interdec Platform: Audit Report

**Date:** 8 October 2026
**Scope:** the whole repository: FastAPI backend, Nuxt 3 frontend, legacy `facade.html`, scripts and tests.

**How this was verified:**
- 35 backend tests (17 existing + 18 new API tests) all pass, including after re-checking every file on disk.
- Nuxt production build and `nuxi typecheck` pass with 0 errors.
- The API was smoke-tested against a copy of the real `interdec.db`.
- A headless-browser run covered login, a new shipment, invoice upload and download, catalogue upload and download, report export, quotes search and Excel export, the Rate Card, user admin, the viewer role and Facade sign-in. There were no JavaScript errors.

---

## 1. Critical: crashes and data integrity

| # | Problem | Fix |
|---|---|---|
| 1 | `routers/vendors.py` had no permission checks or upload validation. It also served catalogues inline whenever their type started with `application/` or `image/`, which includes SVG and XHTML, so an uploaded file could run script. Its filenames went unsanitized into headers. | Hardened in place with the same API (category filter, catalogue list, upload notifications kept). Uses the shared safe upload/download helpers in `files.py`. |
| 2 | **`openpyxl` was missing** from `requirements.txt` and `start.sh`, so every Excel export crashed. | Added it. `start.sh` now installs from `requirements.txt`. |
| 3 | `start.sh` created a virtualenv but never used it. Packages went into the system Python. | It now uses the venv's interpreter on Linux, macOS and Windows Git Bash, and stops on install failure. |
| 4 | The database path was relative to the **current folder**. Starting uvicorn from anywhere else silently created a new, empty database. | The path now resolves from the backend folder. It can be overridden with `INTERDEC_DATABASE_URL`. |
| 5 | **Shipment refs collided.** `IMP-2026-{count+1}` reused a ref after any deletion and was hard-coded to 2026. | Refs are now per-year max + 1. |
| 6 | Activity timestamps were wrong by the server's UTC offset (`datetime.utcnow().timestamp()`). | Switched to `time.time()`. |
| 7 | `_ensure_columns()` ran `ALTER TABLE` without committing, so on SQLAlchemy 2 the migration could be lost. | It now uses `engine.begin()`. |

## 2. Security

| # | Vulnerability | Fix |
|---|---|---|
| 8 | **Hard-coded JWT secret** (`"interdec-platform-secret-key-2026-change-in-production"`). Anyone with the source could forge an admin token. | The key comes from `INTERDEC_SECRET_KEY`, or a random key is generated once into `backend/.secret_key` (git-ignored). |
| 9 | **No server-side authorization.** Any logged-in user, including "Reports Viewer", could create or delete projects, shipments, shippers and vendors. They could also use or delete-adjacent all of Quotations, and list every user. Only the UI hid the buttons. | Added `require_importflow_editor`, `require_quotes_access` and an admin-only users list. Role checks now match the UI rules. |
| 10 | **Stored XSS via file upload.** Shipment documents were served `inline` with the uploader-supplied MIME type, so an uploaded `text/html` file ran script on the app's origin. | Only PDF, images and plain text are served inline. Everything else downloads as `application/octet-stream`, with `nosniff`. |
| 11 | Header injection via filenames in `Content-Disposition`. | Filenames are sanitized and RFC 5987 encoded (`files.py`). |
| 12 | No upload validation (size or base64). One upload could bloat the database without limit. | 15 MB limit, base64 validation and a per-vendor catalogue cap. The client checks size too. |
| 13 | **Cross-window messaging trusted any sender.** The portal acted on `idf-migrate` from any window, so a hostile page could import data as the user. The facade accepted `idf-sso` (an identity *with role*) from anyone, and broadcast the whole quote dataset with target `'*'`. | Both sides now check `origin` and `source`, and all posts target `location.origin`. Removed an unhandled `facade-download` broadcast that leaked workbook bytes. |
| 14 | CORS `allow_origins=["*"]` combined with `allow_credentials=True`. | Explicit origin list (`INTERDEC_CORS_ORIGINS`) with no credentials. Auth is a bearer header. |
| 15 | Report export put user-entered names and descriptions into HTML **unescaped**. | All values are escaped. |
| 16 | `users` PUT/POST accepted arbitrary `apps` keys and roles. You could also demote the last admin. | Apps and roles are whitelisted, and the last active admin is protected. |
| 17 | API proxy hard-coded and logged every request. | Configurable through `runtimeConfig.apiTarget` / `NUXT_API_TARGET`. Only `/api/*` is forwarded, with a clean 502 when the backend is down. |

## 3. Broken logic

| # | Bug | Fix |
|---|---|---|
| 18 | **Shipment workflow could be bypassed.** "Mark as Shipped" forced `in_transit` without a packing list. "Save Shipper" *also* shipped the goods if a packing list existed. Any editor could set any status string. | The server enforces the order: invoice, then packing list + shipper, then in transit, then shipper invoice, then completed. Only ImportFlow admins can override. Status values are validated, and the UI button is disabled until all prerequisites are met. |
| 19 | **Mosquito nets were always free.** The quote, calculate and recompute endpoints never passed `mosqRates` to the engine. | All pricing goes through one `_calc()` helper that passes every catalogue table. |
| 20 | **Saved quotes changed when the rate card changed.** Item BOMs were re-priced on every read with current rates, while totals stayed as saved. Line items stopped adding up to the total, and Excel exports showed it. Migrated quotes were re-priced with the wrong catalogue. | Each revision now stores its priced BOM snapshot. Older rows fall back to recompute. |
| 21 | Changing a quote's project only updated the name. **`project_id` was never saved.** | Fixed and validated. Renaming a project now also updates linked quotes. |
| 22 | Sent, won or lost revisions could still be edited through the API, and older revisions' status could change. | Only draft revisions are editable, and only the latest revision's status changes. |
| 23 | Legacy migration: **notes accumulated** across a project's quotes (quote 3 got quotes 1–3's descriptions). A non-numeric `rev` crashed the import. Quotes with no revisions were imported empty. | Notes are now per quote, rev sorting is safe, and empty quotes are skipped. |
| 24 | New revisions dropped the transport and logistics cost. | Carried over from the previous revision. |
| 25 | Rate Card accepted invalid values: blanks, negative numbers, or default markup below the floor. Non-numeric VAT caused a 500 error. | Validated server- and client-side. |
| 26 | Change-password **stripped spaces** but login doesn't, so passwords with leading or trailing spaces stopped working. | Passwords are compared verbatim. |
| 27 | Deleting a shipper silently detached it from shipped or completed cycles. Deleting a vendor in use orphaned shipments. | Both are blocked with a clear message while still in use. |
| 28 | Deleting a user left their notifications behind. | Cleaned up. User updates are now logged. |
| 29 | Excel export crashed on balustrade items with no length. | Handled safely. |

## 4. Frontend bugs and unreachable features

| # | Bug | Fix |
|---|---|---|
| 30 | **New shipments didn't appear** until a full reload, because the shared store wasn't refreshed. From the Shipments list, the "go to detail" step landed on the list instead. | The modal reloads data, then opens the new shipment. Works from the Dashboard too. |
| 31 | **Catalogue download (↓) always failed** with 401: a plain `<a href>` sends no auth token. | Authenticated blob download. |
| 32 | **Quotations access couldn't be granted** in User Management (no toggle), and users couldn't be deleted from the UI. | Added a Quotations column and toggle, plus a Delete button. You can no longer disable or delete yourself. |
| 33 | **Mosquito net rates had no editor** (all ₦0), so the feature was unreachable. | New "Mosquito Net Rates" section on the Rate Card. |
| 34 | Project page's "New Shipment" just jumped to the Shipments list. | Opens the form pre-filled with that project. |
| 35 | Quotes search used the wrong variable (`!q` instead of `!s`). | Fixed. |
| 36 | "Export PDF" actually downloaded an `.html` file. | Opens a print view ("Save as PDF"), with HTML download as the fallback. |
| 37 | File chip and upload box styles used unitless numbers (`gap: 8`), which browsers ignore, so the layout was broken. | Fixed with proper units. |
| 38 | Platform admins without an explicit ImportFlow role were treated as viewers in some screens. | One role rule shared by the UI and the API. |
| 39 | Download errors showed "[object Blob]". Validation errors showed raw objects. | Readable messages. |
| 40 | Demo shipment files have no stored bytes, so View and Download failed. | Shown as "demo record" instead of broken buttons. |
| 41 | No `tsconfig.json`, so editors and typecheck had no project types. | Added. Typecheck passes with 0 errors. |

## 5. Follow-up fixes

| # | Item | Fix |
|---|---|---|
| 42 | The native quote editor couldn't build **composite items**, so the feature was only reachable through migrated quotes. | Each item now has "+ Add composite element", with its own type, size and glass. It is validated and priced live, including the shared-edge sub-frame rule. |
| 43 | The editor had no **Position** field, although the client Excel prints it. | Added. |
| 44 | **Demo passwords** (`123456`, `sales123`, `viewer123`) are public. | Anyone signing in with one must set a new password before using the app, and demo passwords can't be chosen again. Passwords an admin sets for a user are temporary in the same way. |

## 6. Still yours to decide

- **Pricing quirks.** Sealant is charged even without a sub-frame, and composites use a 1.5×(W+H) sub-frame. Both are deliberately kept from the audited legacy engine. Changing them changes every quote's price, so confirm with the business first. Each one is a single line in `pricing.py`.
- **Files are stored as base64 inside SQLite.** This is fine at the current scale. Move them to disk or object storage if volumes grow.
- The **legacy facade** keeps its own users in browser localStorage. Retire it once the migration is confirmed.
