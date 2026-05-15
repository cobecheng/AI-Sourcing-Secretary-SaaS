# AI Sourcing Secretary SaaS

Chat-first AI sourcing secretary for specialty retailers, starting with Pokemon / TCG shops.

The product principle is simple:

> The chat is the product. The dashboard is supporting infrastructure.

This repository starts with a safe MVP foundation: canonical planning docs, mock-mode-first app scaffolding, Docker Compose, and CI placeholders. Real scraping, paid LLM calls, browser submissions, Gmail sending, and supplier outreach are intentionally not active in the first commit.

## Canonical Docs

Read these before changing architecture or opening feature work:

- [Project plan](docs/PROJECT_PLAN.md): full product and architecture source of truth.
- [Roadmap](docs/ROADMAP.md): issue-by-issue implementation map.
- [Decisions](docs/DECISIONS.md): architecture decision log.

## Local Quickstart

```bash
cp .env.example .env
docker compose up --build
```

Services are planned to run at:

- Frontend: <http://localhost:3000>
- Backend: <http://localhost:8000>
- Backend health: <http://localhost:8000/health>

## Repo Layout

```text
backend/     FastAPI foundation, mock mode, tests
frontend/    Next.js chat workspace foundation
docs/        Canonical plan, roadmap, architecture decisions
.github/     CI workflow
```

## Safety Defaults

- Mock mode is enabled by default.
- No autonomous purchasing.
- No real email sending without approval.
- No contact-form submission without approval.
- No CAPTCHA bypass, login-wall bypass, payment submission, or false business information.
- Every future outbound action must be approval-gated and audit-logged.

