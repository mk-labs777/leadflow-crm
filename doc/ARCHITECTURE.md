# LeadFlow CRM — Technical Architecture

**Document ID:** LF-ARC-001  
**Version:** 1.0  
**Date:** 2026-11-14  
**Repository:** https://github.com/mk-labs777/leadflow-crm  
**Companion documents:** [REQUIREMENTS.md](REQUIREMENTS.md), [PLAN.md](PLAN.md)

## 1. Architectural decision

Build **one modular Django monolith** with server-rendered templates. This is an internal workflow application, not a JavaScript-heavy SaaS platform. Prefer mature framework capabilities over additional infrastructure.

```
                        INTERNET / LOCAL DEMO
                      +-----------------------+
                      | Public inquiry form   |
                      | Staff browser / login |
                      +-----------+-----------+
                                  |
                           HTTP(S) requests
                                  |
                 +----------------v----------------+
                 | Django application (Python)     |
                 | Authentication and permissions  |
                 | Views + forms + services        |
                 | Django Templates + HTMX         |
                 +----------------+----------------+
                                  |
                          Django ORM
                                  |
                 +----------------v----------------+
                 | PostgreSQL (Docker deployment)  |
                 | SQLite (fast local tests only)  |
                 +---------------------------------+
```

No separate frontend service, microservices, job queues, Redis, Kubernetes, or external email connectors are required for the MVP.

## 2. Technology choices

| Concern | Decision | Reason |
| --- | --- | --- |
| Language | Python 3.13 | Stable, familiar tooling and officially supported by Django 6.1 |
| Framework | Django 6.1, pinned patch version via lock/constraints | ORM, auth, forms, migrations and admin support |
| Page rendering | Django Templates | Simple, secure server-rendered workflow pages |
| CSS | Bootstrap 5.3 plus small custom stylesheet | Fast, responsive, consistent visual system |
| Progressive interaction | HTMX 2 where useful | Table filters, inline updates without full SPA |
| Charts | Chart.js | Simple monthly activity visualizations |
| Database | PostgreSQL 17 for Docker; SQLite for local tests | Real relational constraints and portable tests |
| DB layer | Django ORM and migrations | Avoid competing database abstractions |
| Tests | pytest + pytest-django, targeted browser tests via Playwright | Repeatable behavior and authorization checks |
| Packaging | Docker + Docker Compose | Reproducible demo installation |
| App server | Gunicorn (WSGI) | Straightforward Linux deployment |
| CI | GitHub Actions | Checks, tests, migration consistency |

