# Connect Gmail to the hosted FoodLoop app

FoodLoop on Render Free cannot reach Gmail SMTP on ports 465/587. Use the Gmail API over HTTPS instead. The existing Gmail app password cannot authorize the API.

## One-time Google setup

1. Open [Google Cloud Console](https://console.cloud.google.com/). Create or select a project for FoodLoop.
2. Enable **Gmail API** under APIs & Services.
3. Configure Google Auth Platform branding and audience for the sender's account. For a test setup, add the Gmail sender as a test user. Request only the `https://www.googleapis.com/auth/gmail.send` scope; FoodLoop does not need permission to read the inbox.
4. Create an OAuth client with application type **Desktop app**. Download its JSON credentials to a private folder outside this repository. Do not send the file or its contents in chat.
5. In PowerShell, run the helper, substituting the JSON path and your actual Gmail address:

```powershell
.\.venv\Scripts\python.exe scripts/connect_gmail.py --client-file 'C:\path\to\client.json' --sender 'your-address@gmail.com'
```

6. Open the printed Google authorization link, sign in as the sender, and approve sending access. The helper receives the callback only on `127.0.0.1`, verifies state and uses PKCE. It saves `.env.gmail-api`, which is ignored by Git, without displaying tokens or sending mail.

The helper waits up to ten minutes. Re-run if the authorization expires. Google can revoke refresh tokens; an external OAuth app left in Testing typically receives a refresh token that expires in seven days when using Gmail scopes. Resolve the appropriate consent/publishing requirements before relying on it for ongoing production delivery. Follow Google's current instructions for the account and audience; don't assume a development consent flow establishes a production email service.

## Connect Render

Save these keys from `.env.gmail-api` directly in the FoodLoop Render service's environment settings, preserving all existing variables:

- `GMAIL_CLIENT_ID`
- `GMAIL_CLIENT_SECRET`
- `GMAIL_REFRESH_TOKEN`
- `DEFAULT_FROM_EMAIL` — the authorized Gmail address or its verified send-as alias
- `EMAIL_BACKEND=core.email_backends.GmailAPIEmailBackend`
- `EMAIL_NOTIFICATIONS_ENABLED=1`
- `PUBLIC_APP_URL=https://foodloop-zambia.onrender.com`

The application intentionally does not auto-load `.env.gmail-api`; authorization alone must not activate sends from local development or change the hosted service. A controlled deployment activates the Render configuration. Keep email notifications disabled until the sender connection is ready. The Gmail API can also serve password-reset emails once its backend is configured.

## Verify

1. Sign in as administrator and open **System status**. Confirm sender configuration and the job cycle timestamp.
2. Use a consenting real test account with a valid email address and email notifications enabled. Trigger an account approval or other expected notification. Do not change unrelated organisations just to test mail.
3. Confirm provider acceptance and receipt in the intended inbox, including spam-folder checks. A database sent timestamp is provider acceptance, not proof of inbox placement.
4. Verify that a failed attempt is retried during a later job cycle. The managed scheduler runs every five minutes while the Render service is awake. Render Free sleeps after inactivity, so background delivery is not continuous while asleep.

Gmail API sends use existing queue leases and retry limits. A network timeout after Gmail accepted a message can still produce a duplicate on retry; exactly-once external delivery is not guaranteed.

References: [Gmail Python quickstart](https://developers.google.com/workspace/gmail/api/quickstart/python), [Gmail send method](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/send), [Google native-app OAuth](https://developers.google.com/identity/protocols/oauth2/native-app), [OAuth token expiration](https://developers.google.com/identity/protocols/oauth2#expiration), [Render Free limitations](https://render.com/docs/free).
