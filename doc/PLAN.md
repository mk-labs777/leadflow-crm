# LeadFlow CRM — Codex Implementation Plan

**Document ID:** LF-PLAN-001  
**Version:** 1.0  
**Date:** 2026-11-14  
**Repository:** https://github.com/mk-labs777/leadflow-crm  
**Specification:** [REQUIREMENTS.md](REQUIREMENTS.md)  
**Architecture:** [ARCHITECTURE.md](ARCHITECTURE.md)

## 1. Operating principles

Codex owns implementation, testing and documentation **from an essentially empty GitHub repository**. The user acts as product owner and reviews pull requests. Do not use the earlier ChatGPT ZIP starter project.

**Do not stop at planning:** create code, migrations, views, templates and tests. Work incrementally, retaining completed work in branches/PRs. Do not merge to `main`, purchase cloud services, send real communications or deploy publicly without the user's approval.

Use the following phases as *acceptance gates*, not as a rigid hour-by-hour forecast. If Codex has a finite execution budget, finish the current phase and report its exact status instead of claiming the whole application is complete.

## 2. Work breakdown and acceptance gates

### Phase 0 — Repository foundation and engineering guardrails

**Goals**

- Inspect the existing repository, identify default branch, read the three docs and any `AGENTS.md`.
- Set up Python 3.13 + Django 6.1 project, dependency file/lock, `.gitignore`, `.env.example`, baseline `README.md` and `AGENTS.md` (if absent).
- Create Django settings split or disciplined env-based settings; Dockerfile, Compose skeleton, PostgreSQL connection and local SQLite fallback for tests.
- Establish GitHub Actions CI, pytest configuration, and a minimum working home/login route.
- Create initial PR; do not merge it without approval.

**Gate P0:** Project installs; `manage.py check` passes; test runner starts; `docker compose build` works; no secrets are committed. CI runs or its inability to run is documented.

### Phase 1 — Domain model, roles and security

**Goals**

- Create Customer, Inquiry, Activity, Appointment, Task, Quote and QuoteItem models with migrations.
- Implement Django authentication, manager/employee domain roles and reusable queryset/access helpers.
- Establish source/status/category choices and coherent time-zone handling (`Asia/Tokyo` display).
- Configure admin for managers only; ensure ordinary employees cannot use Django admin.
- Add migration and role-permission tests.

**Gate P1:** Migrations apply to clean PostgreSQL/SQLite; unauthenticated internal access redirects; employee cannot read/write another employee's inquiry or related customer/quote/task; manager can perform company-wide administration.

### Phase 2 — Customer management and public inquiry intake

**Goals**

- Build Japanese customer list/detail/create/edit/search screens with proper scope checks.
- Build public renovation inquiry form with server validation, CSRF, practical anti-spam measures and thank-you page.
- Implement atomic customer lookup + inquiry + initial Activity creation with conservative duplicate handling.
- Add manager's unassigned intake queue and seed minimal fictional example records.
- Add tests for valid, invalid, repeated and ambiguous submissions.

**Gate P2 — First usable vertical slice:** A fictional customer submits a web form, the inquiry is saved in a database, a manager sees it in the unassigned queue, and no unauthenticated user can access CRM data.

### Phase 3 — Inquiry lifecycle and interaction history

**Goals**

- List/search/filter inquiries by status, customer and owner.
- Implement manager assignment and employee updates to assigned inquiries.
- Record automatic Activity entries for assignment and status changes, plus manual call/visit/email notes.
- Create clear, Japanese inquiry detail pages and status badges.
- Add negative-permission tests against direct URL requests.

**Gate P3:** Manager assigns an inquiry; its owner sees it, a different employee does not; status and notes persist and activity history accurately reflects the changes.

### Phase 4 — Appointments, quotations and follow-up tasks

**Goals**

- Create/edit/cancel inspection appointments and show upcoming schedule.
- Create quotes with multiple QuoteItems, Decimal arithmetic, explicit tax rate, and printable HTML estimate.
- Implement follow-up tasks, due dates, completion/reopening and overdue detection in Tokyo time.
- Link all three features to the inquiry detail and activity timeline.
- Add quote calculation and permissions tests.

**Gate P4:** Quote line item totals and tax match test fixtures, quote print view works, tasks correctly move into/out of overdue counts, and unrelated employees cannot access these records.

### Phase 5 — Dashboard, professional Japanese UI, synthetic portfolio data

**Goals**

- Implement manager and employee dashboards with correct scope, monthly inquiry trends and closed-inquiry conversion rate.
- Apply consistent responsive Bootstrap styling; improve forms, search, tables, empty/error states and keyboard navigation.
- Create reproducible, idempotent synthetic data generator for 50–100 customers and approximately five staff identities with safe setup instructions.
- Add `docs/DEMO_WALKTHROUGH.md` demonstrating intake → assignment → inspection → quote → follow-up → outcome → metrics.
- Include visible **自主制作デモ / 架空データ** notices.

**Gate P5:** Dashboard values equal database queries, a full walkthrough is usable on desktop and narrow mobile layouts, and running the seed command twice does not create duplicate intended fixtures.

