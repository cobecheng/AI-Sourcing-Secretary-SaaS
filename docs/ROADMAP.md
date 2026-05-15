# Roadmap And Issue Breakdown

Use this as the working issue map. Each issue should link back to relevant sections of [PROJECT_PLAN.md](PROJECT_PLAN.md).

## Milestone 0: Safe Foundation

1. Repo foundation and documentation
   - Add README, `.env.example`, Docker Compose, CI placeholders, and canonical docs.
   - Acceptance: contributors can find the product source of truth before changing architecture.
   - Plan references: sections 1-5, 22-27, Codex Additions.

2. Backend app shell
   - Add FastAPI app, health endpoint, settings, mock mode, tests, and Dockerfile.
   - Acceptance: `/health` returns app name, environment, and mock mode status.
   - Plan references: sections 4, 17, 18, 22.

3. Frontend app shell
   - Add Next.js chat workspace shell with project sidebar, chat panel, and supplier side panel.
   - Acceptance: the first screen is the product workspace, not a marketing page.
   - Plan references: sections 2, 3, 19, 20.

## Milestone 1: Data And Mock Workflow

4. Database models and migrations
   - Implement the core schema, including `approval_requests` and workflow/job tracking.
   - Acceptance: migrations apply cleanly and include user/project scoping.
   - Plan references: section 17, Codex Additions A-C.

5. Project creation through chat
   - Convert a user chat request into a project, conversation, messages, and milestones in mock mode.
   - Acceptance: a user can create a mock sourcing project from chat.
   - Plan references: sections 1, 3, 16, 18.

6. Mock sourcing workflow
   - Produce mock search, supplier discovery, verification, missing-info prompts, and supplier cards.
   - Acceptance: local development works without any API keys.
   - Plan references: sections 16, 21, 22.

## Milestone 2: LLM Router And Budget Controls

7. Internal LLM router interface
   - Add task-type routing, model tiers, schema validation, confidence handling, mock provider, and logging hooks.
   - Acceptance: business logic calls only the internal router.
   - Plan references: sections 5-11.

8. Budget and usage logging
   - Track cost, tokens, latency, confidence, fallback, and budget status per task/user/project.
   - Acceptance: reaching 80% budget emits a chat warning in mock mode.
   - Plan references: sections 6, 12, 13.

9. Model usage debug panel
   - Show model/provider/task/cost/latency/confidence/fallback in development/admin mode only.
   - Acceptance: hidden in normal mode, visible in development.
   - Plan references: section 19.

## Milestone 3: Supplier Research

10. Real search integration
    - Integrate Exa behind feature flags and cache search results.
    - Acceptance: mock mode remains default; real mode requires API keys.
    - Plan references: sections 4, 12, 16.

11. Scraping integration
    - Integrate Firecrawl or Crawl4AI behind feature flags and cache scraped text.
    - Acceptance: source URLs and evidence snippets are stored.
    - Plan references: sections 12, 14, 17.

12. Supplier extraction, deduplication, and scoring
    - Use deterministic parsing first, then model router when needed.
    - Acceptance: duplicated domains are merged and uncertain suppliers become manual review.
    - Plan references: sections 8-12, 21.

## Milestone 4: Approvals And Outreach

13. Approval request system
    - Implement approval cards and backend approval lifecycle.
    - Acceptance: outbound actions cannot execute without approved `approval_requests`.
    - Plan references: sections 14, 18, 20, Codex Addition A.

14. Email draft workflow
    - Draft supplier emails, check for hallucinated business details, and wait for user approval.
    - Acceptance: no email is sent in this issue.
    - Plan references: sections 9, 10, 14, 20.

15. Contact form inspection
    - Use Playwright to inspect public contact forms and map fields.
    - Acceptance: CAPTCHA/login/document/payment cases pause for user review.
    - Plan references: sections 14, 15, 20.

16. Email sending and contact-form submission
    - Add Gmail sending and Playwright submission only after approval.
    - Acceptance: every outbound action is idempotent and audit-logged.
    - Plan references: sections 14, 15, 18, Codex Additions B and E.

## Milestone 5: Replies And Reporting

17. Inbox sync and reply parsing
    - Sync Gmail threads, parse supplier replies, and extract terms.
    - Acceptance: supplier terms are linked to source messages.
    - Plan references: sections 1, 17, 18.

18. Follow-up drafting
    - Draft follow-ups when suppliers ask for more information.
    - Acceptance: follow-ups require user approval before sending.
    - Plan references: sections 14, 16, 18.

19. Supplier report and CSV export
    - Generate shortlist/report and CSV export.
    - Acceptance: report cites evidence URLs and extracted terms.
    - Plan references: sections 1, 18, 25, 27.

20. Admin and production hardening
    - Add observability, retries, provider health checks, CI expansion, and security review.
    - Acceptance: provider failures degrade safely and do not trigger autonomous outbound action.
    - Plan references: sections 6, 11, 13, Codex Additions C-E.

