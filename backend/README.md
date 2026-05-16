# Backend

FastAPI foundation for the AI Sourcing Secretary SaaS.

Current state:

- mock mode first
- health endpoint
- router placeholders for the planned project, chat, milestone, research, supplier, form, approval, outreach, inbox, report, and LLM router APIs
- tests that do not require external API keys

Real LLM, search, scraping, browser automation, Gmail, and outbound submission integrations must be added behind approval and feature gates.

## Local Commands

```bash
python -m pip install -e ".[dev]"
pytest
uvicorn app.main:app --reload
```

## Migrations

```bash
alembic upgrade head
alembic downgrade -1
```

The default migration fallback is `sqlite:///./dev.db` for local smoke testing. Production and Docker Compose should provide `DATABASE_URL` for Postgres.

## Safety

Placeholder endpoints return `status: not_implemented`. They are route skeletons only. Future issues must keep provider calls behind mock-mode checks, approval records, idempotency keys, and audit logging where relevant.
