# Canonical Project Plan: Chat-first AI Sourcing Secretary

This document is the project source of truth. Preserve the original product direction here, and record intentional changes as clearly labeled additions or architecture decisions.

## Original Codex Execution Plan

You are building an MVP for a chat-first AI Sourcing Secretary SaaS for specialty retailers, starting with Pokemon / TCG shops.

The product should feel like an AI secretary, not just a dashboard tool.

The user interacts with the system through a chatbot-style interface. The AI receives sourcing requests, researches suppliers, reports progress after each milestone, asks the user for missing business information, drafts outreach, and submits emails/contact forms only after user approval.

The MVP must keep things simple, but the architecture must be flexible enough to support cost-efficient model routing, browser automation, email outreach, contact-form submission, reply parsing, and future voice calling.

Do not build voice calls in MVP.
Do not build autonomous purchasing.
Do not build payment handling.
Do not build CRM integrations yet.

---

## 1. MVP Goal

A user can type:

> Find Pokemon TCG distributors in the UK or EU. I want sealed products like booster boxes and ETBs. Prefer suppliers that accept small retailers.

The AI should:

1. Understand and structure the sourcing request.
2. Report that the request is understood.
3. Search the web for potential suppliers.
4. Report how many potential suppliers were found.
5. Visit/scrape supplier websites.
6. Verify relevance.
7. Report how many suppliers look relevant.
8. Find contact methods.
9. If email exists, draft an email.
10. If only a contact form exists, inspect the form using browser automation.
11. Ask the user for missing business information if the supplier requires it.
12. Ask user approval before sending emails or submitting forms.
13. Track sent outreach.
14. Monitor replies.
15. Extract supplier terms such as MOQ, pricing availability, payment terms, shipping region, lead time, and account requirements.
16. Generate a supplier shortlist/report.

---

## 2. Main UX

The main UI should be a chat workspace.

Left sidebar:

- Projects
- New project button
- Project status
- Supplier count
- Pending approvals
- Unread replies

Main panel:

- Chat conversation
- User messages
- Assistant messages
- Milestone updates
- Approval cards
- Missing information prompts
- Supplier cards
- Contact form previews

Right panel:

- Supplier list
- Current task status
- Milestones
- Pending approvals
- Extracted supplier terms

The most important product principle:

> The chat is the product. The dashboard is supporting infrastructure.

---

## 3. Example Chat Flow

User:

> Find Pokemon TCG distributors in the UK or EU. I want sealed products like booster boxes and ETBs. Prefer suppliers that accept small retailers.

AI:

> Got it. I'll look for UK/EU suppliers that sell Pokemon TCG sealed products and may accept small retailers.
>
> I'll check:
> - Official distributors
> - Wholesalers
> - Importers
> - Specialist TCG suppliers
>
> I'll report back after each milestone.

AI:

> Milestone complete: I found 38 potential supplier websites.
>
> Next, I'm checking which ones actually mention Pokemon, trading cards, TCG, sealed products, or wholesale supply.

AI:

> Milestone complete: 14 suppliers look relevant.
>
> Breakdown:
> - 8 have email addresses
> - 4 have contact forms only
> - 2 need manual review
>
> I'm preparing outreach drafts now.

AI:

> Some suppliers ask for business information before they share wholesale pricing.
>
> Please provide the details you want me to use:
> - Store name
> - Website or marketplace link
> - Country
> - VAT number, optional
> - Expected monthly order size

---

## 4. Tech Stack

Frontend:

- Next.js 15
- React
- TypeScript
- Tailwind CSS
- shadcn/ui
- TanStack Query
- Zod

Backend:

- FastAPI
- Python
- PostgreSQL
- SQLAlchemy or SQLModel
- Redis
- Celery or Dramatiq

Agent orchestration:

- LangGraph

Web search:

- Exa API

Scraping:

- Firecrawl or Crawl4AI

Browser automation:

- Playwright

Optional AI browser control:

- browser-use

Email:

- Gmail OAuth API

Model routing:

- Internal LLM router
- LiteLLM proxy
- OpenRouter
- Google Gemini
- Groq
- Together AI
- Fireworks AI
- Mistral
- OpenAI / Anthropic as premium fallback
- Optional local Ollama/vLLM later

Local development:

- Docker Compose

---

## 5. Critical Architecture Decision: Model Routing

