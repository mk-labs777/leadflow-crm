# LeadFlow CRM — Product Requirements

**Document ID:** LF-REQ-001  
**Version:** 1.0  
**Date:** 2026-11-14  
**Status:** Approved baseline for implementation; changes require documentation  
**Repository:** https://github.com/mk-labs777/leadflow-crm

## 1. Purpose and positioning

LeadFlow CRM is a **self-initiated portfolio demonstration**, developed from scratch to show prospective customers on the Japanese freelance marketplace Coconala what a small-business CRM implementation can accomplish.

The fictional client is a Japanese home-renovation contractor with roughly five employees. The business receives inquiries through a website and telephone, and currently relies on disconnected email, Excel sheets, and informal notes. LeadFlow demonstrates an end-to-end replacement for the *inquiry-to-quotation* workflow.

**Representation rule:** The project must be labelled **「自主制作デモ / 架空データ」** or equivalently conspicuous Japanese wording. Do not assert that a real client commissioned, used, or benefited from the system. Do not fabricate measured financial or operational improvements. Use only synthetic personal data.

## 2. Objectives and success criteria

1. Prove that public website inquiries are persisted automatically and appear in an internal CRM without manual copying.
2. Centralise customers, inquiries, owners, interaction history, quotations, appointments, and follow-up tasks.
3. Let managers identify unanswered work, overdue tasks, and pipeline outcomes from database-derived metrics.
4. Present a polished, understandable Japanese business interface that can be demonstrated in 3–5 minutes.
5. Make the system reproducible: a new developer can set it up from README instructions, seed fictitious data, and run tests.

**Definition of MVP done:** All P0 functional requirements below pass the documented acceptance tests; no fake buttons or hardcoded dashboards are presented as functional; security-critical permissions pass automated tests; local Docker startup succeeds; and a reviewer can follow the entire end-to-end workflow.

## 3. Intended users and roles

| Role | Description | Authority |
| --- | --- | --- |
| Public visitor | Person submitting a fictional inquiry on the public demo form | Submit inquiry only; no CRM access or record lookup |
| Employee | Assigned sales/renovation representative | View and update only assigned inquiries and their related data; view customers linked to those inquiries or created by them; manage own assigned tasks/quotes |
| Manager | Team lead | View and manage all company records, staff assignments, dashboard, and exports; manage user accounts through secured administration |

The system is **single-company**, not multi-tenant. Use Django authentication with explicit group/permission checks. A user's `is_staff` flag alone must not substitute for the domain role unless the architecture explicitly enforces the policy.

For employees, unassigned inquiries are not accessible by default. Managers allocate them. All authorization must be enforced at the queryset and write-operation levels, including direct URL access.

## 4. Business workflow

1. A website visitor submits an inquiry with their name, email, category, subject, and details (phone optional).
2. The server validates the request and saves the new inquiry transactionally. It links to an existing customer when an unambiguous normalized email match exists; otherwise it creates a customer. It must **not** overwrite existing customer identity/contact data from an unauthenticated submission.
3. The new inquiry appears as **新規受付 (New)**, source **Web form**, with an activity entry and no assigned employee.
4. A manager assigns it to an employee. Assignment is recorded in its activity history.
5. The employee contacts the customer, records notes, and schedules a site inspection.
6. The employee creates a quotation, enters line items, and marks it sent. The CRM can display a print-friendly quotation in Japanese.
7. Follow-up tasks record the next action and deadline; overdue incomplete tasks appear on the employee and manager dashboards.
8. An authorized user records the outcome as won (成約) or lost (失注). A lost reason can be recorded in notes; a structured reason is optional.

### Inquiry statuses

| Code | Japanese label | Meaning |
| --- | --- | --- |
| `new` | 新規受付 | Newly received and not yet handled |
| `contacted` | 初回対応済 | Initial contact completed |
| `inspection_scheduled` | 現地調査予定 | Visit/inspection appointment arranged |
| `quotation_sent` | 見積提出済 | Quotation has been sent |
| `won` | 成約 | Customer accepted and contract outcome recorded |
| `lost` | 失注 | Opportunity closed without a contract |

Status updates must be authorized, validated, timestamped and added to activity history. Permit deliberate corrections to earlier states; do not force an artificial one-way workflow. Quotation status and inquiry status are separate fields; when a quotation is marked *sent*, offer an explicit synchronized inquiry update, or implement a documented rule and test it. Do not silently make contradictory states.

## 5. P0 functional requirements — required for the MVP

Every requirement has an identifier. Tests and pull requests should reference these IDs.

### FR-01 — Authentication and authorization

- Django login/logout and password hashing, configured without hardcoded passwords.
- Manager and Employee roles with server-side access restrictions, including create/edit/read/delete and exports.
- Protect every internal page from anonymous users; require POST and CSRF for state-changing actions.

