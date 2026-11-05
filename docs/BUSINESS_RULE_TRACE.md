# Business rules and use-case traceability

| Rule | Implementation / evidence |
| --- | --- |
| BR-001 Authentication | Protected views, photo endpoint, session logout and direct URL tests. |
| BR-002 Verified organisations | Publication/request guards; TC-04/05 and verification-evidence tests. |
| BR-003 Approved pathway | Discovery hard filter and request eligibility service; TC-09/10. |
| BR-004 No unsuitable human food | Model/form condition validation and discovery/matching/request guard; TC-10. |
| BR-005 Honest provider description | Required listing fields and provider safety acknowledgement; TC-06/07/19. This records acknowledgement rather than independently inspecting food. |
| BR-006 No safety certification | Explicit wording on details, request forms and draft terms. |
| BR-007 Allocation bounds | Database constraints and transactional acceptance; actual SQLite/PostgreSQL race checks. |
| BR-008 Deadline enforced | Discovery, detail/request/transition checks and housekeeping; TC-21. |
| BR-009 Dual confirmation impact | Full-quantity provider confirmation plus recipient receipt; TC-16/17. |
| BR-010 Eligible human recipients; no resale | Admin evidence requirements, role/pathway restrictions and recipient acknowledgement. Real-world behaviour cannot be guaranteed by software. |
| BR-011 No payments | Donation-only model choice; no checkout/payment endpoints; terms explain responsibility for any external money exchange. |
| BR-012 Private pickup details | Accepted-party scope and permission tests; TC-18. Food photos have an authenticated, pathway-scoped endpoint. |
| BR-013 Highest suitable use | Hierarchy guidance in create/edit form and terms. |
| BR-014 Expiry and reservation release | Configurable expiry, cancellation, no-show handling, idempotent deadline tests and scheduler command. |
| BR-015 Immutable administrator audit | Reasoned actions include actor, record and timestamp; deletion test and read-only admin interfaces. |

| Use case | Implementation / verification |
| --- | --- |
| UC-01 Create listing | Listing form, photo validation, safety acknowledgement; TC-06/07 and recorded browser demo. |
| UC-02 Find/request | Matching, filters, request form and stock checks; TC-09 to TC-12 and recorded demo. |
| UC-03 Review request | Acceptance/decline guards, reservation, notification and private-details reveal; TC-13/18. |
| UC-04 Confirm collection | Ready state, both confirmations, accepted quantity, events and impact; TC-15 to TC-17. |
| UC-05 Verify organisation | Evidence/reason checks and administration interface; TC-03 and recorded demo. |
| UC-06 Flag listing | Report form, review queue, dismissal/removal and audit; TC-20 and recorded demo. |
| UC-07 View impact | Scoped listed/collected totals, per-pathway/per-unit tables, configurable meal estimate, optional sourced CO2 and exports; TC-17. |

See SRS_AUDIT.md for all 77 numbered functional and non-functional requirements. Remaining operational and human sign-offs are listed separately in REMAINING_SIGNOFF.md.
