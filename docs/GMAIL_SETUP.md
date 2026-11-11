# Gmail notification setup

For the hosted Render Free service, use [Gmail API setup](GMAIL_API_SETUP.md). The SMTP instructions below apply to local development or hosts that permit Gmail SMTP connections.

The notification pipeline sends a formatted HTML email plus plain-text alternative for account, request, decision, collection, moderation and deadline events. Users can turn email updates off under Your profile; signup includes the same preference. In-app notifications stay available independently.

## Connect the sender

Run `.\.venv\Scripts\pythonw.exe scripts\configure_gmail.py` on the local Windows computer. Enter the sender Gmail address and a Google app password in the masked field. The window links to Google's App Passwords page. Google requires 2-Step Verification for app passwords, and some managed or protected accounts do not offer them.

Official instructions: https://support.google.com/accounts/answer/185833

The helper authenticates with `smtp.gmail.com:587` using STARTTLS. It sends no email during setup. On success, it atomically saves settings in `.env`, with file access restricted to the current Windows user. The app password is not printed or stored in the database, source ZIP or Git. Existing environment variables take precedence over `.env`.

Saving enables delivery configuration, but a worker must be running to process queued messages. Start it with:

```powershell
.\.venv\Scripts\python.exe manage.py run_scheduler --interval 30
```

This runs deadline jobs and notification delivery every 30 seconds. On a hosted deployment, run it as a worker process or schedule `manage.py run_jobs`. Restart the worker after changing sender configuration. Do not start multiple local workers intentionally; short database claims coordinate overlapping workers.

Set `PUBLIC_APP_URL` to the actual HTTPS app URL for clickable email links. Until the app is hosted, emails direct users to sign in to FoodLoop rather than including a broken localhost link. The phone's USB connection is needed for local app access, independently of Gmail delivery.

## Delivery behavior

- Each email has a single recipient and a stable Message-ID.
- Successful deliveries are recorded and not selected again.
- SMTP happens outside database transactions so a slow mail server does not hold the application's write lock.
- Failed deliveries retry with backoff, up to five attempts; error records omit server responses and credentials.
- Opted-out users, inactive accounts, invalid/missing email addresses and notifications older than 24 hours are skipped.
- A worker claim expires if it crashes. As with other SMTP queues, delivery followed by a worker crash before recording success can result in a duplicate; strict exactly-once external delivery is not claimed.

Development tests use Django's in-memory backend and do not send email. The Gmail helper only checks authentication. Gmail authentication is now verified and the local 30-second worker is running. One actual queued notification was successfully submitted through Gmail SMTP. Inbox placement still needs confirmation by the recipient.