**Acceptance:** An anonymous GET of `/dashboard/` redirects to login. An employee cannot view or mutate another employee's inquiry, even by guessing its ID. A manager can assign an unassigned inquiry.

### FR-02 — Customer records

- Create, view, edit and search customer records.
- Fields: name, email, phone, address (optional), notes, creator, created/updated timestamps.
- Customer page shows all inquiries visible to that user and associated history.
- Search by name, email, or phone, with case-insensitive email handling.
- Prefer archive/deactivate over irreversible deletion of customers with history.

**Acceptance:** A newly registered customer survives page reload and appears in search. Employees cannot retrieve customers outside their permitted scope.

### FR-03 — Public inquiry intake

- Public form fields: name*, email*, phone, renovation category*, subject*, inquiry detail*. Clearly state that the form is a demo; do not collect genuine personal information.
- Categories: kitchen, bathroom, exterior/roof, interiors, other; Japanese labels.
- Validate length and field formats; protect against spam and excessive submission volume with a practical rate-limiting approach and a honeypot or equivalent.
- Create an inquiry and an initial activity event in one database transaction.
- Normalize email and use it for deterministic matching only when one customer unambiguously matches. Flag ambiguous matches for manager review rather than merging data indiscriminately. Never reveal whether an email matches existing customers to the public visitor.
- Provide a confirmation page, without revealing internal record details.

**Acceptance:** A valid form submission persists one inquiry linked to a customer, and the record appears in a manager's unassigned inquiry queue. A second inquiry from the same normalized email creates another inquiry linked to the same unambiguous customer. Invalid submissions create no partial records.

### FR-04 — Inquiry management

- Create internal inquiries from CRM; list/search/filter by status, assigned employee and customer.
- Detail page: customer, service category, description, source, status, owner, timestamps, notes, tasks, appointments and quotations.
- Manager-only assignment/reassignment; authorized employee can update status and notes on their inquiry.
- Record assignment and status changes in an append-only interaction history with timestamp, actor, action and optional note.
- Never treat ownership visible in the browser as proof of permission.

**Acceptance:** Manager assignment makes a previously unassigned inquiry visible to its new owner. Assignment and status changes generate distinct history records. Other employees receive a denied response.

### FR-05 — Activities and history

- Manual note entries for calls, visits and customer communications.
- Automatic events for intake, assignment, status change, quotation creation/sending and task completion.
- Display newest first or in an explicit chronological timeline; include actor and time.

**Acceptance:** Adding a note persists and appears after refresh; changing a status produces a traceable event.

### FR-06 — Inspections / appointments

- Create, edit or cancel an inspection appointment associated with an inquiry.
- Fields: scheduled start, optional end, employee, location/notes, and status (`scheduled`, `completed`, `cancelled`).
- Display upcoming appointments in the inquiry detail and the owner's task/appointments page.

**Acceptance:** An appointment scheduled for a future date appears in the appropriate list; an employee cannot edit an unrelated inquiry's appointment.

### FR-07 — Quotations

- Create and edit quotations for an inquiry with a title, issue date, optional validity date, status (`draft`, `sent`, `accepted`, `rejected`), and multiple line items.
- Item fields: description, quantity (decimal), unit price in JPY (decimal), and line amount. Compute subtotal, tax and total on the server; client-side previews are optional.
- For the MVP, support a **single quotation-level consumption tax rate**, default 10%, displayed explicitly; document that reduced-rate mixed-tax invoices are out of scope.
- Use `Decimal`, not binary floating point, for monetary calculations. Document rounding: calculate unrounded line amounts, subtotal, then round tax to whole yen using `ROUND_HALF_UP`; total = subtotal + rounded tax. Reject negative amounts and invalid quantities.
- Provide a printable HTML quotation with a clear **SAMPLE / DEMO** label; native PDF generation is optional.

**Acceptance:** Two known line items produce mathematically correct subtotal/tax/total, reload consistently, and print without exposing internal edit controls.

### FR-08 — Follow-up tasks

- Create, update, complete and reopen follow-up tasks linked to inquiries; include title, assignee, due date, optional note, timestamps.
- Overdue means `due_date < today in Asia/Tokyo` and the task is not completed.
- Managers see all company tasks; employees see only their assigned tasks, subject to inquiry access policy.

**Acceptance:** A task due yesterday appears as overdue until completed; completed tasks are excluded from overdue counts.

### FR-09 — Dashboard and reports

- Manager dashboard: total customers, new/unassigned inquiries, active inquiries, overdue tasks, quotations sent, won inquiries, and conversion rate.
- Employee dashboard: the same metrics where meaningful but scoped to assigned records. No company-wide record leakage.
- Monthly inquiry trend chart, based on persisted records, with an empty state when no data exists.
- Define conversion rate as `won / (won + lost) * 100` for closed inquiries in the chosen period; show **N/A** if no closed inquiries. Avoid denominators that silently include all new leads.
- Define date-filter semantics and timezone. Dashboard metrics must be computed from real database queries.