Model routing must be a first-class subsystem.

The app should not call OpenAI, Claude, Gemini, Groq, OpenRouter, or any provider directly from business logic.

Instead, use:

```text
Business logic
  |
  v
Internal LLM Router
  |
  v
LiteLLM Proxy
  |
  v
Providers / models
```

The router should choose the cheapest capable model for each task.

Important principle:

> Use cheap/free models for repetitive low-risk work. Use mid-tier models for communication drafts and supplier scoring. Use premium models only for complex reasoning, risky decisions, final reports, or fallback. Ask the user when business, legal, payment, contract, CAPTCHA, login, or document issues appear.

---

## 6. Model Router Requirements

The internal LLM router must support:

- task-based model selection
- model tiers
- fallback models
- confidence-based escalation
- schema validation
- retry logic
- per-user budget limits
- per-project budget limits
- per-task max cost
- provider health checks
- token/cost tracking
- latency tracking
- prompt/output logging
- model quality evaluation
- A/B testing of models
- environment-based configuration
- local/mock mode

Every LLM call must log:

- task_type
- user_id
- project_id
- input_tokens
- output_tokens
- estimated_cost_usd
- actual_cost_usd, if available
- provider
- model
- latency_ms
- prompt_version
- schema_version
- confidence
- fallback_used
- error, if any

---

## 7. Model Tiers

Tier 0: Free / local / near-free models
Use for simple, repetitive, low-risk tasks.

Tier 1: Ultra-cheap production models
Use for high-volume extraction, classification, and simple parsing.

Tier 2: Mid-tier reliable models
Use when quality matters but the task is not extremely complex.

Tier 3: Premium reasoning models
Use only for complicated or risky tasks.

Tier 4: Human/user escalation
Use when the model should not decide.

---

## 8. Default Model Routing Table

milestone_update:

- tier: 0 or 1
- examples: local model, OpenRouter free model, Gemini Flash-Lite, Groq Llama 8B

intent_classification:

- tier: 0 or 1
- examples: local Qwen/Llama, Gemini Flash-Lite, Groq model

sourcing_request_extraction:

- tier: 1
- examples: Gemini Flash-Lite, Mistral Small, Qwen small/medium

search_query_generation:

- tier: 1 or 2
- examples: Gemini Flash-Lite, Mistral Small, Qwen

search_result_filtering:

- tier: 0 or 1
- examples: Groq Llama 8B, Gemini Flash-Lite, local model

supplier_website_extraction:

- tier: 1
- examples: Gemini Flash-Lite, Together cheap model, Fireworks open model

supplier_deduplication:

- tier: 0 or code-first
- examples: deterministic code, embeddings, cheap model only if needed

supplier_relevance_scoring:

- tier: 2
- examples: Gemini Flash, Mistral Medium, Qwen large

supplier_trust_scoring:

- tier: 2 with tier 3 fallback
- examples: Gemini Flash, Claude/GPT fallback

email_draft_generation:

- tier: 2
- examples: Gemini Flash, Mistral Medium, Claude Haiku-style model

important_email_review:

- tier: 3
- examples: GPT-class premium model, Claude Sonnet-class model, Gemini Pro-class model

contact_form_field_mapping:

- tier: 1 or 2
- examples: Gemini Flash-Lite, Gemini Flash

browser_action_decision:

- tier: 2 with tier 3 fallback
- examples: Gemini Flash, GPT/Claude fallback

reply_parsing:

- tier: 1
- examples: Gemini Flash-Lite, Groq, Together cheap model

final_report_generation:

- tier: 3
- examples: GPT-class premium model, Claude Sonnet-class model, Gemini Pro-class model

---

## 9. Confidence-based Escalation

Every LLM task should return a confidence score.

Example output:

```json
{
  "result": {},
  "confidence": 0.87,
  "requires_escalation": false,
  "reason": "Supplier clearly lists wholesale Pokemon TCG products."
}
```

Routing logic:

If confidence >= 0.85:

- Accept result.

If confidence is between 0.60 and 0.85:

- Verify with another cheap or mid-tier model.

If confidence < 0.60:

- Escalate to premium model or ask user.

If task involves payment, contract, login, CAPTCHA, document upload, account creation, legal terms, pricing commitment, or exclusivity:

- Ask user.

---

## 10. Model Cascade

