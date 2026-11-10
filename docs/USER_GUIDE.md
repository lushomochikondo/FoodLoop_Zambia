# FoodLoop Zambia user guide

Start the local server with `.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000` from the project directory. Open http://127.0.0.1:8000 in a browser. All displayed times are CAT (UTC+2). prototype walkthrough records are fictional.

## Providers

1. Sign in as `provider` and select **Create a listing**.
2. Upload a photo of the actual food (JPG, PNG or WebP, under 8 MB). You can preview it before publishing.
3. Enter a positive quantity and unit, food condition, general area, private pickup address and future collection deadline.
4. Choose the highest suitable recovery pathway: people, animals, then compost. A spoiled condition cannot be used for human consumption.
5. Read and tick the safety acknowledgement, then publish the donation. Listings are free; FoodLoop has no payment flow.
6. Review incoming requests on the dashboard. Accepting reserves the requested quantity; a pending request does not reserve stock. Acceptance reveals pickup details to that recipient.
7. Mark the accepted request **Ready for collection**. At handover, select **Confirm full collection**. This records the full accepted quantity. Partial collection is outside the MVP.
8. The recipient must also confirm receipt before the collection contributes to impact totals.

On a listing's detail page, **Edit listing** is available while it is available and has no accepted or collected allocation. Editing cancels pending requests and notifies requesters so they can review the changed details. **Withdraw listing** cancels active requests, releases reservations, and prevents new requests. Completed collections stay in the impact history.

## Recipients and recovery partners

Sign in as `recipient` or `school` for food for people, `farm` for animal feed, or `compost` for organic recovery. Beneficiaries can browse all recovery pathways. Collection requests are limited to the account's approved use. Livestock farmer / animal feed and Composting / organic recovery are available in beneficiary registration alongside human-food programme types. Suitable listings receive match scores and appear first under Recommended; other pathways remain visible for browsing. Matches are ranked by location (30%), deadline urgency (30%), quantity fit (20%) and condition suitability (20%). Each match includes a score and reasons. Organisation preferences and provisional nearby areas can be adjusted by the administrator/configuration.

Use the food, pathway and area filters to find donations. Open a listing, request a quantity, and accept the safety acknowledgement. The exact pickup address and phone remain hidden until acceptance. After collection, confirm the full quantity. Use **Cancel** if the collection cannot proceed. Use **Report a concern** on the listing to flag inaccurate or unsafe information for review.

## Administrators

Sign in as `admin` and choose **Administration**. Review the organisation's eligibility evidence, select Approve, Reject or Suspend, and give a reason. The decision is recorded in the audit trail. Under **Manage accounts & evidence**, create users, assign organisation memberships, maintain verification information, and reset passwords using Django's admin interface. Food-provider and recipient roles are assigned through their organisation; administrator access uses the user's staff permission.

Review reports and record a reason to dismiss them or remove the listing. Removal cancels active requests and releases reservations. Listings can also be removed directly in listing moderation. Administrators may cancel requests, but cannot accept them or confirm collections on behalf of a party. Audit and request-event records cannot be changed or deleted in the application.

## Notifications and impact

The notification count appears in navigation. The inbox shows new requests, decisions, ready/confirmation events, cancellations, deadline warnings and verification changes. Mark individual items or the whole inbox as read. Notifications are private to the signed-in user.

**Your impact** separates listed and collected quantities, keeps kilograms/litres/pieces/trays/bags separate, and reports confirmed kilograms by pathway. Estimated meals use human-consumption kilograms divided by 0.4 kg per meal. The assumption is configurable. There is no invented conversion between units, and CO₂ estimates are omitted until a source and factor are agreed. Filter by dates/pathway and export confirmed collections to CSV.

## Deadlines and fallback

Pending requests expire after 24 hours or the listing deadline, whichever occurs first. Accepted/ready requests without dual confirmation become No-show at the deadline and release their reservations. Housekeeping runs when dashboards/details are opened; unattended processing requires periodically running `manage.py process_deadlines` (see the deployment guide). Once a listing deadline passes, released stock is not available for new requests.

The local copy runs without internet once dependencies are installed. Fonts and decorative images are stored locally. Run `manage.py backup_prototype` before the prototype walkthrough to back up SQLite and uploaded photos. A timestamped backup is saved in `backups/`. A backup includes personal/organisation information; keep it private.

## Profile, installation and notes

Open **Your profile** to update your own name/email. Recipients and recovery partners can set their usual collection quantity and unit to improve quantity-fit scoring. This cannot change verification or account role.

On a listing's **Request history**, expand your request to add collection notes. Notes do not change the original confirmation date used by reports. The listing shows its creation time and donation type; providers can filter their listings by availability/status.

On supported browsers, **Install app** appears when installation is available. Edge also exposes the installed-app option in its browser menu. The app launches in its own window. Offline navigation shows a public connection notice, with no cached private listings or account records.

Your impact now includes a per-pathway, per-unit table, so pieces, bags and trays are never silently excluded or converted to kilograms. Optional CO2 estimates require an agreed source; optional email delivery requires an enabled SMTP account.

## Self-registration

Choose **Create an account** on the sign-in page, or open `/signup/`. Register as a food provider, a recipient for people, an animal-feed partner, or a composting partner. Enter your organisation and contact details, choose your own password, and accept the terms/privacy acknowledgement. Providers must confirm they are authorised to list food; human-food recipients must describe safe handling/storage capacity.

The app signs you into a pending account and notifies the administrator. Only administrator approval enables publishing or requesting food. Public sign-up cannot create administrators or approve organisations. Existing organisations should ask their administrator to add a member.

## Email updates

Under Your profile, set your email address and toggle email updates. Events still appear in the in-app inbox if you opt out. Gmail delivery requires the sender connection and a running worker; see GMAIL_SETUP.md.

## Deleting listings and accepting requests

Providers can choose **Delete listing** on a listing's detail page, including withdrawn listings. Confirm the deletion on the next page. Unused listings and their photos are permanently deleted. Listings with request or moderation history disappear from discovery while their accountability records are retained. Active requests are cancelled and reservations released; completed collection totals remain unchanged.

Recipients choose **Request food**, enter a quantity, accept the safety acknowledgement, and send the collection request. The listing's provider can then use **Accept** under **Incoming collection requests** on that listing's page or on the dashboard. After acceptance, the recipient sees private pickup details. Administrator verification and provider acceptance are separate actions.
