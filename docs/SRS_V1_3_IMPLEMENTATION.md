# SRS v1.3 implementation notes

This project treats the v1.3 **Demo** release requirements as the MVP. The operational defaults are seeded in `Platform settings` and can be changed in Django Administration. Do not treat informational meal, weight conversion, or ZMW value estimates as audited financial or nutrition measurements.

## Implemented MVP additions

- Collection handover uses a six-digit code visible to the requesting organisation while a request is ready, plus a QR representation that the provider can scan with a supported device camera. The database stores only a password hash. Codes expire with the listing, are single-use, lock after the configured number of wrong attempts, and attempts are written to the audit log. Manual entry remains available when camera scanning is unavailable.
- Providers record the confirmed quantity and measured kilogram weight. Kilogram listings are prefilled from quantity; litres use the configurable proposal factor and must be reviewed at handover. Other units require a weight entry. Dashboard impact figures use confirmed weight.
- Eligible recipient and recovery organisations are ranked at publication and notified in groups. The next group is notified at the configured portion of a listing's lifetime if no request has been accepted. Releasing accepted quantity after cancellation, expiry, or no-show triggers another ranked group. Duplicate recipients and organisations with active requests are skipped.
- Provider impact statements report confirmed kilograms, estimated human meals, and pathway value estimates in ZMW when administrators configure rates. They identify the calculation basis and state that the statement is informational, with no payment due.
- Recovery reports include a selectable listed/collected/wasted area heat map with a companion table and unit separation. Wasted quantity is expired listed quantity less confirmed collection; withdrawn, removed, and deleted listings are excluded.
- Platform settings include request expiry, re-offer timing and group size, handover attempts, meal weight, litres-to-kilograms proposal, weight limit, matching weights, reverification interval, and pathway value estimates.

## Post-demo scope

The v1.3 requirements identified as post-demo remain future work: SMS and USSD, recurring collection arrangements, physical recovery hubs, network partner workflows, offline-first handover, and the associated advanced operational requirements. These features should not be represented as available in the current MVP.

## Configuration

The migration seeds defaults for a fresh database. Administrators can edit values in Django Administration → Platform settings. `.env.example` also lists deployment defaults. Confirm local value-per-kilogram rates and the litres-to-kilograms proposal before using them in operational reporting.
