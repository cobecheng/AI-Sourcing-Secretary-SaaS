# Observability Review

## Current Coverage

- `agent_runs` records LLM task type, provider, model, cost, latency, confidence, schema version, and fallback usage.
- `llm_budgets` tracks daily, monthly, and project budget consumption.
- `approval_requests` stores exact payloads, decision state, decision user, and timestamps.
- `audit_logs` records approval decisions, mock email execution, and mock form submission.
- `/admin/readiness` reports provider readiness without making paid provider calls.

## Risky Workflow Checklist

- Project creation stores the original user request and missing business info prompts.
- Search stores cached result metadata only. It does not scrape, submit forms, or send outreach.
- Scraping reads public pages only and stores supplier evidence. It does not submit forms.
- Supplier scoring stores confidence metadata and evidence URLs.
- Outreach drafting creates approval payloads only. It does not send.
- Outbound execution requires an approved approval request and writes audit records.

## Remaining Production Work

- Add structured request logging with request IDs.
- Add metrics counters for provider degraded-safe paths and approval decisions.
- Add trace propagation around LangGraph workflow nodes once durable workflows are introduced.
- Add alerting for repeated provider failures, budget exhaustion, and blocked risky actions.
