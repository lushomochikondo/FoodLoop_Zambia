# Render testing deployment

The root `render.yaml` provisions one free Python web service. It uses existing
PostgreSQL and S3-compatible storage; it does not create a database or paid worker.

## Create the service

1. Push this configuration to GitHub.
2. In Render, select **New > Blueprint**, connect
   `lushomochikondo/FoodLoop_Zambia`, and select the branch containing `render.yaml`.
3. Supply the prompted environment values privately in Render. `DATABASE_URL` must
   point to an externally reachable PostgreSQL database, never localhost. Use the
   existing database provider's connection string with TLS enabled. The local
   migration state does not establish that the database is reachable from Render.
4. Supply the two bucket names, S3 endpoint and access credentials. Both buckets
   must exist and remain private. `OBJECT_STORAGE_REGION=auto` suits Cloudflare R2;
   change it to the actual region if using another S3 provider.
5. Deploy. The build collects static assets; startup checks production settings,
   applies pending migrations, and starts Gunicorn. This startup migration strategy
   is for a single testing instance; use a release migration step before scaling.
6. Open the generated HTTPS `onrender.com` URL. The app automatically trusts its
   Render hostname and uses that origin for notification links. For a custom domain,
   configure `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, and `PUBLIC_APP_URL`.

Keep secrets out of Git and chat. No seed accounts are created automatically.
Existing users are available only if this is the database containing those users;
migrations create schema, not a copy of local records.

## Scheduled jobs and email

Use an external scheduler to send a GET request every five minutes to
`https://YOUR-SERVICE.onrender.com/internal/run-jobs/`, with the header
`Authorization: Bearer YOUR_CRON_SECRET`. Store the generated Render secret in the
scheduler's private configuration. Do not put it in a URL or public workflow.
Allow for cold starts and verify successful runs. A free web service alone does
not run background jobs while sleeping. Without a configured scheduler, unattended
deadline processing and queued notifications are not fully operational.

Email is initially disabled. Render free web services block outbound SMTP ports
25, 465, and 587; the existing Gmail SMTP configuration will therefore need a paid
service or a change to an HTTPS email provider before email tests can pass.

## Verify before inviting testers

- Confirm login, admin access, and secure cookies over HTTPS.
- Create a donation and complete its request/collection workflow using two roles.
- Upload a photo and private evidence; verify the intended access restrictions.
- Redeploy and confirm database records and uploads still exist.
- Confirm scheduled jobs run and notification delivery behaves as configured.

Free Render services sleep after 15 minutes without traffic and have usage limits.
Expect slow first visits. Keep the existing external database: Render's free
PostgreSQL expires after 30 days. No custom domain is required for initial testing.

References: https://render.com/docs/free and https://render.com/docs/blueprint-spec