Use a model cascade instead of always using the strongest model.

Generic cascade:

1. Try cheapest suitable model.
2. Validate JSON schema.
3. Check required fields.
4. Check confidence.
5. Retry with stronger model if needed.
6. Escalate to user if still unclear.

Example: supplier extraction

1. Cheap model extracts supplier info.
2. Validate JSON schema.
3. Check if supplier name, website, contact method, product evidence, and confidence exist.
4. If missing or low-confidence, retry with a mid-tier model.
5. If still unclear, mark supplier as "Needs manual review."

Example: email drafting

1. Mid-tier model drafts email.
2. Cheap model checks for hallucinated business details.
3. If risky, premium model rewrites.
4. User approves before sending.

---

## 11. Provider Strategy

For MVP, support:

LiteLLM:

- Main proxy/router layer.

OpenRouter:

- Model marketplace.
- Testing different models.
- Access to cheap/free models.
- Fallback routing.

Google Gemini:

- Cheap high-volume tasks.
- Extraction.
- Classification.
- Long-context processing.

Groq:

- Fast low-cost inference.
- Simple classification.
- Simple parsing.
- Milestone updates.

Together AI / Fireworks AI:

- Cheap hosted open models.
- Useful for high-volume extraction.

Mistral:

- Cheap/mid-tier European provider option.
- Good for extraction and drafting.

OpenAI / Anthropic:

- Premium fallback only.
- Complex reasoning.
- Important communication.
- Final reports.

Initial target distribution:

80% of calls:

- cheap/free/near-free models

15% of calls:

- mid-tier models

5% of calls:

- premium models

---

## 12. Cost-saving Rules

Use deterministic code before LLMs.

Do not use an LLM for:

- email extraction
- phone extraction
- URL normalization
- domain deduplication
- basic country/domain detection
- HTML form field extraction
- checking required fields
- simple regex-based parsing

Use caching for:

- search results
- scraped website text
- supplier extraction output
- email drafts
- contact form field mappings
- reply extraction
- embeddings

Use batching for:

- search result filtering
- simple classification
- short snippet extraction
- supplier scoring where context is small

Use embeddings before LLM scoring:

1. Embed supplier page.
2. Compare with target product query.
3. Only send relevant suppliers to LLM.

Force small structured outputs:

> Return JSON only. No long explanations unless specifically required.

---

## 13. Budget Rules

Each project should have model-spend limits.

Per project:

- max_llm_cost_usd
- max_search_results
- max_suppliers_to_scrape
- max_email_drafts
- max_contact_form_inspections
- max_premium_model_calls

Per user:

- daily spend limit
- monthly spend limit
- premium call limit

Per task:

- max cost
- max retries
- max tokens

Budget behavior:

When project reaches 80% budget:

- warn user in chat.

When project exceeds budget:

- pause expensive tasks.
- ask user whether to continue.
- continue only with cheap/local models if allowed.

---

## 14. Human-in-the-loop Rules

The AI must not act fully autonomously.

The AI cannot send emails without user approval.
The AI cannot submit contact forms without user approval.
The AI cannot invent business details.
The AI cannot create supplier accounts without approval.
The AI cannot agree to contracts, purchases, pricing, exclusivity, or payment terms.
The AI cannot upload documents without explicit approval.
The AI cannot bypass CAPTCHA.
The AI cannot bypass login walls.
The AI cannot submit payment information.
The AI must ask the user for missing supplier-required information.
The AI must store evidence URLs for supplier claims.
The AI must store screenshots before form submission when possible.
Every outbound action must be logged.

Supplier-required info that should trigger a chat question:

- business name
- contact name
- business email
- phone number
- store website
- VAT number
- company registration number
- shipping address
- expected order volume
- retail/online store description
- years in business
- product categories wanted

---

## 15. Browser Automation

Use Playwright for contact-form inspection and submission.

The browser agent can:

- open public supplier websites
- find contact pages
- find wholesale application pages
- detect contact forms
- extract form fields
- identify required fields
- prepare form submissions
- take screenshots before submission
- submit forms after user approval

The browser agent cannot:

- bypass CAPTCHA
- bypass login walls
- create accounts without approval
- upload documents without approval
- submit payment information
- agree to contracts
- pretend to be human
- submit false business information

Contact form flow:

