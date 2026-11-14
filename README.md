# LeadFlow CRM

**自主制作デモ / 架空データ** — A Japanese, single-company renovation CRM built from scratch with Python 3.13 and Django 6.1.3. This is an independent portfolio demonstration, not a real client's system. Use synthetic information only; the application never sends real email.

Working features: public inquiry intake and conservative customer matching; manager/employee permissions; customer search/edit/archive; inquiry assignment and status history; notes; inspection appointments; decimal-based estimates and printable HTML; follow-up tasks; scoped database-driven dashboards; idempotent demo data.

Specifications: [requirements](doc/REQUIREMENTS.md), [architecture](doc/ARCHITECTURE.md), [plan](doc/PLAN.md). See [progress and verification](doc/PROGRESS.md) and the [3–5 minute walkthrough](doc/DEMO_WALKTHROUGH.md).

## Local setup (SQLite)

Requires Python **3.13**. No frontend build, Redis, SMTP server, or external credentials are needed. Use the existing checkout in an isolated cloud task; no additional worktree is necessary.

```sh
python3.13 -m venv .venv
. .venv/bin/activate
pip install --require-hashes -r requirements.lock
cp .env.example .env
```

Generate private local secrets into `.env` (do not commit this file):

```sh
python - <<'PY'
from pathlib import Path
import secrets
p = Path('.env')
s = p.read_text()
s = s.replace('DJANGO_SECRET_KEY=\n', 'DJANGO_SECRET_KEY=' + secrets.token_urlsafe(60) + '\n')
s = s.replace('POSTGRES_PASSWORD=\n', 'POSTGRES_PASSWORD=' + secrets.token_urlsafe(32) + '\n')
p.write_text(s)
p.chmod(0o600)
PY
```

The Python app reads environment variables; it does not automatically load `.env`. For the shell-compatible example above:

```sh
set -a
. ./.env
set +a
python manage.py migrate
python manage.py seed_demo
python manage.py changepassword demo-manager
python manage.py changepassword demo-employee-1
python manage.py changepassword demo-employee-2
python manage.py runserver 127.0.0.1:8000
```

Open `http://127.0.0.1:8000/`. The public demo form is `/inquiry/`; staff login is `/accounts/login/`. Every page displays the fictional-demo notice. All times are Asia/Tokyo.

`seed_demo` creates 60 fictional customers/inquiries, five employees (`demo-employee-1` … `demo-employee-5`), a manager (`demo-manager`), 54 tasks/appointments, and 18 multi-item quotations. It never supplies a shared password, resets a user's password, or rewrites existing sample records on repeat execution. Set each needed account's password with `changepassword` locally. `createsuperuser` can also bootstrap a manager; superusers explicitly have the domain Manager role. No real personal contact data is seeded.

Managers with `is_staff=True` can manage accounts at `/admin/`. Add users to the `Employee` or `Manager` group explicitly. The staff flag alone grants no CRM or admin role. Non-superuser Managers can create/edit/deactivate accounts, while account deletion is disabled to retain history. Domain records in admin are view-only; changes go through the CRM to preserve business events and quote totals.

## Docker Compose (PostgreSQL 17)

Prepare `.env` and its generated secrets as above. PostgreSQL has no host port; the web app binds to loopback only. These are **local demo** settings.

```sh
docker compose build
docker compose up -d
docker compose ps
docker compose exec web python manage.py seed_demo
docker compose exec web python manage.py changepassword demo-manager
docker compose exec web python manage.py changepassword demo-employee-1
```

Startup waits for PostgreSQL's health check and applies migrations idempotently before starting Gunicorn. CSS/JS are vendored with upstream licenses and collected during the build, so browsers need no CDN connection. Django serves static files only in local `DEBUG=1` mode; an approved public deployment must provide a real static-file server.

In a corporate/cloud TLS-intercepting environment, package installation during the build may need the environment's CA bundle. Do **not** disable TLS or hash verification. A session-only build tested in the Codex environment uses the existing Dockerfile and a temporary variant, without copying the CA into the image:

```sh
python - <<'PY'
from pathlib import Path
s = Path('Dockerfile').read_text().replace(
    'RUN pip install --require-hashes -r requirements.lock',
    'RUN --mount=type=secret,id=proxy_ca,required=true PIP_CERT=/run/secrets/proxy_ca pip install --require-hashes -r requirements.lock')
Path('/tmp/leadflow-cloud.Dockerfile').write_text(s)
PY
docker build -f /tmp/leadflow-cloud.Dockerfile \
  --secret id=proxy_ca,src=/etc/ssl/certs/ca-certificates.crt \
  -t leadflow-review-web .
docker compose -p leadflow-review up -d --no-build
```

The temporary image tag matches that Compose project. On machines without an intercepting proxy, use the standard build command.

## Verification

With the local virtual environment activated and local settings exported:

```sh
python manage.py check
python manage.py makemigrations --check --dry-run
pytest -q
```

Or, against real PostgreSQL in Compose:

```sh
docker compose exec -T web python manage.py check
docker compose exec -T web python manage.py makemigrations --check --dry-run
docker compose exec -T web pytest -q
```

