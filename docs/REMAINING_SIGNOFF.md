# Remaining SRS sign-off

These items are open. They are not hidden behind a claim that all requirements are complete.

| Item | What is ready | What is still needed |
| --- | --- | --- |
| Public hosting | Source package, Dockerfile, PostgreSQL configuration, production static assets, protected photo endpoint, scheduler commands | Hosting account/platform connection and persistent storage; actual deployment and HTTPS/proxy checks. No hosting resource or charge has been created. |
| First-time-user usability | Recorded automated provider task; clear guide and phone forms | A person unfamiliar with the app completes their role's task without help in under 3 minutes. Use the worksheet below. |
| Physical devices | Responsive/engine automation and screenshots | Test on actual Android/iOS phones and a tablet, with the venue's network conditions. |
| Supervisor review | Draft food-sharing terms, safety acknowledgements and privacy notice in the app | Confirm final wording, prototype area, nearby-area assumptions and sample organisations. Lusaka Central and 24-hour pending expiry are provisional defaults. |
| Real-world privacy | Minimal fields, role-limited visibility, private photos, stripped image metadata, audit records | Confirm the legal basis, operational contact, any registration duties and agreed retention period before collecting real partner data. Twelve months is a proposal, not an approved policy. |
| Optional email | Gmail authentication verified; local worker running; one actual queued notification submitted through SMTP | Recipient confirmation of inbox placement; configure the worker separately on the eventual host. |
| Optional CO2 | Positive configurable factor, required source, estimate labelling and tests | An agreed real factor/source. The interface deliberately omits an unsupported estimate. |
| prototype URL and QR | Local fallback and recorded video | Published URL before a meaningful QR code can be created. |

## First-time-user worksheet

Record person, device/browser, start/end time, duration, errors and whether assistance was needed.

| Role | Task from dashboard | Target | Result |
| --- | --- | --- | --- |
| Provider | Publish a complete photo listing | Under 3 minutes without assistance | Pending human trial |
| Recipient | Find suitable food and submit a request | Under 3 minutes without assistance | Pending human trial |
| Recovery partner | Find material for the approved pathway and request | Under 3 minutes without assistance | Pending human trial |
| Administrator | Review complete evidence and approve an organisation with a reason | Under 3 minutes without assistance | Pending human trial |

The recorded automated task timing is an engineering check, not a substitute for this trial.
