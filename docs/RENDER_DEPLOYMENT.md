# Render testing deployment

## Hosted testing status (9 November 2026)

- App: https://foodloop-zambia.onrender.com
- Render service: `foodloop-zambia`, free plan, Oregon, tracking `master`.
- Database: Neon project `neon-yellow-ladder` (`lively-darkness-17241400`).
- Initial deployment applied the Django migrations. Local users and records were
  not copied to the hosted database.
- HTTPS login, signup, admin login and five static assets returned HTTP 200.
- Image uploads initially returned HTTP 500. Render's six storage variables were
  updated from the locally verified working configuration. After redeploying,
  an unpublished admin draft image uploaded successfully and its signed image URL
  returned HTTP 200. The diagnostic draft and image were removed.
- Email remains disabled; an external scheduler and authenticated upload/workflow
  verification are still outstanding.
- The unused `neon-champagne-castle` project (`divine-unit-28363931`) has no
  FoodLoop tables, users or organizations. Deletion through Neon was rejected
  because its organization is managed by Vercel; remove it through Vercel.
- The existing 72-test local suite reported four failures and two errors:
  signup expectations differ from the eligibility flow, an audit assertion expects
  “provider” where the implementation uses “donor”, and a photo test assumes a
  filesystem path while local settings select object storage.

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

## 10 November release preparation

The collection route planner, nationwide Zambia map controls and donor road-access reports are ready for the hosted testing release. The isolated suite passes 98 tests; mobile and desktop browser checks pass, including a Kasama listing and acceptance privacy. Production static collection is checked separately. Migrations 0023 and 0024 must be applied by the existing startup command. Existing records default to private pins and unknown road access. Automatic whole-route surface analysis is not included. Email delivery and the external job scheduler remain separate operational work.

## Phone notifications and approval email

Phone notification controls require both the workspace and push context processors. Configure WEB_PUSH_PUBLIC_KEY and WEB_PUSH_PRIVATE_KEY as a matching VAPID key pair in Render; WEB_PUSH_SUBJECT can be the HTTPS app URL. Notification creation now attempts targeted delivery after commit. Failed attempts remain queued for the authenticated scheduled job to retry. A user must open Notifications, enable phone alerts on their own device, and grant browser/OS permission. Send test phone alert checks the same server delivery path. iPhone users need a supported Home Screen web app.

Approval emails remain disabled until a working sender is configured. On Render free use EMAIL_BACKEND=core.email_backends.ResendEmailBackend, RESEND_API_KEY, DEFAULT_FROM_EMAIL with a provider-verified sender, PUBLIC_APP_URL and EMAIL_NOTIFICATIONS_ENABLED=1. Keep API keys in Render secrets. Test provider delivery before enabling for testers. Existing Gmail SMTP settings cannot use blocked SMTP ports on Render free. The queued retry scheduler still needs an external caller.

## Immediate donor publishing

Donor registrations receive posting access immediately and open the listing editor after signup. Migration 0025 enables existing pending donor accounts and records an audit entry. It does not reactivate suspended, declined or needs-information accounts. Beneficiary and recovery partner approvals remain required. Published human-consumption listings appear immediately to eligible beneficiaries; feed and compost remain restricted to matching recovery partners. Donor onboarding and the listing editor explain this audience distinction.

## Inclusive beneficiary categories and browsing

Beneficiary registration includes livestock farmers and composting operators alongside human-food programmes. Each account currently has one approved recovery pathway. Animal-feed and compost applications use relevant handling and accountability fields rather than human-feeding counts or food-handler fields. Beneficiaries can browse all available pathways; collection forms and server-side requests remain limited to the approved use. Listing pins, written addresses and access reports retain their existing privacy controls. Migration 0026 records the new programme choices.
