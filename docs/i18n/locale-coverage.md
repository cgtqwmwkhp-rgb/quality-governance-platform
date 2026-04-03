# Locale Coverage Report (D27)

Tracking of translation coverage across supported locales.

## Supported Locales

| Locale | Language | Status | Key Count | Coverage |
|--------|----------|--------|-----------|----------|
| `en` | English | Primary (complete) | ~2000+ | 100% |
| `cy` | Welsh | Partial | ~56 | ~3% |

## Coverage Strategy

Per [ADR-0010](../adr/ADR-0010-backend-i18n-strategy.md), all localization is handled in the frontend. The backend API is English-only.

### Partial Locale Strategy

Welsh (`cy`) is maintained as a partial locale. The i18n framework (`react-i18next`) falls back to English (`en`) for any key not present in the Welsh locale file. This means:

1. **Core navigation and labels** are prioritized for Welsh translation.
2. **Domain-specific content** (e.g., audit finding types, risk categories) falls back to English.
3. **User-generated content** (titles, descriptions) is not translated.

### Coverage Targets

| Milestone | Target Coverage | Key Categories |
|-----------|----------------|----------------|
| Phase 1 (current) | ~3% | Navigation, common buttons, page titles |
| Phase 2 | 20% | Form labels, status values, priority levels |
| Phase 3 | 50% | All static UI text, error messages |
| Phase 4 | 80% | Full coverage excluding domain-specific terms |

## CI Enforcement

The `scripts/i18n-check.mjs` script validates:
1. All `t('key')` calls in `.tsx`/`.ts` files have corresponding entries in `en.json`.
2. Welsh (`cy.json`) key parity is tracked (non-blocking) to monitor coverage drift.

## Adding Translations

1. Add the English key to `frontend/src/i18n/locales/en.json`.
2. Optionally add the Welsh translation to `frontend/src/i18n/locales/cy.json`.
3. Run `node scripts/i18n-check.mjs` to validate.

## Related Documents

- [`docs/adr/ADR-0010-backend-i18n-strategy.md`](../adr/ADR-0010-backend-i18n-strategy.md) — backend i18n decision
- [`frontend/src/i18n/locales/en.json`](../../frontend/src/i18n/locales/en.json) — English locale
- [`frontend/src/i18n/locales/cy.json`](../../frontend/src/i18n/locales/cy.json) — Welsh locale
- [`scripts/i18n-check.mjs`](../../scripts/i18n-check.mjs) — CI validation script