1. Supplier has no public email.
2. AI finds contact/wholesale form.
3. Playwright extracts form fields.
4. Deterministic code identifies required fields.
5. LLM maps known user/project memory to fields.
6. AI asks user for missing fields.
7. AI shows form preview in chat.
8. User approves.
9. Playwright submits form.
10. Screenshot and submission result are saved.
11. AI reports milestone.

---

## 16. LangGraph Workflow

Build a deterministic graph, not a fully free autonomous agent.

Nodes:

1. receive_chat_message
2. classify_intent
3. extract_sourcing_request
4. check_missing_user_info
5. ask_user_for_missing_info
6. generate_search_queries
7. milestone_request_understood
8. web_search_suppliers
9. milestone_suppliers_discovered
10. scrape_supplier_sites
11. extract_supplier_candidates
12. deduplicate_suppliers
13. score_suppliers
14. milestone_suppliers_verified
15. find_contact_methods
16. draft_email_if_email_exists
17. inspect_contact_form_if_no_email
18. extract_form_fields
19. ask_user_for_missing_form_info
20. create_approval_request
21. send_email_after_approval
22. submit_form_after_approval
23. milestone_outreach_completed
24. sync_inbox
25. parse_supplier_reply
26. ask_user_if_supplier_needs_more_info
27. draft_followup
28. generate_report

Workflow:

```text
START
  |
  v
Chat message received
  |
  v
Classify user intent
  |
  v
Update project state
  |
  v
Ask missing questions if needed
  |
  v
Generate research plan
  |
  v
Report milestone: request understood
  |
  v
Search web
  |
  v
Report milestone: suppliers discovered
  |
  v
Scrape supplier websites
  |
  v
Extract supplier candidates
  |
  v
Deduplicate suppliers
  |
  v
Score suppliers
  |
  v
Report milestone: suppliers verified
  |
  v
Find contact method
  |
  v
IF email exists:
      draft email
      ask user approval in chat
      send after approval
  |
  v
IF only contact form exists:
      inspect form with browser
      extract required fields
      ask user for missing info
      ask approval in chat
      submit form after approval
  |
  v
Report milestone: outreach completed
  |
  v
Monitor inbox
  |
  v
Parse replies
  |
  v
If supplier asks for more info:
      ask user in chat
      draft reply after user answers
  |
  v
Generate sourcing report
END
```

---

## 17. Database Schema

### users

```sql
id
email
name
created_at
```

### projects

```sql
id
user_id
name
description
target_products
region
budget
status
created_at
updated_at
```

### conversations

```sql
id
project_id
user_id
created_at
updated_at
```

### chat_messages

```sql
id
conversation_id
sender
message_type
content
metadata_json
created_at
```

sender values:

- user
- assistant
- system
- agent

message_type values:

- text
- milestone_update
- approval_request
- supplier_card
- form_preview
- missing_info_prompt
- error

### milestones

```sql
id
project_id
name
status
summary
metadata_json
created_at
completed_at
```

### project_memory

```sql
id
project_id
key
value
source_message_id
created_at
updated_at
```

### suppliers

```sql
id
project_id
name
website
country
email
phone
supplier_type
contact_method
trust_score
relevance_score
status
notes
created_at
updated_at
```

### supplier_sources

```sql
id
supplier_id
url
title
snippet
extracted_text
source_type
created_at
```

### contact_forms

```sql
id
supplier_id
form_url
form_type
fields_json
requires_captcha
requires_login
status
created_at
updated_at
```

### form_submissions

```sql
id
supplier_id
contact_form_id
submitted_payload_json
status
approved_by_user
screenshot_before_url
screenshot_after_url
submitted_at
created_at
```

### outreach_messages

```sql
id
project_id
supplier_id
channel
subject
body
status
approved_by_user
sent_at
created_at
```

### email_threads

```sql
id
supplier_id
gmail_thread_id
last_message_at
status
created_at
```

### supplier_terms

```sql
id
supplier_id
moq
price_list_available
payment_terms
shipping_regions
lead_time
account_requirements
extracted_from_message_id
created_at
```

### agent_runs

```sql
id
project_id
agent_type
task_type
status
input_json
output_json
error
provider
model
input_tokens
output_tokens
estimated_cost_usd
actual_cost_usd
latency_ms
prompt_version
schema_version
confidence
fallback_used
created_at
updated_at
```

