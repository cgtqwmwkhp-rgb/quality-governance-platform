# Voluntary Product Accessibility Template (VPAT®)

**Product name:** Quality Governance Platform  
**Product version:** v2.x  
**Report date:** 2026-03-20  
**Contact:** Product & Platform Engineering (accessibility@quality-governance.platform — Quality Governance Platform Accessibility Team)  

**Evaluation standard:** Web Content Accessibility Guidelines (WCAG) 2.1 Level AA  

**Scope:** Web application (React/Vite frontend) and associated public employee portal surfaces exercised in release testing. Native mobile wrappers, if used, are out of scope unless explicitly listed in a future revision.

---

## Notes for interpreting this report

- **Supports** — The criterion is met for the product as delivered and evaluated, **or** the criterion does not apply to current content/features and there is no user-facing gap (explained in Remarks).  
- **Partially Supports** — The criterion is met in part; exceptions or gaps are described.  
- **Does Not Support** — The criterion is not met for substantial parts of the product.

**Evaluation methods used**

- **Automated:** axe-core (via Vitest/jest-axe and CI accessibility lint gates on the frontend; see `.github/workflows/ci.yml` frontend job).  
- **Manual keyboard:** Full keyboard traversal of primary layouts, modals, and forms; focus order checks.  
- **Screen reader:** Spot-checks with VoiceOver (macOS/iOS) and NVDA (Windows) on representative flows (navigation, incident/portal reporting, data tables).  

**Product notes referenced in remarks**

- Skip-to-content link and landmark structure on main shell layouts.  
- `eslint-plugin-jsx-a11y` blocking gate for critical a11y anti-patterns in `frontend/src/`.  
- Form labels and error association patterns aligned with React Testing Library / design system components.

---

## WCAG 2.1 Level AA — Summary Table

| Criterion | Level | Conformance | Remarks and explanations |
|-----------|-------|-------------|-------------------------|
| **1.1.1** Non-text Content | A | **Supports** | Meaningful images and icons use accessible names or are marked decorative; automated axe-core checks catch missing names on tested components. Decorative assets use `alt=""` or equivalent. |
| **1.2.1** Audio-only and Video-only (Prerecorded) | A | **Supports** | No prerecorded audio-only or video-only content is in scope for the evaluated release; users are not presented with such barriers. Re-evaluate if media is added. |
| **1.3.1** Info and Relationships | A | **Partially Supports** | Semantic HTML and ARIA used for headings, lists, and tables in key screens; some complex data-dense views (filters, dense tables) rely on visual grouping that is not always exposed with full structure in every state. Evidence: keyboard review + axe on representative pages; design system patterns for `table`/`thead`/`th` where used. |
| **1.4.1** Use of Color | A | **Supports** | Status and severity are not conveyed by color alone; icons/text labels accompany color cues in primary workflows. Manual review of incident/RTA status patterns. |
| **1.4.3** Contrast (Minimum) | AA | **Partially Supports** | Core theme meets contrast for primary text and controls; a small number of secondary badges, disabled states, and chart colors may fall below 4.5:1 in edge themes or data visualisations. Evidence: axe contrast rules + manual sampling. |
| **1.4.4** Resize Text | AA | **Supports** | Layouts use responsive typography; browser zoom to 200% verified on main employee and authenticated dashboards without loss of essential functionality. |
| **2.1.1** Keyboard | A | **Partially Supports** | Primary navigation, forms, and dialogs are operable via keyboard; some third-party or legacy widgets (e.g. certain pickers, map/embed placeholders) may require extra tab stops or lack visible focus until refactored. Evidence: manual keyboard pass; focus trap checks on modals. |
| **2.1.2** No Keyboard Trap | A | **Supports** | Modal dialogs and drawers use focus containment with Esc/close controls verified in manual keyboard testing. |
| **2.4.1** Bypass Blocks | A | **Supports** | Skip link to main content is available on primary layouts; landmark regions (`header`, `nav`, `main`) used for efficient navigation with screen readers. |
| **2.4.2** Page Titled | A | **Supports** | Routes set document titles reflecting module context (e.g. incidents, audits); verified in spot-checks. |
| **2.4.3** Focus Order | A | **Partially Supports** | Focus order matches reading order on most pages; exceptions may occur in multi-column filter toolbars or dynamically injected panels where order is being tightened. |
| **2.4.4** Link Purpose (In Context) | A | **Supports** | Link text and `aria-label` patterns reviewed for “read more” / icon-only controls in tested flows. |
| **2.4.7** Focus Visible | AA | **Partially Supports** | Default focus rings enabled; custom components sometimes use subtle focus styles that meet contrast in light mode but are harder to perceive in dark mode or on busy backgrounds. Evidence: keyboard testing + design token review. |
| **3.1.1** Language of Page | A | **Supports** | `lang` attribute set on root HTML; content is predominantly English (Welsh/Polish roadmap items tracked separately). |
| **3.2.1** On Focus | A | **Supports** | Focus changes do not trigger unexpected context changes on evaluated components; validated on autocomplete and filter controls used in testing. |
| **3.3.1** Error Identification | A | **Partially Supports** | API and form errors surface messages in UI; not all fields consistently associate programmatically via `aria-describedby` across every legacy form variant. Evidence: portal submission flows + axe on form tests. |
| **3.3.2** Labels or Instructions | A | **Supports** | Required fields and formats documented in labels/helper text on primary reporting flows; jsx-a11y rules reduce unlabeled inputs in new code. |
| **4.1.1** Parsing | A | **Supports** | Tested builds use valid DOM output from React; no duplicate-ID or broken nesting issues observed in axe-core runs and manual checks on sampled pages. |
| **4.1.2** Name, Role, Value | A | **Partially Supports** | Interactive components largely expose correct roles/states (`button`, `expanded`, `selected`); a subset of custom composites still needs explicit `aria-*` parity with visual state (e.g. advanced filters, multi-selects). Evidence: screen reader spot-checks + axe rules. |

---

## Remediation plan (Partially Supports only)

| Criterion | Remediation actions | Target outcome |
|-----------|---------------------|----------------|
| **1.3.1** | Audit dense tables and filter panels; ensure `scope`/headers or `aria` relationships; add captions or summaries where tables are used for layout incorrectly. | Full programmatic structure on top 10 IMS screens. |
| **1.4.3** | Tokenise chart and badge colours; fix failing pairs in theme; add patterns for data series. | 100% of primary UI text/control pairs ≥ 4.5:1 (or 3:1 for large text) on default themes. |
| **2.1.1** | Replace or wrap problematic widgets; ensure all actions have keyboard equivalents; document shortcuts where applicable. | No essential task blocked by keyboard-only use. |
| **2.4.3** | Re-order DOM or use `tabIndex` only where necessary after DOM order fix; test filter-heavy pages. | Focus order matches visual reading order on audited pages. |
| **2.4.7** | Align focus ring tokens with WCAG non-text contrast; verify dark mode. | Consistent, perceivable focus across components. |
| **3.3.1** | Standardise error summary pattern; wire `aria-invalid` / `aria-describedby` for all form controls. | Errors programmatically tied to fields in portal + admin forms. |
| **4.1.2** | Component library pass for composites; add tests with axe + screen reader scripts. | Roles/states match visual UI for audited components. |

---

## Legal disclaimer

This VPAT is provided in good faith based on internal evaluation as of the report date. It is not a certificate of compliance. Customers should perform their own assessments for their deployment context, integrations, and customisations.
