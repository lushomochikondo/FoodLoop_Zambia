# Deployment and operations

## Current environment

The working app is local at http://127.0.0.1:8000 with SQLite and local media. It is not publicly deployed. A phone's `127.0.0.1` refers to that phone, not the development computer. Cross-device access requires an explicitly configured LAN address or a hosted deployment.

## Local fallback

Install Python 3.13, create `.venv`, install `requirements.txt`, run migrations, and seed fictional data. Existing prototype account passwords are preserved by seed. Launch with `manage.py runserver 127.0.0.1:8000`. Copy the project, installed dependencies, database and media to the prototype laptop ahead of time. Test with networking disabled. Record a separate backup prototype walkthrough video and generate a QR code only after a public URL exists.

`manage.py backup_prototype` uses SQLite's backup API to produce a consistent database copy, and copies media alongside it. Avoid uploading while taking the backup so the file set stays aligned. Backup folder names are UTC. To restore, stop the local server and copy a chosen backup's `db.sqlite3` and `media/` into a separate project copy first. Validate it before replacing an active working copy. The secret key and environment configuration are stored separately and must be preserved privately.

## Hosting prerequisites

Use a Python/Django-capable Linux host, managed PostgreSQL, persistent media storage and an HTTPS domain. Cloudflare Workers/Sites cannot directly run this standard Django process. Select the actual hosting account/platform before deployment; this project has not been provisioned with remote credentials or a domain.

Install `requirements-production.txt`. Set:

| Variable | Purpose |
| --- | --- |
| `DJANGO_DEBUG=0` | Disable developer error pages |
| `DJANGO_SECRET_KEY` | A new private production secret |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated real hostnames |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Comma-separated HTTPS origins |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | Database credentials |
| `POSTGRES_HOST`, `POSTGRES_PORT` | Database endpoint |
| `POSTGRES_SSLMODE` | Defaults to `require`; use the provider's secure configuration |
| `REQUEST_EXPIRY_HOURS` | Defaults to 24 |
| `MEAL_WEIGHT_KG` | Defaults to 0.4; use a positive number |

Run `python manage.py migrate`, `python manage.py collectstatic --noinput`, and `python manage.py check --deploy`. Launch `gunicorn config.wsgi:application`. WhiteNoise serves collected static files. Food photos use the authenticated `/listings/<id>/photo/` route in both development and production; do not expose a public `/media/` route. Keep the media directory on persistent storage. Uploaded images are verified and re-encoded JPEG with EXIF removed, but still need persistent storage and backups.

Configure the reverse proxy for HTTPS and upload limits above 8 MB. Only configure Django's forwarded-protocol trust if the chosen proxy strips untrusted incoming headers; that setting deliberately depends on the final hosting setup. Secure cookies, HTTPS redirect, session expiry and HSTS are configured when DEBUG is disabled. Check the provider's HTTPS/proxy configuration before first public deployment.

Run `python manage.py process_deadlines` every five minutes using the host scheduler. This expires pending requests, marks missed collection deadlines, releases reservations, and creates deduplicated deadline notifications. Schedule PostgreSQL `pg_dump` and media backups; test restores. Do not rely on filesystem SQLite backups for a hosted PostgreSQL deployment.

Use real production accounts and credentials rather than publishing the local prototype passwords. Confirm organisation verification, final acknowledgement wording, privacy/retention decisions and the operational administrator before using real partner data.

## Verification

Run `manage.py test`, `qa/concurrent_acceptance.py`, and `qa/responsive_check.py` locally. The concurrency script isolates a temporary file-backed SQLite database and races two real service calls for the last kilogram. It never changes the working database. PostgreSQL uses the same transactions with row locking, but its concurrency behavior must also be tested on the actual hosted database before launch.

The browser script uses installed Edge and Playwright; install the optional QA package with `python -m pip install playwright`. It covers 11 viewport widths and screenshots, not physical-device compatibility or a complete assistive-technology audit. Recheck on real Android/iOS devices and browsers used by pilot partners.

## Prepared release artifacts

`Dockerfile` builds a Python 3.13 application image, installs production requirements, collects hashed/compressed static assets, and runs Gunicorn as a non-root user. It accepts the host's `PORT` variable through `scripts/serve.py`. Run `python manage.py migrate` as a separate release step before starting web traffic. Docker is not installed on the development computer, so the image itself has not been built or run here.

WhiteNoise now serves collected static files directly in production. A separate static server is optional; uploaded photos are now served through an authenticated, pathway-scoped Django endpoint; persistent media storage is required. Set `DJANGO_MEDIA_ROOT` to the persistent media mount. WhiteNoise intentionally does not serve user uploads. Enable `DJANGO_TRUST_PROXY=1` only after confirming your hosting platform's trusted HTTPS proxy behavior.

`.env.example` lists the required configuration without real credentials. It is an example; Django loads a separate local `.env` with environment variables taking precedence. `python scripts/package_release.py` creates a source-only ZIP under `dist/`. It excludes database records, uploaded food photos, backups, the virtual environment and local secrets. The ZIP is suitable for review or source transfer, not a complete data backup. The archive's contents are checked after creation.

`python qa/production_smoke.py` tests DEBUG-disabled rendering, hashed static asset serving, HTTPS redirects and HSTS locally without creating a hosted resource. Production-mode checks and the unit suite pass. Actual hosting, persistent media storage and HTTPS/proxy configuration remain to be tested in the selected account. The suite and allocation race also pass on a separate local PostgreSQL instance.

## Completed audit additions

Protected food photos use `/listings/<id>/photo/`, not a public media directory. Keep `DJANGO_MEDIA_ROOT` on persistent storage. Development and production use the same permission checks for images.

Optional notification emails are queued until `manage.py send_notifications` runs with `EMAIL_NOTIFICATIONS_ENABLED=1` and SMTP configured. Run `manage.py run_jobs` every five minutes, or use `manage.py run_scheduler` as a separate worker. Email remains disabled in the local prototype. In-memory email tests send nothing to external recipients.

Optional environmental estimates require both `CO2E_KG_PER_KG` (positive) and `CO2E_SOURCE`. Without an agreed source/factor, no CO2 estimate is displayed. `MEAL_WEIGHT_KG` must also be positive; configuration checks reject invalid assumptions.

The PWA manifest, icons, service worker and public offline page are implemented. Installation requires a supported browser in a secure context (HTTPS when hosted, or local loopback during development). The service worker caches only explicitly listed public assets; authenticated pages and uploaded food photos remain network-only.

Gmail setup and email preferences/retry details are in [GMAIL_SETUP.md](GMAIL_SETUP.md). Local configuration uses a masked setup window; credentials are not required in chat.