### audit_logs

```sql
id
user_id
action
entity_type
entity_id
metadata_json
created_at
```

### llm_budgets

```sql
id
user_id
project_id
daily_limit_usd
monthly_limit_usd
project_limit_usd
premium_call_limit
current_daily_spend_usd
current_monthly_spend_usd
current_project_spend_usd
created_at
updated_at
```

### llm_model_configs

```sql
id
task_type
tier
provider
model
priority
max_input_tokens
max_output_tokens
max_cost_usd
enabled
created_at
updated_at
```

---

## 18. API Endpoints

### Chat

```http
POST /projects/:id/chat
GET /projects/:id/messages
```

### Projects

```http
POST /projects
GET /projects
GET /projects/:id
PATCH /projects/:id
DELETE /projects/:id
```

### Milestones

```http
GET /projects/:id/milestones
POST /projects/:id/milestones
PATCH /milestones/:id
```

### Research

```http
POST /projects/:id/research/start
GET /projects/:id/research/status
```

### Suppliers

```http
GET /projects/:id/suppliers
GET /suppliers/:id
PATCH /suppliers/:id
```

### Forms

```http
POST /suppliers/:id/forms/inspect
GET /suppliers/:id/forms
POST /forms/:id/prepare-submission
POST /forms/:id/approve-submit
POST /forms/:id/reject
```

### Approvals

```http
GET /projects/:id/approvals
POST /approvals/:id/approve
POST /approvals/:id/reject
PATCH /approvals/:id/edit
```

### Outreach

```http
POST /suppliers/:id/outreach/draft
GET /projects/:id/outreach/pending
POST /outreach/:id/approve-send
POST /outreach/:id/reject
PATCH /outreach/:id
```

### Inbox

```http
POST /inbox/sync
GET /projects/:id/replies
POST /replies/:id/extract
POST /replies/:id/draft-followup
```

### Reports

```http
POST /projects/:id/report/generate
GET /projects/:id/report
GET /projects/:id/export.csv
```

### LLM Router

```http
POST /llm/complete
GET /llm/usage/project/:id
GET /llm/usage/user/:id
GET /llm/models
PATCH /llm/models/:id
GET /llm/budgets/project/:id
PATCH /llm/budgets/project/:id
```

---

## 19. Frontend Components

- ChatWorkspace
- ChatMessageList
- ChatInput
- MilestoneMessage
- ApprovalCard
- SupplierCard
- SupplierSidePanel
- ProjectSidebar
- FormPreviewCard
- MissingInfoPrompt
- SupplierTable
- ProjectStatusBadge
- BudgetUsageBadge
- ModelUsageDebugPanel

The ModelUsageDebugPanel should only be visible in development/admin mode.

It should show:

- model used
- provider
- task type
- cost
- latency
- confidence
- fallback used

---

## 20. Approval Cards

### Email Approval Card

Show:

- supplier name
- recipient email
- subject
- body
- source evidence
- detected missing information
- approve button
- edit button
- reject button

### Contact Form Approval Card

Show:

- supplier name
- form URL
- detected fields
- values to submit
- missing fields
- screenshot preview if available
- approve submit button
- edit button
- reject button

---

## 21. Supplier Statuses

- Discovered
- Needs Verification
- Qualified
- Email Found
- Contact Form Found
- Missing User Info
- Email Drafted
- Form Prepared
- Pending Approval
- Email Sent
- Form Submitted
- Replied
- Follow-up Needed
- Rejected
- Converted
- Manual Review Needed

---

## 22. Mock Mode

If API keys are missing, the app must still work locally.

Mock mode should provide:

- mock chat responses
- mock milestones
- mock suppliers
- mock supplier scores
- mock email drafts
- mock contact forms
- mock reply parsing
- mock report generation

This allows development without paying for LLM/search/scraping APIs.

---

## 23. Environment Variables

```env
DATABASE_URL=
REDIS_URL=

APP_ENV=development
MOCK_MODE=true

EXA_API_KEY=
FIRECRAWL_API_KEY=

GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GMAIL_REDIRECT_URI=

LITELLM_PROXY_URL=
LITELLM_MASTER_KEY=

OPENROUTER_API_KEY=
GEMINI_API_KEY=
GROQ_API_KEY=
TOGETHER_API_KEY=
FIREWORKS_API_KEY=
MISTRAL_API_KEY=
OPENAI_API_KEY=
ANTHROPIC_API_KEY=

DEFAULT_CHEAP_MODEL=
DEFAULT_MID_MODEL=
DEFAULT_PREMIUM_MODEL=

MAX_PROJECT_LLM_COST_USD=5
MAX_USER_DAILY_LLM_COST_USD=2
MAX_PREMIUM_CALLS_PER_PROJECT=5
```

