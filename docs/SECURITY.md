# Security And Secret Storage

This project is mock-safe by default. Real provider access must be enabled through explicit environment flags and credentials.

## Secrets

- Local development uses `.env`, which must never be committed.
- Production secrets should live in the deployment platform secret manager, not in GitHub variables unless the value is non-sensitive.
- GitHub Actions should use environment-scoped secrets for deploy-only jobs.
- Future OAuth credentials for Gmail, Google, Microsoft, or supplier portals must be stored server-side only.
- Access tokens must be encrypted at rest before persistence. Refresh tokens should be scoped to the minimum required mailbox or account permissions.

## Provider Credentials

- `EXA_API_KEY`, `FIRECRAWL_API_KEY`, `LITELLM_MASTER_KEY`, and future OAuth client secrets are privileged credentials.
- Backend code should read credentials through typed settings only.
- Frontend code must not receive provider keys, refresh tokens, LiteLLM keys, or crawl provider keys.
- Health checks should report configured/not configured status without echoing secret values.

## Production Defaults

- `MOCK_MODE=true` is the safest default.
- Real search requires `MOCK_MODE=false`, `ENABLE_REAL_SEARCH=true`, and `EXA_API_KEY`.
- Real scraping requires `MOCK_MODE=false`, `ENABLE_REAL_SCRAPING=true`, and `FIRECRAWL_API_KEY`.
- Production CORS origins must be explicit. Wildcard origins are rejected by settings validation.

## Risky Workflows

- Email sending, contact form submission, browser automation, and any legal/payment/account action require an `approval_request`.
- Approval cards must show the exact payload values to be sent or submitted.
- Decisions and outbound executions must be written to `audit_logs`.
- Provider failures must degrade to mock fallback or safe errors, never autonomous outbound action.