**Acceptance:** Seeded records produce expected counts; updating an inquiry from `lost` to `won` changes the conversion rate on refresh; empty datasets do not cause errors.

### FR-10 — Sample data and portfolio walkthrough

- A reproducible, idempotent command produces ~50–100 explicitly fictional customers, ~5 demo employees, representative inquiries, appointments, tasks and quotations.
- Example emails use `example.test` or similarly reserved domains, with no real phone/address identifiers.
- Do not ship known shared credentials in public documentation. Allow demo-account setup through local environment variables or a documented password-reset command.
- A walkthrough demonstrates intake → manager assignment → inspection → quote → follow-up → won/lost → dashboard.

**Acceptance:** Executing the seed command twice does not double the intended sample dataset. A reviewer can follow the documented scenario without guesswork.

## 6. P1 desirable enhancements (only after P0 is stable)

- Validated CSV customer/inquiry **import** with column mapping, preview, reject report and deduplication; manager CSV export with spreadsheet formula-injection protection.
- More advanced reports, such as inquiry source and staff workload, with clear metric definitions.
- Saved filters, pagination for large tables, and more polished mobile navigation.
- Printer-optimised PDF quotation if the HTML print view proves insufficient.

P1 work must not silently displace missing P0 features.

## 7. Explicitly out of scope for the first release

Direct Gmail/IMAP ingestion, sending real emails or SMS, accounting/invoicing/payments, inventory, construction-site project management, AI-generated responses, public APIs/webhooks, multi-tenant accounts, complex workflow builders, and Kubernetes deployment. External integrations may be proposed later but require a separate specification and credentials/security review.

## 8. Usability requirements

- Every user-facing interface and validation message is in **Japanese**; developer documentation may be in English.
- Desktop-first with functional responsive mobile layouts (approximately 375px phone width and up).
- Consistent navigation, clear forms, status labels, loading/empty/error/success states and accessible keyboard focus.
- Use real data in screenshots and charts only if synthetic; do not misrepresent mockups as functional screens.
- Avoid gratuitous animations or unnecessary frontend complexity.

## 9. Nonfunctional requirements and safety boundaries

| ID | Requirement | Verification |
| --- | --- | --- |
| NFR-01 | Source controlled in `mk-labs777/leadflow-crm`; develop via PRs | Git history and PR |
| NFR-02 | Local startup via Docker Compose with PostgreSQL | Clean-start smoke test |
| NFR-03 | Automated unit, integration and permission tests | Test run output |
| NFR-04 | No committed credentials, tokens or real customer data | Secret scan/manual review |
| NFR-05 | Proper CSRF, server validation, escaped templates and privilege checks | Security tests |
| NFR-06 | `DEBUG=False` production mode and safe env configuration | `manage.py check --deploy` |
| NFR-07 | Dates stored with timezone awareness and displayed in Asia/Tokyo | Date-boundary tests |
| NFR-08 | No real email delivery or unapproved public deployment | Configuration check |
| NFR-09 | App supports basic navigation on phone and desktop | Browser smoke tests |

The MVP is a **portfolio demonstration**, not authorization to process real individuals' personal information. A real customer deployment would require a separate privacy/security assessment, hardening, backup and recovery planning, monitoring, incident response and operational agreements.

## 10. Acceptance walkthrough (manual, end-to-end)

1. Start a clean database and seed fictitious users/sample data.
2. Sign in as manager; confirm an unassigned-inquiry queue exists.
3. In a separate private browser session, submit a fictitious inquiry using the public form.
4. As manager, verify customer matching, inquiry source/status and initial history event.
5. Assign the inquiry to an employee; confirm it appears in that employee's account and not in an unrelated employee's account.
6. Record a contact note and future inspection appointment.
7. Create a quote with at least two line items; verify yen totals and print view.
8. Mark the quote sent and move the inquiry to the documented pipeline stage.
9. Create an overdue task, check dashboard and task list, complete it, and verify the overdue figure changes.
10. Close the inquiry as won or lost; verify the conversion metric responds appropriately.
11. Run test suite and authorization-negative tests before accepting the PR.

## 11. Definition of terms

- **Customer:** a person/company contact that may have multiple inquiries.
- **Inquiry:** one distinct potential renovation project or request.
- **Quote:** versioned estimate associated with one inquiry; may have multiple items.
- **Activity:** append-only audit-like business timeline event (not a substitute for a hardened security audit log).
- **Assigned owner:** employee responsible for the inquiry.
- **Closed inquiry:** inquiry in `won` or `lost` state.

## 12. Change control

`REQUIREMENTS.md` defines **what** the application must do. `ARCHITECTURE.md` defines **how** it will be built. `PLAN.md` defines **when and how to verify** each implementation increment. If requirements and code diverge, Codex must report the discrepancy rather than inventing a new requirement. Scope changes require a separate, reviewable commit or PR explanation.
