# Verification evidence

- Automated suite: 42 tests passed on SQLite and 42 on local PostgreSQL 17.11. This is one suite exercised on two database engines, not 84 distinct scenarios.
- Actual simultaneous acceptance of the last kilogram: one accepted, one blocked, on SQLite and PostgreSQL.
- Responsive checks: {'edge': 124, 'firefox': 124, 'webkit': 124}; total 372, across 11 widths from 320 to 1920 pixels. Inter loaded throughout and no horizontal overflow was detected.
- Automated WCAG A/AA checks: 48 role/page/width checks, no reported violations after fixes. This does not replace a complete manual accessibility audit.
- Local navigation timings: median 113 ms, maximum 594 ms. These are local developer-machine results, not hosted-network guarantees.
- PWA: manifest validation, Edge installability and service-worker offline page verified.
- Production-mode smoke: HTTPS redirect/HSTS, sign-in page and hashed CSS/font/image/scripts pass locally with DEBUG disabled.
- Backup: actual local SQLite/media backup created; a separate fixture backup was restored and checked in the suite.
- prototype walkthrough: isolated full workflow recorded with external network requests denied; actual local data was not used or modified by the recording script.

See SRS_AUDIT.md for requirement-level evidence and REMAINING_SIGNOFF.md for outstanding human/external checks. Docker has not been built here because Docker is unavailable. No public deployment is claimed.

## Self-registration follow-up

The suite now has 49 passing tests on SQLite, including seven new registration/security/validation tests. The previous PostgreSQL run covered the pre-registration 42-test suite; the additional registration tests were not rerun on PostgreSQL in this follow-up. The signup page passed five responsive widths (320, 390, 768, 820, 1440) and five automated A/AA accessibility scans. The sign-up link was clicked in the browser, and the page was opened on the USB-connected Pixel 6.
