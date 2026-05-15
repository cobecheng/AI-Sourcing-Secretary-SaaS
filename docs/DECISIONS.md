# Architecture Decisions

Record decisions here when implementation choices could affect future issues.

## ADR-0001: Preserve The Original Plan As Canonical

Status: Accepted

Decision: `docs/PROJECT_PLAN.md` is the source of truth for product direction, architecture constraints, and MVP safety rules.

Reason: The product depends on subtle behavior: chat-first UX, human approval, budget-aware model routing, and safe outbound automation. Keeping those details in one canonical file reduces drift across future issues.

## ADR-0002: Mock Mode Is The Default

Status: Accepted

Decision: The first foundation runs in mock mode and does not execute paid API calls, scraping, real browser submissions, or real emails.

Reason: The MVP should be locally useful and safe before credentials, provider routing, Gmail OAuth, browser automation, or supplier outreach are enabled.

## ADR-0003: Business Logic Calls The Internal LLM Router Only

Status: Accepted

Decision: Business logic must call the internal LLM router instead of provider SDKs directly.

Reason: The app needs task-based model selection, cost tracking, schema validation, fallback, confidence escalation, provider health checks, and future A/B evaluation.

## ADR-0004: Approvals Are First-class Records

Status: Accepted

Decision: Use explicit approval request records for user decisions around email sending, contact-form submission, account creation, budget continuation, and other risky actions.

Reason: Approval state is a workflow object, not just a boolean on an outreach row. It needs payload preview, edits, decision metadata, auditability, and expiration.

## ADR-0005: Use Current Stable Next.js For The Frontend Shell

Status: Accepted

Decision: Use the current stable Next.js and React versions for the frontend scaffold, even though the original product plan named Next.js 15.

Reason: The first frontend implementation exposed a security advisory in the Next.js 15 dependency line. Keeping the scaffold on the current stable Next.js/React release gives us clean install/build/audit checks while preserving the App Router architecture expected by the plan.
