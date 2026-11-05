# Complete SRS v1.1 requirement audit

Source: FoodLoop_Zambia_SRS_v1.1.pdf, FLZ-SRS-001, 4 November 2026. All 52 FR and 25 NFR identifiers were extracted from the supplied PDF.

**Local verification is not final SRS sign-off.** External decisions and environment checks remain explicitly open below. Passing test counts are not used as a substitute for the requirement matrix.

| ID | Release / priority | Requirement | Status | Evidence / remaining condition |
| --- | --- | --- | --- | --- |
| FR-001 | Demo / Must | The system shall allow a user to register or be created with a defined account role (provider, recipient, recovery partner or administrator). For the demonstration, administrator-created accounts are acceptable. | Implemented and locally verified | TC-01 plus SignupTests: public registration creates pending provider/recipient/recovery memberships; only administrators can approve access or create staff accounts.  |
| FR-002 | Demo / Must | The system shall allow registered users to sign in and sign out. | Implemented and locally verified | TC-01: sign-in/sign-out and ended session.  |
| FR-003 | Demo / Must | The system shall restrict screens and actions according to the user's role, enforced on the server. | Implemented and locally verified | TC-02: direct URL restrictions; role and ownership tests.  |
| FR-004 | Demo / Must | The system shall allow an administrator to review and update organisation verification status. | Implemented and locally verified | TC-03: reasoned verification with required evidence.  |
| FR-005 | Post-demo / Should | The system should allow users to update basic profile information. | Implemented and locally verified | Profile and matching preferences test; role escalation inputs ignored.  |
| FR-006 | Demo / Must | The system shall allow a verified provider to create a surplus-food listing. | Implemented and locally verified | TC-06: provider publishes a valid listing.  |
| FR-007 | Demo / Must | Each listing shall capture food name or type, quantity, unit, area/location, condition, collection deadline, a single recovery pathway, and listing type. | Implemented and locally verified | TC-06/07: required fields, positive quantity, explicit Donation type.  |
| FR-008 | Demo / Must | The system shall allow a provider to edit a listing while it is in an editable status (Available with no accepted requests). | Implemented and locally verified | Edit guards and pending-request notification tests.  |
| FR-009 | Demo / Must | The system shall allow a provider to mark a listing as withdrawn. | Implemented and locally verified | Withdrawal cancels active requests and releases allocations.  |
| FR-010 | Demo / Must | The system shall display listing status, creation time and collection deadline. | Implemented and locally verified | TC-06: status, created date and deadline displayed in CAT.  |
| FR-011 | Demo / Should | The system should allow a short description and handling or storage notes. | Implemented and locally verified | Listing notes form and detail rendering; handling/storage guidance.  |
| FR-012 | Demo / Must | The system shall display available listings to authorised users. | Implemented and locally verified | TC-09: role/pathway-scoped discovery.  |
| FR-013 | Demo / Must | The system shall display key listing details before a recipient submits a request. | Implemented and locally verified | Detail view tests and recorded browser workflow.  |
| FR-014 | Demo / Should | The system should allow filtering by recovery pathway, area, food type and availability. | Implemented and locally verified | TC-09: food/area/pathway/availability filters.  |
| FR-015 | Demo / Must | The system shall prevent requests on listings that are withdrawn, expired, removed, fully allocated or otherwise unavailable. | Implemented and locally verified | TC-12/21; withdrawal/removal/allocation guards.  |
| FR-016 | Demo / Must | The system shall identify potentially suitable listings using location, quantity, urgency, condition and intended-use suitability (scoring method in 4.4.1). | Implemented and locally verified | Matching score tests and browser-visible reasons.  |
| FR-017 | Demo / Must | The system shall never recommend a listing for human consumption when it is marked unsuitable for human consumption. | Implemented and locally verified | TC-10: human pathway hard filter and spoiled-condition rejection.  |
| FR-018 | Demo / Should | The system should show the reasons a listing matched (for example, 'Same area, 6 hours left'). | Implemented and locally verified | TC-11: visible scores and match reasons.  |
| FR-019 | Demo / Must | The system shall rank listings nearer their collection deadline higher when other conditions are equal. | Implemented and locally verified | TC-11: nearer-deadline ranking with other factors equal.  |
| FR-020 | Demo / Must | A verified recipient or recovery partner shall be able to request an available listing for its approved pathway. | Implemented and locally verified | TC-04/12: verified recipient request, correct pathway, valid quantity.  |
| FR-021 | Demo / Must | The system shall record the requesting organisation, listing, requested quantity and request date/time. | Implemented and locally verified | Request model metadata and timestamped request event.  |
| FR-022 | Demo / Must | The provider shall be able to accept or decline a request. | Implemented and locally verified | Acceptance/decline state machine and browser workflow.  |
| FR-023 | Demo / Must | Quantity is reserved only when a request is accepted. The system shall prevent accepted allocations from exceeding the available quantity. | Implemented and locally verified | TC-13/14: reservation on acceptance; actual SQLite/PostgreSQL races.  |
| FR-024 | Demo / Must | The system shall display current request status to the relevant users. | Implemented and locally verified | Request statuses on dashboard/details.  |
| FR-025 | Demo / Must | The system shall allow relevant users to move a confirmed request through the defined collection statuses. | Implemented and locally verified | TC-15: transitions restricted to relevant parties.  |
| FR-026 | Demo / Must | Supported statuses: Pending, Accepted, Ready for Collection, Collected, Declined, Cancelled, Expired and No-show. | Implemented and locally verified | All eight statuses represented and lifecycle tests.  |
| FR-027 | Demo / Must | The system shall record the date and time of each status change. | Implemented and locally verified | TC-15: persistent per-transition event timestamps.  |
| FR-028 | Demo / Must | A request becomes Collected only when the provider records the confirmed quantity and the recipient confirms receipt. Collection notes may be added. | Implemented and locally verified | TC-16/17: provider full-quantity handover plus receipt; collection notes.  |
| FR-029 | Demo / Must | The dashboard shall show the total quantity listed in the selected period. | Implemented and locally verified | Impact date filters and listed-by-unit totals.  |
| FR-030 | Demo / Must | The dashboard shall show the total quantity confirmed as collected. | Implemented and locally verified | TC-17: confirmed collection totals only.  |
| FR-031 | Demo / Must | The dashboard shall show the quantity diverted through each recovery pathway. | Implemented and locally verified | Per-pathway, per-unit report; no invented conversions.  |
| FR-032 | Demo / Must | The system shall distinguish listed from collected quantities so uncollected food is never counted as recovered. | Implemented and locally verified | TC-17: listed and collected displayed separately.  |
| FR-033 | Post-demo / Should | The system should allow filtering of impact summaries by date range and pathway. | Implemented and locally verified | Date/pathway report filters and CSV export.  |
| FR-034 | Demo / Must | The administrator shall be able to view accounts and verification status. | Implemented and locally verified | Administrator account/evidence interface.  |
| FR-035 | Demo / Must | The administrator shall be able to approve, reject or suspend organisation access. | Implemented and locally verified | Approval/rejection/suspension with evidence and reasons.  |
| FR-036 | Demo / Must | The administrator shall be able to review and remove listings that violate platform rules. | Implemented and locally verified | Moderation removal with cancellation/release.  |
| FR-037 | Demo / Must | The system shall maintain an audit record of verification, suspension and removal actions, showing who acted, what changed and when. | Implemented and locally verified | Actor/record/action/time audit; no edit/delete interface.  |
| FR-038 | Demo / Must | The system shall require provider organisations to be verified by an administrator before their listings become visible to others. | Implemented and locally verified | TC-05: unverified provider blocked and listing hidden.  |
| FR-039 | Demo / Should | The listing type shall default to Donation (free). Other types (for example reduced price arranged outside the platform) are reserved for future use. | Implemented and locally verified | Explicit donation-only type and free-donation interface.  |
| FR-040 | Demo / Must | The system shall require the provider to tick a safety acknowledgement (Section 11) before a listing is published. | Implemented and locally verified | TC-19: provider acknowledgement required.  |
| FR-041 | Demo / Must | Before a request is accepted, listings shall show only the general area. The exact pickup address and contact details shall be shown only to the provider and, after acceptance, to the accepted recipient. | Implemented and locally verified | TC-18: exact address/contact hidden before acceptance.  |
| FR-042 | Post-demo / Should | The system should automatically expire Pending requests that are not decided within a configured period or before the listing deadline. | Implemented and locally verified | Configured pending expiry; tested idempotent deadline jobs.  |
| FR-043 | Demo / Should | Recipients shall be able to flag a listing (for example misdescribed or unsafe). Flags appear in an administrator review queue. | Implemented and locally verified | TC-20 and recorded report/review workflow.  |
| FR-044 | Demo / Should | The system should show in-app notifications and an unread count for new requests, decisions, ready-for-collection updates and expiring listings. | Implemented and locally verified | Private inbox/unread counts; event and deadline notifications.  |
| FR-045 | Post-demo / Could | The system could allow one optional photo per listing, compressed for low- bandwidth use. | Implemented and locally verified | Valid compressed image upload, preview, metadata stripping, protected delivery.  |
| FR-046 | Demo / Should | The dashboard shall show kilograms diverted from disposal and estimated meals provided, using a documented, configurable assumption (default 0.4 kg per meal). | Implemented and locally verified | Confirmed human kg / configurable positive meal weight.  |
| FR-047 | Demo / Should | The listing form shall explain the recovery hierarchy (people first, then animals, then compost) and prompt the provider to choose the highest suitable pathway. | Implemented and locally verified | Hierarchy guidance in listing form and terms.  |
| FR-048 | Post-demo / Should | The system should allow an administrator to reset a user's password. | Implemented and locally verified | Django admin password-reset acceptance test.  |
| FR-049 | Post-demo / Should | The system should mark an uncollected Ready request as No-show after the deadline and release its quantity. | Implemented and locally verified | Deadline/no-show tests release reserved quantity once.  |
| FR-050 | Post-demo / Could | The dashboard could show estimated CO2e avoided, using a documented emission factor with its source stated. | Configured capability; source pending | Configurable optional factor and source; labelled estimate; test factor only. An agreed real emission factor/source is not supplied; no real CO2 claim is displayed. |
| FR-051 | Post-demo / Could | The system could send email notifications for the same events. | Verified through Gmail | Opt-in SMTP queue implemented; in-memory delivery and duplicate-prevention tested. Gmail authenticated; notification worker running; one queued notification successfully submitted through SMTP. |
| FR-052 | Demo / Must | The system shall require the requester to tick a safety acknowledgement (Section 11) before submitting a request. | Implemented and locally verified | TC-19: recipient safety acknowledgement required.  |
| NFR-001 | Demo / Should | In a usability check, a first-time user shall be able to complete the main task for their role from the dashboard (for example, a provider creating a listing) within 3 minutes without assistance. | Human validation pending | Scripted task recorded; first-time-human timed trial still required. Scripted automation cannot establish first-time-user usability. |
| NFR-002 | Demo / Must | Forms shall use clear labels, safe defaults and validation messages that explain how to correct errors. | Implemented and locally verified | Field validation and labels; automated accessibility checks.  |
| NFR-003 | Demo / Must | The system shall use consistent terminology for food condition, recovery pathway and listing and request status. | Implemented and locally verified | Controlled choices, Ready for Collection wording, status colours.  |
| NFR-004 | Demo / Should | For the demonstration dataset and normal network conditions, common pages should load within 3 seconds. | Local verification; hosted pending | Local load timings in accessibility/performance report; hosted measurements pending. No public deployment/network timing has been measured. |
| NFR-005 | Demo / Should | Search and filtering should return results within 3 seconds. | Local verification; hosted pending | Local filtered navigation tests/timings; hosted network measurements pending. Local filtering has been tested; hosted timing remains. |
| NFR-006 | Demo / Must | The system shall require authentication for protected functions. | Implemented and locally verified | Protected view and photo access tests.  |
| NFR-007 | Demo / Must | Role-based access control shall be enforced on the server, not only by hiding interface elements. | Implemented and locally verified | Role/ownership guards at view and service layers.  |
| NFR-008 | Demo / Must | Passwords shall be stored using a recognised secure password-hashing mechanism. | Implemented and locally verified | Production Django password hashing; test-only MD5 override is isolated to tests.  |
| NFR-009 | Demo / Must | The system shall validate input and protect against common web vulnerabilities (including injection, cross-site scripting and cross-site request forgery). | Implemented and locally verified | CSRF, escaped script inputs, SQL-like search, quantity and image validation tests.  |
| NFR-010 | Demo / Must | Users shall access only the personal and operational information necessary for their role. | Implemented and locally verified | Private address/contact, organisation scopes, notification and photo permissions.  |
| NFR-011 | Demo / Must | Listing and request records shall persist across page navigation and sign-out. | Implemented and locally verified | Record persistence through logout/sign-in test.  |
| NFR-012 | Demo / Must | The system shall validate quantities and reject negative or zero values. | Implemented and locally verified | Form validators and database quantity/allocation constraints.  |
| NFR-013 | Demo / Must | The system shall prevent over-allocation of a listing through concurrent or repeated requests, using database transactions and locking. | Implemented and locally verified | Actual concurrent acceptance tests using file-backed SQLite and PostgreSQL.  |
| NFR-014 | Demo / Should | The MVP shall be deployable in a documented demonstration environment. | Local verified; deployment pending | Local run and production configuration documented; Docker image not run here. The local environment runs; public hosting and Docker build still require an environment. |
| NFR-015 | Post-demo / Should | The application shall use a modular structure that allows future addition of messaging, maps, payments or other integrations. | Implemented and locally verified | Separate models/forms/services/matching/views/jobs; configurable integrations.  |
| NFR-016 | Demo / Must | Errors shall be handled without exposing passwords, secret keys or stack traces to end users. | Implemented and locally verified | Safe production 403/404/500 pages and DEBUG-disabled smoke test.  |
| NFR-017 | Demo / Should | The application should support current versions of commonly used browsers. | Engine verification; device sign-off pending | Automated Edge, Firefox and WebKit checks; physical devices still require sign-off. Browser engines are automated; physical phone/tablet verification is not claimed. |
| NFR-018 | Demo / Must | Text, controls and status indicators shall remain readable and usable on mobile-sized screens, with sufficient colour contrast. | Implemented and locally verified | 11 viewport widths; automated A/AA scan and keyboard/mobile menu checks.  |
| NFR-019 | Demo / Should | Pages should stay lightweight for users on limited mobile data: no unnecessary large scripts, and uploaded images compressed. | Implemented and locally verified | Bundled WOFF2 font, compressed provider photos, local assets, small scripts.  |
| NFR-020 | Demo / Must | All timestamps shall be stored in UTC and displayed in CAT (UTC+2). Deadlines shall be evaluated consistently. | Implemented and locally verified | UTC-aware storage; explicit UTC-to-CAT date assertion and displayed CAT labels.  |
| NFR-021 | Demo / Should | A documented procedure shall allow the application to run on a local machine, with demo data loaded, if internet access fails. | Implemented and locally verified | Recorded full local workflow with external requests denied; local fallback guide.  |
| NFR-022 | Demo / Must | Collection and handling of personal data shall follow Zambia's Data Protection Act, 2021 principles: collect only what is needed, state the purpose, limit access, and protect it (Section 7.4). | Technical controls; review pending | Purpose/privacy notice and role restrictions implemented; legal/retention sign-off pending. Supervisor/legal review and retention decision remain external decisions. |
| NFR-023 | Demo / Should | Audit records shall not be editable or deletable through the application interface. | Implemented and locally verified | Admin audit deletion blocked; log/event read-only interfaces.  |
| NFR-024 | Demo / Should | The hosted system shall use HTTPS, secure session cookies and automatic session expiry. | Production-mode verified; hosted pending | Production HTTPS/secure cookies/HSTS/session configuration; hosted verification pending. Production smoke checks are local, not proof of a live HTTPS deployment. |
| NFR-025 | Demo / Should | A database backup or export of the demonstration data shall be taken before the demonstration. | Implemented and locally verified | Database/media backup and restored-data test; fresh local backup created.  |

