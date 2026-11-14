## Implemented behavior

Builds the Japanese LeadFlow renovation CRM from the approved `doc/` specifications, starting at Phase 0 and implementing FR-01–FR-10. A public demo inquiry is persisted transactionally, appears in the manager's queue, can be assigned to an employee, and proceeds through notes, inspection, multi-item quotation, follow-up task and won/lost reporting. Manager/employee queryset and write scopes prevent cross-owner record access. Every page identifies the project as 自主制作デモ / 架空データ.

Includes customer search/edit/archive, append-only business history, quote edit and sample print view, Decimal tax arithmetic, Tokyo-date dashboard filters and real monthly charts, an idempotent 60-customer/five-employee seed, migrations, hash-locked Python 3.13/Django 6.1.3 dependencies, PostgreSQL 17 Compose/Gunicorn, CI, README and walkthrough. No public deployment or real communications.

## Validation

- `manage.py check`: passed; migration consistency: no changes detected.
- SQLite: **80 pytest tests passed**.
- PostgreSQL 17: **80 pytest tests passed** in Compose's separate test database.
- Clean PostgreSQL initialization/migrations, container build/start/recreation and local HTTP/static requests passed.
- Headless Chromium/Playwright: full intake → assignment → inspection → quote/print → overdue task/completion → won workflow passed; unrelated employee receives 404. Main screens passed 375px viewport/overflow checks; chart rendered; no JavaScript errors.
- Production-mode deployment **security** checks passed without silencing checks.
- Seed idempotence, partial-transaction rollback, quote tampering/rounding, CSRF, direct-URL permissions and Tokyo date boundaries covered by tests. Browser-discovered null-owner/system-actor rendering and assignee defaults have regression tests.

## Decisions and limits

- Follows FR-07's explicit rule: exact decimal subtotal and whole-yen ROUND_HALF_UP tax. Sending a quote synchronizes inquiry status; reversal does not automatically rewind it. Metrics use inclusive Tokyo inquiry-creation-date cohorts. These rules are documented and tested.
- This cloud session's standard Docker build initially failed TLS verification inside pip. A documented temporary Dockerfile mounted the host CA bundle as a BuildKit secret; build passed with TLS and hash verification intact, without embedding the CA. Standard trusted-network Dockerfile retained.
- Full `check --deploy` intentionally reports `mail.E001` for the disabled/dummy mailer. It is not silenced and SMTP is not enabled; actual email is out of scope.
- P1 CSV import/export, advanced reports and native PDF are deferred. Public hosting/hardening and operational work are separate. Remote GitHub Actions execution has not been verified locally.

See `doc/PROGRESS.md` for phase/requirement traceability and detailed evidence; `README.md` for setup/reset and `doc/DEMO_WALKTHROUGH.md` for review steps. Leave open for review; do not merge automatically.