pytest creates a separate test database and does not run tests against the seeded demo database. The committed GitHub Actions workflow runs these checks on PostgreSQL and builds the container; remote CI execution is separate from locally running the commands.

The optional browser suite requires the **specified** Playwright runner and Chromium. If these are not installed, install Playwright in a disposable tooling directory (`npm install --prefix /tmp/leadflow-browser playwright@1.62.1`, `NODE_PATH=/tmp/leadflow-browser/node_modules /tmp/leadflow-browser/node_modules/.bin/playwright install chromium`). No Node dependencies are required to run the app. Set private local passwords for `demo-manager`, `demo-employee-1` and `demo-employee-2` to the same temporary value for this automated check only:

```sh
# Set LF_BROWSER_PASSWORD securely in your local shell, without putting it in Git.
# NODE_PATH must point to your Playwright installation if not already resolvable.
# Use CHROMIUM_PATH=/usr/bin/chromium when using an installed system Chromium.
node tests/browser-smoke.cjs
```

`LF_BASE_URL` defaults to `http://127.0.0.1:8000`. The suite writes ignored screenshots under `test-results/` and adds a synthetic inquiry to the demo database. It exercises intake → manager assignment → employee note/inspection → two-item quote/print → overdue task/completion → won, verifies cross-owner 404, checks charts and 375px layouts, and fails on browser JS errors.

## Documented business rules

- Employee inquiries are owner-scoped; unassigned inquiries are Manager-only. Customers are visible if created by the employee or linked to an assigned inquiry. A shared customer's unrelated inquiries/history remain hidden. Customers can be edited by permitted employees; archiving is Manager-only and retains history.
- Task/appointment assignees must be active Employees and the inquiry's current owner. On inquiry reassignment, existing task/appointment assignments are retained; the Manager must review them. Old owners immediately lose inquiry access and related records are also hidden by the intersection of inquiry/task scope.
- A public inquiry normalizes the email for exact matching. One match is reused without changing identity data. Multiple matches create a new customer and flag the inquiry for review. Submitted identity information is preserved in its initial internal activity. Public responses never reveal match results.
- Intake applies CSRF, max request/field sizes, a honeypot and **10 POSTs per remote IP per 10 minutes per process**. This local-demo limiter uses process memory, ignores untrusted forwarding headers and is not appropriate as the sole abuse protection on the public internet.
- Every inquiry status correction is allowed and logged. Switching a quote to `sent` automatically moves the inquiry to `quotation_sent` and records distinct events, including if it corrects an earlier closed outcome. Reverting a quote does not roll back inquiry status; the user can explicitly correct the latter. This is stated on the quote form.
- Money uses `Decimal`: multiply quantity by whole-yen unit price; keep exact two-decimal line amounts and subtotal; round **tax only** to whole yen with `ROUND_HALF_UP`; total = subtotal + rounded tax. Example: `1.25 × 101 + 2 × 333 = 792.25`, tax `79`, total `871.25`. This follows FR-07's explicit rounding rule where the architecture's broader rounding wording is ambiguous. Single tax rate (default 10%); mixed reduced tax/invoices are out of scope. Browser totals are never accepted.
- Dashboard filters select inquiries **created** within inclusive start/end dates in Tokyo. Task and quote metrics use that same inquiry cohort; active-customer count remains an all-time snapshot. Won/lost reflect current statuses. Conversion is `won / (won + lost) × 100`, N/A when no closed outcomes. Submitted quotes count only current `sent`, not subsequent accepted/rejected statuses. Trend groups persisted creation timestamps into Tokyo months.
- Business activities are append-only through app/model/admin interfaces. They are a traceable business timeline, not a tamper-proof compliance audit system.

## Reset, configuration and limits

For a disposable SQLite demo, stop the server, remove **only your local** `db.sqlite3`, then migrate/seed again. For a disposable Compose demo, `docker compose down` preserves data; `docker compose down --volumes` **permanently removes that project's database**. Never use reset commands against real data. Keep `.env` for a restart; changing the database password in `.env` does not rotate a previously initialized PostgreSQL volume.

`DJANGO_DEBUG` defaults to `0`. Without a secret key, non-debug startup fails closed. Non-debug mode enables HTTPS redirects, HSTS and secure session/CSRF cookies. Configure `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, HTTPS termination, static serving, rate limiting, backups and operations separately before any public deployment. The framework's full `check --deploy` intentionally reports `mail.E001` because this demo uses a disabled/dummy mailer; it is not silenced or replaced with SMTP. `check --deploy --tag security` validates security settings independently. This app is a portfolio demo, not production-client ready.

P1 import/export, advanced reports and native PDF are deferred. HTML quotations can be printed to PDF by the browser. There are no email/SMS/payment integrations. No public deployment is included or authorized.

## Portfolio description

> **自主制作デモ / 架空データ**：小規模リフォーム会社を想定した顧客・案件管理システムです。Web受付から担当者への割当、現地調査、見積作成、フォローアップ、成約状況の可視化までを実装しています。実在する企業の受託・導入実績ではありません。