## Acceptance scenarios TC-01 to TC-22

| Scenario | Local evidence |
| --- | --- |
| TC-01 | AcceptanceTests.test_tc01_all_four_roles_sign_in_and_out |
| TC-02 | WorkflowTests.test_server_permissions |
| TC-03 | AcceptanceTests.test_tc03_verification_evidence_approval_enables_request |
| TC-04 | AcceptanceTests.test_tc04_and_tc05_unverified_access_blocked |
| TC-05 | AcceptanceTests.test_tc04_and_tc05_unverified_access_blocked |
| TC-06 | AcceptanceTests.test_tc06_tc07_listing_fields_and_validation |
| TC-07 | AcceptanceTests.test_tc06_tc07_listing_fields_and_validation |
| TC-08 | MVPTests.test_edit_notifies_pending_requesters; test_withdraw_releases_allocations_and_cancels_pending |
| TC-09 | AcceptanceTests.test_tc09_tc10_pathway_area_food_and_availability |
| TC-10 | AcceptanceTests.test_tc09_tc10_pathway_area_food_and_availability |
| TC-11 | AcceptanceTests.test_tc11_deadline_ranking_and_visible_reasons |
| TC-12 | AcceptanceTests.test_tc12_and_tc19_request_quantity_and_acknowledgement |
| TC-13 | WorkflowTests.test_overallocation_and_release |
| TC-14 | AcceptanceTests.test_tc14_concurrent_last_unit; qa/concurrent_acceptance.py on PostgreSQL |
| TC-15 | AcceptanceTests.test_tc15_tc16_tc17_and_tc18_collection_impact_and_privacy |
| TC-16 | AcceptanceTests.test_tc15_tc16_tc17_and_tc18_collection_impact_and_privacy |
| TC-17 | AcceptanceTests.test_tc15_tc16_tc17_and_tc18_collection_impact_and_privacy |
| TC-18 | AcceptanceTests.test_tc15_tc16_tc17_and_tc18_collection_impact_and_privacy |
| TC-19 | AcceptanceTests.test_tc12_and_tc19_request_quantity_and_acknowledgement |
| TC-20 | MVPTests.test_admin_review_removes_and_audits_listing; qa/acceptance_browser.py |
| TC-21 | AcceptanceTests.test_tc21_deadline_blocks_request |
| TC-22 | qa/acceptance_browser.py: external network denied during complete local workflow |

