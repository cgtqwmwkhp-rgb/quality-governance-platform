# ADR-0010: Backend I18n Strategy

## Status

Accepted

## Date

2026-04-03

## Context

The Quality Governance Platform supports multi-language UI through frontend i18n (react-i18next with `en.json` and `cy.json` locale files). The question arises whether the backend API should also return localized responses.

Backend API responses include:
- Error messages (validation errors, HTTP error details)
- Enum labels (status values, priority levels, severity names)
- System-generated text (reference numbers, audit trail entries)

## Decision

**Backend remains English-only for API responses.** All localization is the frontend's responsibility.

### Rationale

1. **API consumers are machines first**: API responses are consumed by the React frontend, mobile apps, and third-party integrations. These consumers handle their own display localization.
2. **Separation of concerns**: The backend provides structured data (enums, codes, ISO dates). The frontend maps these to human-readable, localized strings via its i18n framework.
3. **Simplicity**: Adding backend i18n introduces complexity (Accept-Language header parsing, message catalogs, fallback chains) with minimal benefit since all current consumers already have frontend i18n.
4. **Error codes over messages**: API error responses use structured error codes (`VALIDATION_ERROR`, `NOT_FOUND`, etc.) that the frontend maps to localized messages. Human-readable error `detail` strings are supplementary.

### Exceptions

- **Email notifications**: If/when the platform sends user-facing emails, those should be localized based on user language preference. This is a future concern and will be addressed in a separate ADR.
- **PDF report generation**: Server-generated PDF reports (e.g., audit reports, customer packs) may need localized templates. This is also a future concern.

## Consequences

- Frontend `en.json` remains the single source of truth for all user-facing strings.
- `cy.json` (Welsh) coverage should be tracked and improved to reach parity with `en.json`.
- No `Accept-Language` header processing is needed in the backend middleware.
- Backend validation error messages remain in English; the frontend maps error codes to localized messages.

## Related

- `frontend/src/i18n/locales/en.json` — English locale (primary)
- `frontend/src/i18n/locales/cy.json` — Welsh locale (partial)
- `scripts/i18n-check.mjs` — CI key validation script
- `docs/i18n/locale-coverage.md` — locale coverage tracking