### Phase 6 — Verification, packaging and handoff

**Goals**

- Run full automated test suite, migration check, Django system checks and Docker Compose clean-start smoke test.
- Run Playwright (if available) against one representative end-to-end happy path plus authorization-denial scenarios.
- Perform targeted security review: CSRF, cross-user queries, secrets, debug settings, CSV injection if export is included, public form abuse, quote tampering.
- Write final README setup and reset commands, a limitations section, and a concise Coconala portfolio description clearly labelled as a fictional demo.
- Produce a final summary: implemented P0 requirements, tests executed, commands/results, screenshots if available, outstanding risks, PR links.

**Gate P6 — MVP acceptance:** Every P0 requirement in `REQUIREMENTS.md` is implemented and tested or is clearly listed as incomplete; `pytest` passes; clean Docker startup works; demonstration walkthrough succeeds; no public deployment occurs without approval.

## 3. Traceability matrix

| Requirement | Primary phase | Minimum verification |
| --- | --- | --- |
| FR-01 Authentication/permissions | 1 | Anonymous redirect and cross-owner denial tests |
| FR-02 Customers | 2 | CRUD/search persistence and scoped access tests |
| FR-03 Public intake | 2 | Atomic create, match, invalid submission tests |
| FR-04 Inquiry management | 3 | Assignment/status/history tests |
| FR-05 Activities | 3 | Auto/manual event tests |
| FR-06 Appointments | 4 | Create/edit/cancel and scope tests |
| FR-07 Quotations | 4 | Multi-item yen/tax/print tests |
| FR-08 Tasks | 4 | Deadline/completion/Tokyo date tests |
| FR-09 Dashboard | 5 | Cohort/denominator/scope/empty-state tests |
| FR-10 Demo data and walkthrough | 5–6 | Idempotent seed and manual walkthrough |

## 4. Pull-request discipline

1. Create a focused branch such as `codex/phase-2-intake`.
2. Identify the relevant requirement IDs and the planned tests in the PR body.
3. Implement the phase without slipping in out-of-scope functionality.
4. Run `python manage.py check`, `python manage.py makemigrations --check --dry-run`, `pytest -q`, plus applicable UI or Docker checks.
5. Include a change summary, test command outputs, known limitations and screenshots for significant UI changes.
6. Leave the PR open for the user to review; **do not merge automatically**.

Do not work on multiple conflicting feature branches at once without an integration strategy. If Codex cannot create a PR, provide the branch/commit URL and explain what permission is missing.

## 5. Milestone priorities and contingency rules

**Priority order:**

1. Working public inquiry → database → manager queue (must not be a mockup).
2. Correct permissions and activity logging.
3. Employee workflow and follow-up tasks.
4. Quotations with correct arithmetic.
5. Real dashboard metrics and polished Japanese presentation.
6. Documentation and reproducible deployment.

If an execution runs short, ship the current verified vertical slice and document missing features; do not produce an impressive UI backed by nonexistent workflows. If a dependency is unavailable, use a documented replacement only when it preserves the architectural goals and does not materially change scope.

## 6. Quick commands to establish and verify

The precise dependency commands depend on the generated `pyproject.toml`; update README and CI consistently. At minimum, the following must be supported:

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate
pytest -q

docker compose build
docker compose up -d
docker compose ps
```

When using Docker Compose, document how to run migrations, create a manager and seed the demonstration database inside the web container. Do not hardcode database passwords in YAML.

## 7. Definition of “complete” versus “ready for a real client”

**Portfolio complete** means all P0 features genuinely work with fictitious data in a demonstrable environment, with adequate tests and honest documentation. **Production-client ready** would require separate requirements discovery, operational monitoring, a backup/restore strategy, incident response, privacy compliance, hardened internet-facing rate limiting, user onboarding, hosting agreements and support processes. Do not conflate the two.

## 8. Initial instruction to paste into Codex Cloud

> Work in the `mk-labs777/leadflow-crm` repository. Build LeadFlow CRM entirely from scratch; do not import the previous ChatGPT starter archive. Read `docs/REQUIREMENTS.md`, `docs/ARCHITECTURE.md` and `docs/PLAN.md` and follow any repository `AGENTS.md`. Begin with Phase 0 and continue through the phases as far as verifiable within this task. Implement code, migrations and tests—not merely a plan. Run checks at every gate. Develop on a branch and open a PR; do not merge or deploy publicly. If blocked or unfinished, explain the exact status and the next task.

## 9. Progress log template (maintained by Codex)

At the end of each implementation task or PR, append or update a concise status in this plan or a linked `docs/PROGRESS.md`:

```text
Date:
Branch / PR:
Phase and requirement IDs:
Implemented:
Tests executed and results:
Manual checks:
Outstanding issues:
Next recommended task:
```

Keep progress grounded in executed commands and committed changes. Do not invent percentages, test results or completion claims.

## Implementation status

See [PROGRESS.md](PROGRESS.md) for implemented phases, requirement traceability, executed checks and remaining limitations.
