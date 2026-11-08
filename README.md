# FoodLoop Zambia

For the hosted testing setup, see [Render deployment](docs/RENDER_DEPLOYMENT.md).

Local Django MVP based on FLZ-SRS-001 version 1.1 (4 November 2026).

## Run locally (PowerShell)

```powershell
cd E:\EVERYTHING\FoodLoop
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py seed_prototype
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

Open http://127.0.0.1:8000. Seed prints a random password for newly created accounts: provider, recipient, school, farm, compost, admin. Rerunning seed preserves existing passwords. Data is fictional; Lusaka Central is a provisional prototype walkthrough area.

## First prototype

Sign in as recipient, request bread, then sign in as provider and accept. Pickup details appear after acceptance. Mark ready, confirm the full accepted quantity as provider, then confirm as recipient. Only then does the dashboard count recovery. Use separate browser profiles to keep both roles signed in.

Admin verification is available under /admin/. Audit records are read-only. All timestamps display in CAT. Impact kilograms currently include only listings explicitly measured in kg; other units have no invented conversion.

## Checks

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py test
```

## Current scope

The local MVP includes provider edit/withdraw, weighted matching with reasons, private in-app notifications, organisation verification evidence and review, listing reports/moderation, request-event history, automatic deadline processing on dashboard/detail access, a scheduled processing command, and a dedicated impact page with date/pathway filters and CSV export. Photos and responsive layouts are implemented.

See [complete SRS audit](docs/SRS_AUDIT.md) and [remaining sign-offs](docs/REMAINING_SIGNOFF.md), [user guide](docs/USER_GUIDE.md), [prototype walkthrough checklist](docs/PROTOTYPE_CHECKLIST.md), and [deployment guide](docs/DEPLOYMENT.md). Public hosting and PostgreSQL verification remain outstanding.

SQLite uses IMMEDIATE transactions to serialize local writes; concurrent acceptance has an isolated test in `qa/concurrent_acceptance.py`. Run `manage.py backup_prototype` for a local database/media backup and `manage.py process_deadlines` for unattended request housekeeping.

## Food photos and design

The photo-led interface uses a deep green sidebar, ivory surfaces, consistent Inter typography and responsive listing cards. Providers can upload one optional JPG, PNG or WebP photo when creating a donation, with immediate local preview. The server verifies the image, limits uploads to 8 MB and 25 megapixels, resizes to at most 1600 pixels, and re-encodes JPEG without EXIF metadata. Photos persist under media/ and appear on cards and detail pages. Existing listings without photos display an honest empty state. Production requires a dedicated media storage and serving configuration; DEBUG media serving is local-only.

Search by food name, area and approved pathway is available on the dashboard. Recovery totals are shown by pathway. Decorative photography credits are in static/images/CREDITS.md.

## Responsive interface verification

The active stylesheet is static/responsive.css. It replaces the earlier layered stylesheets. Inter is bundled in static/fonts/ so the same typeface works locally on phones, tablets and computers without an external font request. The licence is bundled alongside the font. Desktop uses a sidebar; screens under 1024 pixels use an accessible Menu disclosure with a sign-out action. Cards, forms, filters, photos and impact panels reflow at tablet and phone widths. Inputs use 16px text, and primary touch controls are at least 44px high.

Browser QA: install Playwright in the development environment (`python -m pip install playwright`), then run `python qa/responsive_check.py` while the local server runs. It uses installed Microsoft Edge, checks sign-in, dashboard, upload and detail pages at 320, 375, 390, 480, 600, 768, 820, 1024, 1280, 1440 and 1920 pixels, verifies loaded fonts and horizontal overflow, exercises the mobile menu, and saves screenshots in qa/. This is viewport testing, not testing on physical devices.

## Audit completion

The full 77-requirement matrix and TC-01 to TC-22 mapping are in `docs/SRS_AUDIT.md`, generated from the supplied PDF extraction. Business rules and use cases are mapped in `docs/BUSINESS_RULE_TRACE.md`. Public hosting, human usability/device sign-off and supervisory decisions remain explicitly open.

The app now includes PWA installation assets, private production photo delivery, profile preferences, collection notes, explicit donation type, created timestamps, availability filters, per-unit pathway reports, optional sourced environmental estimates and an opt-in email queue. `qa/acceptance_browser.py` records an isolated end-to-end prototype while blocking external browser requests. The recording is at `qa/prototype-recording/FoodLoop-complete-prototype.webm`.

## Verification artifacts

See `docs/VERIFICATION_RESULTS.md` for the final measured results: the 42-test suite on SQLite and PostgreSQL, 372 Edge/Firefox/WebKit layout checks, 48 automated A/AA scans, local load timings, PWA installability, protected photo delivery, and production-mode checks. The optional Playwright/axe QA assets and browser recordings are development artifacts and are not shipped in the source-only release.