Django 6.1 supports Python 3.13 (official documentation: https://docs.djangoproject.com/en/6.1/releases/6.1/). Verify pinned dependency compatibility when implementing; do not rely on floating latest versions in CI.

## 3. Suggested repository layout

```text
leadflow-crm/
├── AGENTS.md                # Codex persistent engineering instructions
├── README.md                # Setup, test and demonstration guide
├── .gitignore
├── .env.example
├── pyproject.toml           # Python tool and dependency configuration
├── manage.py
├── config/
│   ├── settings/            # base, local, production if warranted
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── apps/
│   ├── accounts/            # Django users, domain roles, access helpers
│   ├── customers/           # Customer records and queries
│   ├── inquiries/           # Public intake, inquiry workflow, activities
│   ├── quotations/          # Quotes, items, calculations, print view
│   ├── tasks/               # Follow-ups and inspections
│   └── dashboard/           # Aggregations and reporting
├── templates/               # Shared layout and page templates
├── static/                  # CSS, icons, small JS
├── tests/                   # Cross-module integration and browser tests
├── docs/
│   ├── REQUIREMENTS.md
│   ├── ARCHITECTURE.md
│   ├── PLAN.md
│   └── DEMO_WALKTHROUGH.md  # Created during development
├── Dockerfile
├── compose.yaml
└── .github/workflows/ci.yml
```

This is a **suggested** layout, not a reason to over-engineer. Django apps may be combined if responsibilities remain clear. Avoid service/repository abstractions that only forward ORM calls. Introduce service functions for genuinely transactional multi-model operations (e.g., inquiry intake and quotation totals).

## 4. Core domain model

### Entity relationships

```
User 1 ---- * Inquiry (owner)
User 1 ---- * Customer (created_by)
Customer 1 ---- * Inquiry
Inquiry 1 ---- * Activity
Inquiry 1 ---- * Appointment
Inquiry 1 ---- * Task
Inquiry 1 ---- * Quote
Quote 1 ---- * QuoteItem
```

Use Django's `AUTH_USER_MODEL` and proper ForeignKeys with `related_name`, indices on common filters, and explicit deletion policy. Protect financially or historically relevant parent records; prefer archiving over destructive cascade from customer deletion.

### Recommended model fields

| Model | Required or important fields |
| --- | --- |
| `Customer` | `id`, `name`, `email`, `normalized_email`, `phone`, `address`, `notes`, `created_by`, `created_at`, `updated_at`, `is_active` |
| `Inquiry` | `id`, `customer`, `subject`, `description`, `service_category`, `source`, `status`, `owner` (nullable), `created_at`, `updated_at` |
| `Activity` | `id`, `inquiry`, `actor` (nullable for system), `event_type`, `note`, `created_at` |
| `Appointment` | `id`, `inquiry`, `assigned_to`, `starts_at`, `ends_at` (optional), `location`, `notes`, `status` |
| `Task` | `id`, `inquiry`, `assigned_to`, `title`, `note`, `due_date`, `completed_at`, `created_at` |
| `Quote` | `id`, `inquiry`, `quote_number`, `title`, `issued_on`, `valid_until`, `status`, `tax_rate`, `subtotal`, `tax_amount`, `total`, `created_at` |
| `QuoteItem` | `id`, `quote`, `description`, `quantity`, `unit_price`, `position`, `line_amount` |

Business IDs may be integers initially, but avoid relying on sequential IDs as proof of access. Use `on_delete=PROTECT` on customers/inquiries with history where appropriate. For Quote/QuoteItem, cascade deletion within a *draft* may be allowed only via an authorized operation with meaningful logging.

### Monetary calculation

- `DecimalField` for quantity (e.g. 10 digits/2 decimals) and unit prices (e.g. 12 digits/0 decimals); never use `float` for yen.
- `line_amount = quantity * unit_price`; subtotal = sum of line amounts.
- One quote-level tax rate; default `Decimal('0.10')` (10%); document the limitation.
- Round subtotal and tax to yen at the documented points using `ROUND_HALF_UP`. Store totals as calculated snapshots, with tests preventing stale totals after edits.
- Perform authoritative calculations in a single service, within a transaction when saving line items. Do not trust browser-supplied totals.

### Customer matching

A public form is untrusted input. Normalize email by trimming and case-folding for matching, but do not overwrite an existing customer's contact details from a public submission. If a normalized email corresponds to multiple customers, create a flagged record for manual review rather than silently attaching it to an arbitrary customer. Do not disclose match results to public submitters. Phone numbers can be supplementary duplicate suggestions, not blind auto-merge keys.

## 5. Authorization and information exposure

A single manager account can see all company inquiries; employees see **only their assigned inquiries**, including their related notes, quotes, tasks and appointments. Employee customer-list access is restricted to customers attached to assigned inquiries or created by that employee. Unassigned inquiries form a manager-only queue.

**Access matrix**

| Action | Public | Employee | Manager |
| --- | :---: | :---: | :---: |
| Submit inquiry | Yes | Yes | Yes |
| View internal dashboard | No | Scoped | All |
| View/edit own inquiry | No | Yes | Yes |
| View/edit another employee's inquiry | No | No | Yes |
| Assign/reassign staff | No | No | Yes |
| View permitted customers | No | Yes | Yes |
| Create quotation/task for permitted inquiry | No | Yes | Yes |
| Export all CRM data | No | No | Yes |
| Manage internal users | No | No | Yes |

Implement explicit reusable queryset scopes and object-level permission checks in *every* read and write route. Templates hiding buttons are not security controls. Distinguish `is_staff` (Django admin capability) from the domain role of Manager; use Django Groups or explicit domain permissions. Direct URL access must not leak record details.

## 6. Request and transaction boundaries

### Public intake sequence

1. POST to a Django view with CSRF protection and validated `Form`.
2. Apply anti-abuse checks (rate limiting, honeypot, maximum payload size). For local demo, simple measures are acceptable; public internet exposure requires a shared or reverse-proxy rate limiter.
3. Within `transaction.atomic()`: find an unambiguous customer; otherwise create one or flag ambiguous matching; create Inquiry with `new` status and `web` source; append Activity.
4. Redirect (POST/Redirect/GET) to generic thank-you page.
5. Never expose the customer identifier, existence of an account, or history to the submitter.

### Staff workflow

- All edits are authenticated; POST/PATCH semantics for writes, with Django CSRF and model validation.
- Record status and ownership changes as Activities with previous/new values, actor and timestamp.
- Validate that assignees are active employees. Only managers can assign/reassign.
- Appointments, task completion and quote status changes also create Activities.
- Use `select_related` / `prefetch_related` and pagination for lists that might otherwise generate N+1 queries.

## 7. Dashboard metric definitions

- **Total customers:** manager = all active customers; employee = only in-scope customers.
- **New inquiries:** status `new` among visible inquiries.
- **Unassigned:** only managers; owner is null.
- **Active inquiries:** all visible inquiries excluding `won` and `lost`.
- **Overdue tasks:** incomplete tasks with `due_date < timezone.localdate()` in Asia/Tokyo.
- **Quotations sent:** quotes whose status is `sent` (or equivalent distinct status; make clear whether later accepted quotes count in historical sent totals).
- **Won:** inquiries with status `won`.
- **Conversion rate:** `won / (won + lost)` within the date-filtered cohort; display N/A with zero closed inquiries. Document the cohort definition (e.g., inquiries created in selected period) consistently.
- **Monthly chart:** inquiries grouped by creation month in Asia/Tokyo.

Make metrics computed via ORM queries or services, not UI literals. Tests must verify date boundaries and manager versus employee visibility.

## 8. Interface and interaction strategy

- Entire user-facing interface in Japanese; Bootstrap base with a coherent custom palette, readable typography and clear responsive layout.
- Pages: dashboard, customers, inquiries, inquiry details, quotations and print view, tasks/appointments, manager account administration, public form.
- Start with full-page Django form submissions. Introduce HTMX sparingly for inline status changes or filters; preserve graceful full-page behavior where practical.
- Chart.js loaded only on reporting screens; graceful no-data fallback.
- Provide meaningful feedback and error pages; escape user-originated notes by default; no arbitrary `|safe` on data fields.
- Page headings and form labels must be accessible; include proper button types, validation summaries and keyboard focus visibility.

## 9. Configuration, deployment and secrets

### Development

- Provide a local-only workflow with `.venv` and SQLite if helpful, plus Docker Compose with PostgreSQL.
- Commit `.env.example` containing placeholder variables; never commit `.env`, actual database files, seed passwords or API keys.
- Document migrations, `createsuperuser`, seed command, test commands and reset procedure.
- Use reproducible dependency versions and a supported Python base image.

### Docker Compose

- `web`: Django/Gunicorn container.
- `db`: PostgreSQL 17 with persistent volume and health check.
- Expose web on **127.0.0.1** by default for local review. Do not expose PostgreSQL on the host unless specifically required.
- Avoid running with hardcoded demo passwords or permissive production settings.
- Use migrations as an explicit setup command or a well-documented idempotent startup step.

### Public deployment (separate approval gate)

Do **not** deploy externally without explicit approval. If later approved: HTTPS proxy, correct `ALLOWED_HOSTS`/CSRF trusted origins, `DEBUG=False`, secure cookies, secrets management, static assets, logging, backups and restore tests, rate limiting, and a review of Django's official deployment checklist (`python manage.py check --deploy`). Treat local demo settings as unsuitable for public processing of real people’s data.

## 10. Testing architecture

Use pytest and pytest-django for unit and integration tests, including database-backed tests. Add browser tests for the most valuable workflow if the runner supports Playwright; when browser automation is unavailable, document the limitation and perform manual smoke checks without claiming automation ran.

**High-priority test categories:**

1. Public form: valid, invalid, repeated email, ambiguous email, spam/rate limiting.
2. Permissions: anonymous/employee/manager; cross-employee read and write denial; export denial.
3. History: automatic events on assignment/status/task/quote updates.
4. Quote arithmetic: decimal quantities, yen rounding, zero/negative validation, edits recomputing totals.
5. Tasks: overdue Tokyo date boundary and completion.
6. Dashboards: correct scoped queries, closed-outcome conversion formula, empty dataset.
7. Seed: repeat execution remains idempotent.
8. Docker: clean build, migration and healthy startup.

### CI commands (adjust to chosen tooling)

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
pytest -q
```

CI should run on pushes and pull requests, and fail on missing migrations or failed tests. Add lint/format checks if a formatter is configured (e.g. Ruff), without letting tools silently rewrite business behavior.

## 11. Engineering rules for Codex

- Read `docs/REQUIREMENTS.md` before changing behavior; read this document before architecture changes; follow `docs/PLAN.md` for task order.
- Create small, reviewable branches and PRs. Do not merge or deploy without user approval.
- Implement critical workflows end-to-end before adding optional polish.
- Maintain tests and migrations with every schema/behavior change.
- Prefer straightforward Django patterns over speculative abstractions.
- State exactly which tests ran and whether they passed; never infer that code works from visual appearance alone.
- When a decision is not in scope or conflicts with the documents, choose the smallest safe and reversible design, record the assumption in the PR, and request approval for material changes.

## 12. Deferred architectural choices

No Celery, message queue, external API gateway, email provider, Kubernetes cluster, or AI inference service is part of the MVP. A real client deployment may warrant these later, but they must be justified by operational requirements, not introduced for portfolio impressiveness.