## Evidence artifacts

- `core/tests.py`, `core/test_mvp.py`, `core/test_acceptance.py`: automated behavior/security checks.
- `qa/acceptance-browser-results.json` and `qa/demo-recording/FoodLoop-complete-demo.webm`: isolated browser flow and local-offline proof.
- `qa/responsive-*-results.json`: layout/font checks across 11 widths.
- `qa/accessibility-performance-results.json`: automated axe checks, local navigation timings and PWA installability.
- `qa/production_smoke.py`: DEBUG-disabled page/static/security checks; production photo permission tests run through the normal suite.
- `docs/REMAINING_SIGNOFF.md`: external items that cannot be truthfully marked complete.

## Business rules and workflows

BR-001 to BR-015 are covered by authentication/verification/pathway guards, provider acknowledgement, donation-only listings, reservation bounds, deadlines, dual confirmations, terms/privacy, and immutable audit records. UC-01 to UC-07 are exercised by the request/listing/collection/moderation/report tests and recorded browser workflow. Open supervisory decisions are not counted as completed software features.

## Scope boundary

The implemented application covers the numbered functional requirements, including optional local capabilities for photos, profiles, configurable CO2 estimates and queued email. Payments, WhatsApp/SMS/USSD, AI matching, live maps, partial collection, nationwide deployment and native mobile apps are explicitly outside the SRS MVP. Section 17 future ideas remain a roadmap, not an unimplemented MVP requirement.
