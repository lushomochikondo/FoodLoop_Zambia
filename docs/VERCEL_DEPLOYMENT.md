# Deploy FoodLoop on Vercel

FoodLoop is a Django app. Vercel detects Django from the root `manage.py` and serves it as a Python Function; the existing `config.wsgi:application` is the app entrypoint. Vercel collects and serves Django static assets during the build.

## Required production services

- **PostgreSQL:** attach a managed PostgreSQL integration such as Neon and expose its pooled connection string as `DATABASE_URL`.
- **Persistent object storage:** create separate S3-compatible buckets for application media and private beneficiary evidence. Vercel Functions have a read-only filesystem, so local SQLite and filesystem uploads are only for development.
- **Email:** configure the SMTP environment variables if password reset and email notifications should be enabled.

The app supports private S3-compatible storage through `django-storages`. Listing, story and article media use the media bucket; beneficiary evidence uses the separate private bucket. Both buckets use private access and signed URLs.

## Vercel environment variables

Set these in the Vercel project settings for Production and Preview as appropriate:

| Variable | Purpose |
| --- | --- |
| `DJANGO_DEBUG` | Set to `0`. Debug also defaults off automatically on Vercel. |
| `DJANGO_SECRET_KEY` | Generate a new random value and keep it secret. |
| `DATABASE_URL` | PostgreSQL connection string from the database integration. |
| `OBJECT_STORAGE_BUCKET` | S3-compatible bucket for listing and public-story media. |
| `PRIVATE_UPLOADS_BUCKET` | Separate private bucket for beneficiary evidence. |
| `OBJECT_STORAGE_REGION` | Storage region; use `auto` for R2. |
| `OBJECT_STORAGE_ENDPOINT_URL` | S3-compatible endpoint, such as an R2 endpoint. Leave blank for AWS S3. |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | Credentials for both configured buckets. |
| `DJANGO_ALLOWED_HOSTS` | Add any custom domain hostname, without `https://`. Vercel deployment hosts are allowed automatically. |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Add custom-domain origins, including `https://`. Vercel origins are allowed automatically. |
| `PUBLIC_APP_URL` | Production site origin, including `https://`; used in email links. |
| `EMAIL_NOTIFICATIONS_ENABLED` | Set to `1` after SMTP is configured. |
| `CRON_SECRET` | Random secret for the scheduled-job endpoint. |

For Gmail SMTP, also set `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, and `DEFAULT_FROM_EMAIL`. Use an app password, not the account password.

## Deploy and initialize the database

1. In Vercel, import `lushomochikondo/FoodLoop_Zambia` from GitHub. Vercel should detect Django automatically.
2. Add the PostgreSQL integration and the production environment variables above, then deploy.
3. Install and sign into the Vercel CLI locally. Pull the Production variables to the ignored `.env.local` file:

   ```powershell
   vercel env pull .env.local --environment production
   .\.venv\Scripts\python.exe manage.py migrate
   .\.venv\Scripts\python.exe manage.py createsuperuser
   ```

4. Redeploy after the database is initialized. Create the admin account in the production database; the local SQLite admin user is not included in Git.
5. Add the Vercel domain to any required Gmail password-reset or sender allowlists, then verify password reset and account notifications.

Keep `.env.local` out of Git. It is covered by the existing `.env.*` ignore rule.

## Scheduled work

`/internal/run-jobs/` runs deadline processing and queued email and push notifications. It requires `Authorization: Bearer <CRON_SECRET>` and returns not-found without a valid secret.

This route is not scheduled by default. On a Vercel plan that supports frequent Cron Jobs, add this to `vercel.json` and redeploy:

```json
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "crons": [
    { "path": "/internal/run-jobs/", "schedule": "*/5 * * * *" }
  ]
}
```

Vercel Hobby Cron is limited to once daily, so it is not frequent enough for collection deadlines and notification retries. On Hobby, use an external scheduler or upgrade before enabling frequent background processing.

## Upload limit

Vercel Functions accept request bodies up to 4.5 MB. FoodLoop limits each uploaded photo or document to 4 MB so multipart form submissions stay below that limit. Larger direct-to-object-storage uploads would need a separate browser upload flow.