---

## 24. Build Order

1. Project setup and Docker Compose
2. Database models and migrations
3. Internal LLM router interface
4. LiteLLM proxy setup
5. Mock model provider
6. Budget and logging system
7. Chat UI
8. Project creation through chat
9. Milestone system
10. Mock research workflow
11. Real search/scraping integration
12. Supplier table and side panel
13. Supplier extraction and scoring
14. Email draft approval
15. Contact form inspection with Playwright
16. Contact form approval/submission
17. Gmail OAuth and email sending
18. Inbox sync and reply extraction
19. Report generation
20. Admin/debug model usage panel

---

## 25. Deliverables

- Working Docker Compose setup
- README
- .env.example
- Database migrations
- Backend tests
- Frontend chat workspace
- Supplier side panel
- Basic LangGraph workflow
- Mock mode
- Internal LLM router
- LiteLLM integration
- OpenRouter integration
- Gemini/Groq integration scaffolds
- Cost and usage logging
- Budget enforcement
- Real Exa/Firecrawl/Playwright integration points
- Gmail OAuth integration scaffold

---

## 26. Backend Tests To Include

- project creation from chat
- sourcing request extraction
- model router task selection
- model fallback behavior
- budget limit enforcement
- confidence-based escalation
- supplier deduplication
- supplier extraction schema validation
- email draft hallucination check
- contact form field extraction
- missing user info detection
- approval flow
- audit logging

---

## 27. Final MVP Principle

The AI should feel like an employee doing sourcing work for the user.

It should:

- communicate progress
- ask for missing information
- show work before taking action
- never invent business details
- never send or submit anything without approval
- use cheap models whenever possible
- escalate only when the task is complex or risky

---

## Codex Additions

These additions do not replace the original plan. They tighten implementation boundaries so later issue work stays aligned.

### A. Approval Requests As First-class Data

Add an `approval_requests` table instead of relying only on `approved_by_user` flags on outreach/form rows.

```sql
id
project_id
supplier_id
request_type
status
title
payload_json
decision_json
requested_by_agent_run_id
decided_by_user_id
decided_at
expires_at
created_at
updated_at
```

request_type values:

- email_send
- contact_form_submit
- document_upload
- account_creation
- followup_send
- budget_continue
- manual_review

status values:

- pending
- approved
- rejected
- edited
- expired
- cancelled

### B. Background Jobs And Idempotency

Long-running or outbound work should be represented as jobs and keyed for safe retries.

Add an `agent_jobs` or `workflow_runs` concept for:

- web search
- scraping
- contact-form inspection
- email draft generation
- email send
- contact-form submit
- inbox sync
- reply parsing
- report generation

Every outbound or external side-effect should accept/store an idempotency key:

- email send
- contact form submit
- Gmail inbox sync
- workflow node execution that writes derived records

### C. Auth And Tenant Boundaries

Even in mock mode, shape records around `user_id` and `project_id`.

Rules:

- Every project belongs to a user or organization.
- Every API query must be scoped by authenticated user/tenant.
- Future Gmail OAuth credentials must be encrypted at rest.
- Audit logs must include user, project, action, entity type, entity id, and metadata.

### D. CI And Quality Gates

From the first implementation issue, CI should include:

- backend tests
- backend lint/type checks once tooling is installed
- frontend lint/typecheck/build
- migration smoke test
- Docker Compose config validation

### E. Crawl And Outreach Safety Defaults

Real integrations must obey these rules:

- Respect robots/rate-limit policy where applicable.
- Store source URLs and evidence snippets for supplier claims.
- Do not bypass CAPTCHA or login walls.
- Do not pretend to be human.
- Do not submit false business information.
- Do not send emails or submit forms without a pending approval record being approved.
- Store screenshots before contact-form submission when possible.
- Pause and ask the user for payment, contracts, exclusivity, document upload, account creation, or legal commitments.

