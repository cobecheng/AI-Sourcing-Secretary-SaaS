# Backend

FastAPI foundation for the AI Sourcing Secretary SaaS.

Current state:

- mock mode first
- health endpoint
- router placeholders for the planned project, chat, milestone, research, supplier, form, approval, outreach, inbox, report, and LLM router APIs
- project creation through chat in mock mode
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

## Mock Project Creation

```bash
curl -X POST http://localhost:8000/projects/from-chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Find Pokemon TCG distributors in the UK or EU. I want booster boxes and ETBs."}'
```

The endpoint stores the user message, assistant milestone update, missing-info prompt, project memory, and the initial request-understood milestone. It does not invent business details or call external providers.

## Safety

Placeholder endpoints return `status: not_implemented`. They are route skeletons only. Future issues must keep provider calls behind mock-mode checks, approval records, idempotency keys, and audit logging where relevant.
