# Internationalization and localization (D27)

Guide for translators, developers, and CI for the Quality Governance Platform frontend.

## Current state

- **Strings**: More than **2000** translation keys in a flat JSON map in [`frontend/src/i18n/locales/en.json`](../../frontend/src/i18n/locales/en.json) (approximately **2100+** keys at last count).
- **Libraries**: **i18next**, **react-i18next**, and **i18next-browser-languagedetector** (see [`frontend/package.json`](../../frontend/package.json)).
- **Initialization**: [`frontend/src/i18n/i18n.ts`](../../frontend/src/i18n/i18n.ts) registers English resources, enables `LanguageDetector`, sets `fallbackLng: 'en'`, uses `localStorage` + `navigator` for detection, and logs missing keys in development via `missingKeyHandler`.

## Adding a new locale

1. **Copy the source file**: Duplicate `frontend/src/i18n/locales/en.json` to a new file, for example `frontend/src/i18n/locales/fr.json`.
2. **Translate values**: Keep JSON keys identical; translate only string values. Preserve interpolation placeholders such as `{{count}}` or `{{name}}` exactly.
3. **Register in i18n config**: In [`frontend/src/i18n/i18n.ts`](../../frontend/src/i18n/i18n.ts), import the new JSON and add it to `resources`, for example `fr: { translation: fr }`.
4. **Expose language selection** (if not already): Ensure the UI can set `i18n.changeLanguage('fr')` and that the detector order still makes sense (often `localStorage` first).
5. **Run the key check**: From `frontend/`, run `npm run i18n:check` (see below). Ensure every `t('…')` key used in code exists in **all** locale files, or extend the script to validate multiple files if you add that capability.
6. **Smoke test**: Load the app, switch language, and walk critical flows (forms, tables, errors, dates).

## Translation key conventions

Use **dot-separated** paths that read as **`namespace.feature.element`** (logical namespaces, not i18next multi-namespace files unless you introduce them later).

Examples (from `en.json`):

- `actions.table.status` — table column label in the Actions feature.
- `admin.contracts.title` — admin contracts screen title.
- `a11y.skip_to_content` — accessibility string.

**Rules of thumb**

- Keep keys **stable**; prefer adding a new key over repurposing an old one when meaning changes.
- Use **lower_snake_case** segments after the first dot where it improves readability (`nav.audit_builder`).
- Group by **surface** (`admin.*`, `portal.*`, `workforce.*`) and then **feature** and **widget**.

## CI enforcement

[`scripts/i18n-check.mjs`](../../scripts/i18n-check.mjs) walks `frontend/src` for `t('key')` / `t("key")` / `` t(`key`) `` calls and asserts each key exists in `en.json`. It skips patterns containing `{{` or `$` (dynamic keys).

- **Command**: `npm run i18n:check` from `frontend/` (defined in [`frontend/package.json`](../../frontend/package.json)).
- **Exit code**: Non-zero if any referenced key is missing from `en.json`.

Integrate this script into your CI pipeline so pull requests cannot merge with missing English keys.

## Pluralization

i18next pluralization is enabled with `pluralSeparator: '_'`. For keys that vary by count, define base and plural forms in `en.json`, for example:

- `a11y.search_results_count` — singular form with `{{count}}`
- `a11y.search_results_count_other` — plural form

Use `t('a11y.search_results_count', { count: n })` and ensure the `_other` suffix key exists for English plural rules.

## Date and number formatting

- Prefer the **ECMAScript Intl API** (`Intl.DateTimeFormat`, `Intl.NumberFormat`, `Intl.RelativeTimeFormat`) in helpers or components, driven by `i18n.language` (or a resolved locale string).
- Keep **raw locale-specific literals** out of business logic; format at the UI boundary so domain code stays locale-agnostic.
- Where **date-fns** is used, pair it with an explicit locale import when you need non-English formatting.

## RTL support plan (Arabic / Hebrew)

RTL locales require more than string translation:

- **Layout**: Audit flex/grid directions; use logical properties (`margin-inline-start`, `padding-inline-end`) or Tailwind RTL plugins where appropriate so sidebars and drawers mirror correctly.
- **Icons and chevrons**: Mirror directional icons (back arrows, carousel controls) when `dir="rtl"`.
- **Tables and numeric columns**: Verify alignment and scroll behaviour; numbers may remain LTR inside RTL text.
- **Embedded English**: Product names or codes may stay LTR; wrap with Unicode bidi isolates if mixed strings render incorrectly.
- **Testing**: Add visual and accessibility checks for at least one RTL locale before marking RTL as supported.
