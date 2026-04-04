# Page-Level Story & Screen Inventory (D02)

> Last updated: 2026-04-04
> Review cycle: Monthly

---

## Purpose

This document catalogues every page, screen, and view in the Quality Governance Platform. For each it records the route, owning persona, layout pattern, component usage, state coverage, Storybook story status, UX patterns, navigation context, and accessibility posture. It serves as the single source of truth for:

- **UX audits** — identifying screens that lack empty-state, error, or loading treatment.
- **Story gap analysis** — pinpointing pages and page-level compositions without Storybook coverage.
- **Design system alignment** — verifying that every page composes from the shared `components/ui/` primitives documented in `component-inventory.md`.
- **Accessibility compliance** — tracking ARIA landmarks, keyboard operability, and screen-reader announcements per screen.

Cross-references: `information-architecture.md` (sitemap & navigation hierarchy), `component-inventory.md` (primitive catalogue), `design-system.md` (tokens & patterns), `storybook-plan.md` (story backlog), `personas-and-journeys.md` (persona definitions P1–P5).

---

## Information Architecture Overview

The platform ships two independent navigation shells:

1. **Admin Shell** (`Layout.tsx`) — sidebar + top-bar, 72 px left rail on desktop, hamburger overlay on mobile. Houses all authenticated admin/manager/supervisor views.
2. **Portal Shell** (`PortalLayout.tsx`) — mobile-first single-column layout for unauthenticated or SSO-authenticated field workers.

```
Root (/)
├── /login                           Auth
├── /forgot-password                 Auth
├── /reset-password                  Auth
│
├── / (Layout shell, auth-gated)
│   ├── /dashboard                   Core
│   │
│   ├── CORE ──────────────────────────────
│   │   ├── /incidents               List
│   │   ├── /incidents/:id           Detail
│   │   ├── /near-misses             List
│   │   ├── /near-misses/:id         Detail
│   │   ├── /rtas                    List
│   │   ├── /rtas/:id                Detail
│   │   ├── /complaints              List
│   │   ├── /complaints/:id          Detail
│   │   └── /vehicle-checklists      List
│   │
│   ├── GOVERNANCE ────────────────────────
│   │   ├── /audits                  Kanban / List / Findings
│   │   ├── /audit-templates         Library
│   │   ├── /audit-templates/new     Builder (Wizard)
│   │   ├── /audit-templates/:id/edit Builder (Wizard)
│   │   ├── /audits/:id/execute      Execution (Form)
│   │   ├── /audits/:id/import-review Review (Form)
│   │   ├── /audits/:id/mobile       Mobile Execution
│   │   ├── /investigations          List
│   │   ├── /investigations/:id      Detail (Tabbed)
│   │   ├── /standards               List
│   │   ├── /actions                 List
│   │   ├── /compliance              Evidence Matrix
│   │   ├── /uvdb                    List
│   │   ├── /planet-mark             Dashboard / List
│   │   ├── /customer-audits         List
│   │   └── /signatures              List
│   │
│   ├── LIBRARY ───────────────────────────
│   │   ├── /documents               List
│   │   ├── /policies                List
│   │   └── /risks                   List
│   │
│   ├── ENTERPRISE ────────────────────────
│   │   ├── /risk-register           Register + Heatmap
│   │   ├── /ims                     IMS Dashboard
│   │   └── /ai-intelligence         Dashboard
│   │
│   ├── ANALYTICS ─────────────────────────
│   │   ├── /analytics               Overview
│   │   ├── /analytics/advanced      Advanced
│   │   ├── /analytics/dashboards    Dashboard Builder
│   │   ├── /analytics/reports       Report Generator
│   │   ├── /calendar                Calendar
│   │   └── /exports                 Export Center
│   │
│   ├── AUTOMATION ────────────────────────
│   │   ├── /workflows               Workflow Center
│   │   ├── /compliance-automation   Compliance Automation
│   │   └── /signatures              Digital Signatures
│   │
│   ├── WORKFORCE (admin/supervisor) ──────
│   │   ├── /workforce/assessments       List
│   │   ├── /workforce/assessments/new   Create (Form)
│   │   ├── /workforce/assessments/:id/execute  Execution
│   │   ├── /workforce/training          List
│   │   ├── /workforce/training/new      Create (Form)
│   │   ├── /workforce/training/:id/execute Execution
│   │   ├── /workforce/engineers         List
│   │   ├── /workforce/engineers/:id     Profile (Detail)
│   │   ├── /workforce/calendar          Calendar
│   │   └── /workforce/dashboard         Competency Dashboard
│   │
│   ├── ADMIN (role-gated) ────────────────
│   │   ├── /admin                   Admin Dashboard
│   │   ├── /admin/forms             Forms List
│   │   ├── /admin/forms/new         Form Builder
│   │   ├── /admin/forms/:id         Form Builder (Edit)
│   │   ├── /admin/contracts         Contracts Management
│   │   ├── /admin/settings          System Settings
│   │   ├── /admin/users             User Management
│   │   ├── /admin/lookups           Lookup Tables
│   │   ├── /admin/notifications     Notification Settings
│   │   └── /audit-trail             Audit Trail Viewer
│   │
│   ├── TOOLS ─────────────────────────────
│   │   ├── /search                  Global Search
│   │   └── /notifications           Notification Centre
│   │
│   └── /* (catch-all)               404 Not Found
│
├── /portal/login                    Portal Auth
└── /portal (PortalLayout shell)
    ├── /portal                      Portal Home
    ├── /portal/report               Report Type Picker
    ├── /portal/report/incident      Dynamic Form
    ├── /portal/report/near-miss     Dynamic Form
    ├── /portal/report/complaint     Dynamic Form
    ├── /portal/report/rta           RTA Form
    ├── /portal/report/incident-legacy  Legacy Incident Form
    ├── /portal/report/near-miss-static Legacy Near-Miss Form
    ├── /portal/track                Status Tracker
    ├── /portal/track/:referenceNumber  Tracker (deep link)
    └── /portal/help                 Help & FAQ
```

**Navigation sections** defined in `Layout.tsx`: Core, Workforce, Governance, Library, Enterprise, Analytics, Automation, Admin.

---

## Existing Storybook Coverage

26 component-level stories exist, all under `frontend/src/components/ui/`:

| Story file | Component | a11y tested |
|---|---|---|
| `AlertDialog.stories.tsx` | AlertDialog | Yes |
| `Avatar.stories.tsx` | Avatar | No |
| `Badge.stories.tsx` | Badge | Yes |
| `Breadcrumbs.stories.tsx` | Breadcrumbs | No |
| `Button.stories.tsx` | Button | Yes |
| `Card.stories.tsx` | Card | Yes |
| `Checkbox.stories.tsx` | Checkbox | Yes |
| `DataTable.stories.tsx` | DataTable | Yes |
| `Dialog.stories.tsx` | Dialog | Indirect |
| `DropdownMenu.stories.tsx` | DropdownMenu | Yes |
| `EmptyState.stories.tsx` | EmptyState | Yes |
| `Input.stories.tsx` | Input | Yes |
| `Label.stories.tsx` | Label | Yes |
| `LiveAnnouncer.stories.tsx` | LiveAnnouncer | — |
| `LoadingSkeleton.stories.tsx` | LoadingSkeleton | No |
| `ProgressBar.stories.tsx` | ProgressBar | Yes |
| `RadioGroup.stories.tsx` | RadioGroup | Yes |
| `Select.stories.tsx` | Select | Yes |
| `SetupRequiredPanel.stories.tsx` | SetupRequiredPanel | — |
| `SkeletonLoader.stories.tsx` | SkeletonLoader | No |
| `Switch.stories.tsx` | Switch | Yes |
| `Tabs.stories.tsx` | Tabs | Yes |
| `Textarea.stories.tsx` | Textarea | No |
| `ThemeToggle.stories.tsx` | ThemeToggle | No |
| `Toast.stories.tsx` | Toast | — |
| `Tooltip.stories.tsx` | Tooltip | No |

**Zero page-level stories exist.** All 26 stories cover primitives only.

---

## Page Inventory

### Legend

| Symbol | Meaning |
|---|---|
| **[S]** | State is implemented in code |
| **[ ]** | State is missing / not implemented |
| **[P]** | Partial — handled but incomplete |

---

### 1. Authentication

#### 1.1 Login

- **Route**: `/login`
- **File**: `pages/Login.tsx`
- **Purpose**: Authenticate admin/manager/supervisor users with email + password
- **Persona(s)**: P2 Quality Auditor, P3 Risk Manager, P4 System Admin, P5 Executive
- **Layout Pattern**: Centred card (no sidebar)
- **Key Components**: `Input`, `Button`, `Card`
- **States Covered**:
  - [S] Default (form ready)
  - [S] Loading (submit spinner)
  - [S] Error (invalid credentials)
  - [ ] Rate-limit feedback
  - [S] Redirect to `/dashboard` if already authenticated
- **Story Coverage**: None — needs `Login.stories.tsx`
- **UX Patterns**: Form validation on submit; links to forgot-password
- **Navigation**: Entry point; redirects to `/dashboard` on success; link to `/forgot-password`
- **Accessibility**: Form labels present; `aria-required` on fields

#### 1.2 Forgot Password

- **Route**: `/forgot-password`
- **File**: `pages/ForgotPassword.tsx`
- **Purpose**: Initiate password reset flow via email
- **Persona(s)**: All admin personas
- **Layout Pattern**: Centred card
- **Key Components**: `Input`, `Button`
- **States Covered**:
  - [S] Default form
  - [S] Success confirmation
  - [S] Error state
  - [ ] Rate limiting
- **Story Coverage**: None
- **Navigation**: From `/login`; back to `/login`

#### 1.3 Reset Password

- **Route**: `/reset-password`
- **File**: `pages/ResetPassword.tsx`
- **Purpose**: Set new password using token from email link
- **Persona(s)**: All admin personas
- **Layout Pattern**: Centred card
- **Key Components**: `Input`, `Button`
- **States Covered**:
  - [S] Default form
  - [S] Token expired / invalid
  - [S] Success
- **Story Coverage**: None
- **Navigation**: From email link; redirects to `/login` on success

---

### 2. Dashboard & Overview

#### 2.1 Main Dashboard

- **Route**: `/dashboard`
- **File**: `pages/Dashboard.tsx`
- **Purpose**: Executive overview of platform KPIs — incidents, RTAs, complaints, audits, risks, compliance, carbon
- **Persona(s)**: P2, P3, P5 (primary landing page for all authenticated users)
- **Layout Pattern**: Dashboard — stat cards + widget grid
- **Key Components**: `Card`, `CardHeader`, `CardTitle`, `CardContent`, `CardSkeleton`, `Button`, `Badge`, custom `StatCard`, `ComplianceGauge`, `ActivityFeed`, `UpcomingEvents`
- **States Covered**:
  - [S] Loading (full-page `CardSkeleton` with shimmer)
  - [S] Populated (stat cards, compliance gauges, activity feed, incidents table, quick actions)
  - [S] Error (dismissible error banner with retry)
  - [S] Empty (individual widgets show "No recent activity" / "No upcoming events")
  - [ ] Permission-denied (not applicable — all authenticated users see dashboard)
- **Story Coverage**: None — needs `Dashboard.stories.tsx` (complex; consider composition story)
- **UX Patterns**: Refresh button; notification badge count; quick-action cards linking to modules; compliance progress bars; activity feed with status badges; responsive 2→4-column grid
- **Navigation**: Default landing after login; links out to every major module via stat cards and quick actions
- **Accessibility**: Skip-to-content link in `Layout`; semantic heading hierarchy (`h1` Dashboard); uses `<table>` for incidents with column headers

#### 2.2 IMS Dashboard

- **Route**: `/ims`
- **File**: `pages/IMSDashboard.tsx`
- **Purpose**: Integrated Management System health score across ISO 9001/14001/45001/27001
- **Persona(s)**: P3 Risk Manager, P5 Executive
- **Layout Pattern**: Dashboard — KPI tiles + compliance matrix
- **Key Components**: `Card`, `Badge`, `ProgressBar`, `Button`
- **States Covered**:
  - [S] Loading
  - [S] Populated
  - [P] Error (partial)
  - [ ] Empty state
- **Story Coverage**: None
- **Navigation**: From sidebar "Enterprise > IMS Dashboard"; links to `/compliance`

---

### 3. Safety & Incident Management

#### 3.1 Incidents List

- **Route**: `/incidents`
- **File**: `pages/Incidents.tsx`
- **Purpose**: Browse, search, and create incident reports
- **Persona(s)**: P2, P3 (view/manage); P4 (admin oversight)
- **Layout Pattern**: List-Detail (table with row click → detail)
- **Key Components**: `Input`, `Button`, `EmptyState`, `TableSkeleton`, `Card`, `CardContent`, `Badge`, `Dialog`, `DialogContent`, `DialogHeader`, `DialogTitle`, `DialogFooter`, `DialogDescription`, `Select`, `SelectContent`, `SelectItem`, `SelectTrigger`, `SelectValue`, `Textarea`
- **States Covered**:
  - [S] Loading (`TableSkeleton` with 6 rows × 6 columns)
  - [S] Populated (filterable table with severity/status badges)
  - [S] Empty (`EmptyState` component with "No incidents found" + create CTA)
  - [S] Error (load error banner; create error inline in dialog)
  - [ ] Permission-denied
- **Story Coverage**: None — needs `IncidentsList.stories.tsx`
- **UX Patterns**: Client-side search with `useDeferredValue`; create modal dialog; offline-aware creation (`queueForSync`); keyboard-navigable rows (`role="button"`, `tabIndex`, `onKeyDown`); animated row entrance
- **Navigation**: Sidebar "Core > Incidents"; rows navigate to `/incidents/:id`; create modal inline
- **Accessibility**: Table headers; `role="button"` and `tabIndex={0}` on rows; `aria-required` on form fields; search input with icon

#### 3.2 Incident Detail

- **Route**: `/incidents/:id`
- **File**: `pages/IncidentDetail.tsx`
- **Purpose**: Full incident record — timeline, running sheet, actions, investigation, CAPA linkage
- **Persona(s)**: P2, P3
- **Layout Pattern**: Detail — tabbed content with sidebar rail
- **Key Components**: `Breadcrumbs`, `CardSkeleton`, `Button`, `Card`, `CardContent`, `CardHeader`, `CardTitle`, `Badge`, `Textarea`, `Input`, `Dialog`/`DialogContent`/`DialogHeader`/`DialogTitle`/`DialogFooter`/`DialogDescription`, `Select`/`SelectContent`/`SelectItem`/`SelectTrigger`/`SelectValue`, `Tabs`/`TabsContent`/`TabsList`/`TabsTrigger`, `CaseSummaryRail`, `SubmissionSections`
- **States Covered**:
  - [S] Loading (skeleton)
  - [S] Populated (full record with tabs: Details, Running Sheet, Actions, Investigation)
  - [S] Error (load failure, update failure with toast)
  - [S] Edit mode (inline field editing with save/cancel)
  - [ ] Not-found state for invalid IDs
  - [ ] Permission-denied
- **Story Coverage**: None
- **UX Patterns**: Breadcrumb trail; inline editing with pencil icon toggle; status update via select; running sheet entries; investigation linking; action creation from incident; back navigation
- **Navigation**: From `/incidents` row click; breadcrumbs back to list; cross-links to `/investigations/:id`
- **Accessibility**: Breadcrumb nav; tabbed interface using Radix Tabs; labelled form fields

#### 3.3 Near Misses List

- **Route**: `/near-misses`
- **File**: `pages/NearMisses.tsx`
- **Purpose**: Browse and create near-miss reports
- **Persona(s)**: P2, P3
- **Layout Pattern**: List with create dialog
- **Key Components**: `Input`, `Button`, `EmptyState`, `TableSkeleton`, `Card`, `Badge`, `Dialog`, `Select`, `Textarea`
- **States Covered**:
  - [S] Loading
  - [S] Populated
  - [S] Empty
  - [S] Error
- **Story Coverage**: None
- **Navigation**: Sidebar "Core > Near Misses"; rows → `/near-misses/:id`

#### 3.4 Near Miss Detail

- **Route**: `/near-misses/:id`
- **File**: `pages/NearMissDetail.tsx`
- **Purpose**: Full near-miss record with investigation linkage
- **Persona(s)**: P2, P3
- **Layout Pattern**: Detail — tabbed
- **Key Components**: `Breadcrumbs`, `Card`, `Badge`, `Tabs`, `Dialog`, `Button`
- **States Covered**:
  - [S] Loading
  - [S] Populated
  - [S] Error
  - [ ] Not-found
- **Story Coverage**: None

#### 3.5 RTAs List

- **Route**: `/rtas`
- **File**: `pages/RTAs.tsx`
- **Purpose**: Road traffic collision list and creation
- **Persona(s)**: P2, P3
- **Layout Pattern**: List with create dialog
- **Key Components**: `Input`, `Button`, `EmptyState`, `TableSkeleton`, `Card`, `Badge`, `Dialog`, `Select`
- **States Covered**:
  - [S] Loading
  - [S] Populated
  - [S] Empty
  - [S] Error
- **Story Coverage**: None
- **Navigation**: Sidebar "Core > RTAs"; rows → `/rtas/:id`

#### 3.6 RTA Detail

- **Route**: `/rtas/:id`
- **File**: `pages/RTADetail.tsx`
- **Purpose**: Full RTA record with vehicle and person details
- **Persona(s)**: P2, P3
- **Layout Pattern**: Detail — tabbed
- **States Covered**:
  - [S] Loading
  - [S] Populated
  - [S] Error
  - [ ] Not-found
- **Story Coverage**: None

#### 3.7 Complaints List

- **Route**: `/complaints`
- **File**: `pages/Complaints.tsx`
- **Purpose**: External complaint tracking
- **Persona(s)**: P2, P3
- **Layout Pattern**: List with create dialog
- **Key Components**: `Input`, `Button`, `EmptyState`, `TableSkeleton`, `Card`, `Badge`, `Dialog`, `Select`, `Textarea`
- **States Covered**:
  - [S] Loading
  - [S] Populated
  - [S] Empty
  - [S] Error
- **Story Coverage**: None
- **Navigation**: Sidebar "Core > Complaints"; rows → `/complaints/:id`

#### 3.8 Complaint Detail

- **Route**: `/complaints/:id`
- **File**: `pages/ComplaintDetail.tsx`
- **Purpose**: Full complaint record with resolution tracking
- **Persona(s)**: P2, P3
- **Layout Pattern**: Detail — tabbed
- **States Covered**:
  - [S] Loading
  - [S] Populated
  - [S] Error
  - [ ] Not-found
- **Story Coverage**: None

#### 3.9 Vehicle Checklists

- **Route**: `/vehicle-checklists`
- **File**: `pages/VehicleChecklists.tsx`
- **Purpose**: Pre-use vehicle inspection records
- **Persona(s)**: P2 (field), P3 (oversight)
- **Layout Pattern**: List
- **States Covered**:
  - [S] Loading
  - [S] Populated
  - [S] Empty
  - [ ] Error
- **Story Coverage**: None

---

### 4. Governance — Audits & Compliance

#### 4.1 Audit Management

- **Route**: `/audits`
- **File**: `pages/Audits.tsx`
- **Purpose**: Manage internal and external audit runs — schedule, execute, track findings
- **Persona(s)**: P2 Quality Auditor (primary), P3 Risk Manager, P5 Executive (view)
- **Layout Pattern**: Multi-view — Kanban board / Table list / Findings list (toggle)
- **Key Components**: `Button`, `Input`, `Card`, `CardContent`, `Badge`, `Dialog`/`DialogContent`/`DialogDescription`/`DialogHeader`/`DialogTitle`/`DialogFooter`, `LoadingSkeleton`, `EmptyState`, `ToastContainer`
- **States Covered**:
  - [S] Loading (`LoadingSkeleton variant="table"`)
  - [S] Populated (Kanban with 4 columns: Scheduled → In Progress → Pending Review → Completed)
  - [S] Empty (per-column empty message; list-view `EmptyState`)
  - [S] Error (load error banner with retry; form error in dialog)
  - [S] Success feedback (success message with icon after create)
  - [ ] Permission-denied
- **Story Coverage**: None — highest priority for page-level stories
- **UX Patterns**: View mode toggle (Board/List/Findings); search filter; kanban column counters; stat summary cards (total/in-progress/completed/avg-score/open-findings); schedule modal with template selector and version picker; import modal for external audits with file upload and OCR queue; `aria-pressed` on view toggle; keyboard-navigable cards
- **Navigation**: Sidebar "Governance > Audits"; cards/rows → `/audits/:id/execute` or `/audits/:id/import-review`; template selection links to `/audit-templates`
- **Accessibility**: `role="button"` and `tabIndex` on cards/rows; `aria-pressed` on toggle buttons; labelled form fields; `sr-only` actions column header

#### 4.2 Audit Template Library

- **Route**: `/audit-templates`
- **File**: `pages/AuditTemplateLibrary.tsx`
- **Purpose**: Browse, search, and manage published audit templates
- **Persona(s)**: P2, P4
- **Layout Pattern**: List with cards
- **Key Components**: `Button`, `Input`, `Card`, `Badge`, `EmptyState`
- **States Covered**:
  - [S] Loading
  - [S] Populated
  - [S] Empty
  - [S] Error
- **Story Coverage**: None
- **Navigation**: Sidebar "Governance > Audit Builder"; "New Template" → `/audit-templates/new`; card click → `/audit-templates/:id/edit`

#### 4.3 Audit Template Builder

- **Route**: `/audit-templates/new`, `/audit-templates/:templateId/edit`
- **File**: `pages/AuditTemplateBuilder.tsx`, with sub-components in `pages/audit-builder/` (`SectionEditor.tsx`, `QuestionEditor.tsx`, `TemplateHeader.tsx`, `PublishDialog.tsx`)
- **Purpose**: Build and publish multi-section audit templates with scoring, question types, and ISO clause tagging
- **Persona(s)**: P2, P4
- **Layout Pattern**: Wizard / Builder — multi-panel editor
- **Key Components**: `Button`, `Input`, `Card`, `Dialog`, `Badge`, `Select`, `Textarea`, `Tabs`
- **States Covered**:
  - [S] Loading (existing template load)
  - [S] Populated (sections and questions tree)
  - [S] Create mode (blank template)
  - [S] Edit mode (pre-populated from API)
  - [S] Publish confirmation dialog
  - [S] Error (save/publish failures)
  - [ ] Unsaved changes warning
- **Story Coverage**: None
- **Navigation**: From `/audit-templates` library; publish returns to library

#### 4.4 Audit Execution

- **Route**: `/audits/:auditId/execute`
- **File**: `pages/AuditExecution.tsx`
- **Purpose**: Step-by-step audit form — answer questions, capture evidence, score sections
- **Persona(s)**: P2 Quality Auditor
- **Layout Pattern**: Form / Wizard — section-by-section navigation
- **Key Components**: `Button`, `Card`, `Badge`, `Select`, `Textarea`, `Input`, `ProgressBar`, `Dialog`
- **States Covered**:
  - [S] Loading
  - [S] Populated (active audit with progress)
  - [S] Section complete indicators
  - [S] Error (save failure)
  - [ ] Offline mode indicator
  - [ ] Auto-save feedback
- **Story Coverage**: None — critical for P2 journey
- **UX Patterns**: Section navigation sidebar; progress indicator; question-by-question flow; evidence attachment; finding creation inline; score calculation; auto-save
- **Navigation**: From `/audits` board/list; section sidebar navigation within page; "Complete Audit" → back to `/audits`

#### 4.5 Audit Import Review

- **Route**: `/audits/:auditId/import-review`
- **File**: `pages/AuditImportReview.tsx`
- **Purpose**: Review and validate externally imported audit data (OCR/AI-extracted)
- **Persona(s)**: P2
- **Layout Pattern**: Review form with source document comparison
- **States Covered**:
  - [S] Loading
  - [S] Populated (mapped findings for review)
  - [S] Error (OCR queue failure)
  - [ ] Empty (no extracted data)
- **Story Coverage**: None

#### 4.6 Investigations List

- **Route**: `/investigations`
- **File**: `pages/Investigations.tsx`
- **Purpose**: Root-cause investigation tracking
- **Persona(s)**: P2, P3
- **Layout Pattern**: List with create dialog
- **Key Components**: `Button`, `Input`, `Card`, `Badge`, `EmptyState`, `Dialog`, `Select`
- **States Covered**:
  - [S] Loading
  - [S] Populated
  - [S] Empty
  - [S] Error
- **Story Coverage**: None
- **Navigation**: Sidebar "Governance > Investigations"; rows → `/investigations/:id`

#### 4.7 Investigation Detail

- **Route**: `/investigations/:id`
- **File**: `pages/InvestigationDetail.tsx`, with sub-components in `pages/investigation/` (`InvestigationHeader.tsx`, `InvestigationTimeline.tsx`, `InvestigationComments.tsx`, `InvestigationActions.tsx`, `InvestigationEvidence.tsx`)
- **Purpose**: Full investigation workspace — timeline, root cause, evidence, actions, comments
- **Persona(s)**: P2, P3
- **Layout Pattern**: Detail — multi-panel tabbed with timeline
- **Key Components**: `Breadcrumbs`, `Card`, `Badge`, `Tabs`, `Dialog`, `Button`, `Textarea`, `Input`
- **States Covered**:
  - [S] Loading
  - [S] Populated (header + tabs: Timeline, Evidence, Actions, Comments)
  - [S] Error
  - [ ] Not-found
- **Story Coverage**: None

#### 4.8 Standards Library

- **Route**: `/standards`
- **File**: `pages/Standards.tsx`
- **Purpose**: Browse ISO standards and clauses
- **Persona(s)**: P2, P3
- **Layout Pattern**: Searchable list / tree
- **States Covered**:
  - [S] Loading
  - [S] Populated
  - [S] Empty
  - [ ] Error
- **Story Coverage**: None

#### 4.9 Actions Tracker

- **Route**: `/actions`
- **File**: `pages/Actions.tsx`
- **Purpose**: Unified corrective/preventive action tracker across all modules
- **Persona(s)**: P2, P3, P4
- **Layout Pattern**: List with filters and create dialog
- **Key Components**: `Button`, `Input`, `Card`, `Badge`, `EmptyState`, `Dialog`, `Select`
- **States Covered**:
  - [S] Loading
  - [S] Populated (filterable by status, priority, assignee)
  - [S] Empty
  - [S] Error
- **Story Coverage**: None
- **Navigation**: Sidebar "Governance > Actions"; also linked from Dashboard "Overdue Actions" card

#### 4.10 Compliance Evidence

- **Route**: `/compliance`
- **File**: `pages/ComplianceEvidence.tsx`
- **Purpose**: ISO clause mapping with evidence linking and gap analysis
- **Persona(s)**: P2, P3, P5
- **Layout Pattern**: Matrix / Grid
- **States Covered**:
  - [S] Loading
  - [S] Populated
  - [P] Empty
  - [S] Error
- **Story Coverage**: None

#### 4.11 UVDB Audits

- **Route**: `/uvdb`
- **File**: `pages/UVDBAudits.tsx`
- **Purpose**: Achilles UVDB B2 audit protocol management
- **Persona(s)**: P2
- **Layout Pattern**: List
- **States Covered**:
  - [S] Loading
  - [S] Populated
  - [S] Empty
  - [ ] Error
- **Story Coverage**: None

#### 4.12 Planet Mark

- **Route**: `/planet-mark`
- **File**: `pages/PlanetMark.tsx`
- **Purpose**: Carbon management and Planet Mark certification tracking
- **Persona(s)**: P3, P5
- **Layout Pattern**: Dashboard + List
- **States Covered**:
  - [S] Loading
  - [S] Populated
  - [ ] Empty
  - [ ] Error
- **Story Coverage**: None

#### 4.13 Customer Audits

- **Route**: `/customer-audits`
- **File**: `pages/CustomerAudits.tsx`
- **Purpose**: Track customer-initiated audit programmes
- **Persona(s)**: P2, P3
- **Layout Pattern**: List
- **States Covered**:
  - [S] Loading
  - [S] Populated
  - [S] Empty
  - [ ] Error
- **Story Coverage**: None

#### 4.14 Digital Signatures

- **Route**: `/signatures`
- **File**: `pages/DigitalSignatures.tsx`
- **Purpose**: Digital signature workflows for document approval
- **Persona(s)**: P2, P3, P4
- **Layout Pattern**: List
- **States Covered**:
  - [S] Loading
  - [S] Populated
  - [S] Empty
  - [ ] Error
- **Story Coverage**: None

---

### 5. Library & Documents

#### 5.1 Documents

- **Route**: `/documents`
- **File**: `pages/Documents.tsx`
- **Purpose**: AI-powered document library with search and upload
- **Persona(s)**: P2, P3, P4
- **Layout Pattern**: List with search and upload
- **Key Components**: `Input`, `Button`, `Card`, `Badge`, `EmptyState`, `Dialog`
- **States Covered**:
  - [S] Loading
  - [S] Populated
  - [S] Empty
  - [S] Error
- **Story Coverage**: None

#### 5.2 Policies

- **Route**: `/policies`
- **File**: `pages/Policies.tsx`
- **Purpose**: Policy library with version control
- **Persona(s)**: P2, P3
- **Layout Pattern**: List
- **States Covered**:
  - [S] Loading
  - [S] Populated
  - [S] Empty
  - [ ] Error
- **Story Coverage**: None

#### 5.3 Operational Risks

- **Route**: `/risks`
- **File**: `pages/Risks.tsx`
- **Purpose**: Operational risk register (distinct from enterprise `/risk-register`)
- **Persona(s)**: P3
- **Layout Pattern**: List with heatmap
- **States Covered**:
  - [S] Loading
  - [S] Populated
  - [S] Empty
  - [S] Error
- **Story Coverage**: None

---

### 6. Enterprise

#### 6.1 Enterprise Risk Register

- **Route**: `/risk-register`
- **File**: `pages/RiskRegister.tsx`
- **Purpose**: Enterprise-level risk register with 5×5 heatmap, bow-tie analysis, KRI monitoring, risk appetite thresholds
- **Persona(s)**: P3 Risk Manager (primary), P5 Executive
- **Layout Pattern**: Register (table) + Heatmap (matrix) + Detail panel
- **Key Components**: `Button`, `Card`, `CardContent`, `Badge`, custom heatmap matrix, filter panel
- **States Covered**:
  - [S] Loading
  - [S] Populated (risk table + heatmap + stats)
  - [S] Empty
  - [S] Error
  - [S] Detail view (expand risk)
  - [S] Create/edit dialog
  - [ ] Permission-denied
- **Story Coverage**: None — high priority for P3 journey
- **UX Patterns**: View toggle (Register/Heatmap); filter by category/department/status; risk level colour coding; appetite threshold indicators; export button; linked audits/actions references
- **Navigation**: Sidebar "Enterprise > Risk Register"; linked from Dashboard "High Risks" card

#### 6.2 AI Intelligence

- **Route**: `/ai-intelligence`
- **File**: `pages/AIIntelligence.tsx`
- **Purpose**: AI-driven anomaly detection, trend predictions, natural language analysis
- **Persona(s)**: P3, P5
- **Layout Pattern**: Dashboard with insight cards
- **States Covered**:
  - [S] Loading
  - [S] Populated
  - [P] Empty
  - [ ] Error
- **Story Coverage**: None

---

### 7. Analytics & Reporting

#### 7.1 Analytics Overview

- **Route**: `/analytics`
- **File**: `pages/Analytics.tsx`
- **Purpose**: KPI overview with trend charts
- **Persona(s)**: P3, P5
- **Layout Pattern**: Dashboard
- **States Covered**:
  - [S] Loading
  - [S] Populated
  - [ ] Empty
  - [ ] Error
- **Story Coverage**: None

#### 7.2 Advanced Analytics

- **Route**: `/analytics/advanced`
- **File**: `pages/AdvancedAnalytics.tsx`
- **Purpose**: Deep-dive analytics with custom date ranges, drill-down, and comparisons
- **Persona(s)**: P3, P5
- **Layout Pattern**: Dashboard with configurable widgets
- **States Covered**:
  - [S] Loading
  - [S] Populated
  - [ ] Empty
  - [ ] Error
- **Story Coverage**: None

#### 7.3 Dashboard Builder

- **Route**: `/analytics/dashboards`
- **File**: `pages/DashboardBuilder.tsx`
- **Purpose**: Build custom dashboards with drag-and-drop widget placement
- **Persona(s)**: P3, P4, P5
- **Layout Pattern**: Builder / Canvas
- **States Covered**:
  - [S] Loading
  - [S] Populated
  - [S] Empty (blank canvas)
  - [ ] Error
- **Story Coverage**: None

#### 7.4 Report Generator

- **Route**: `/analytics/reports`
- **File**: `pages/ReportGenerator.tsx`
- **Purpose**: Generate and export management reports (PDF/Excel)
- **Persona(s)**: P3, P5
- **Layout Pattern**: Form → preview
- **States Covered**:
  - [S] Loading
  - [S] Populated
  - [ ] Error
- **Story Coverage**: None

#### 7.5 Calendar View

- **Route**: `/calendar`
- **File**: `pages/CalendarView.tsx`
- **Purpose**: Cross-module calendar showing audits, actions, reviews, training
- **Persona(s)**: P2, P3, P4
- **Layout Pattern**: Calendar grid
- **States Covered**:
  - [S] Loading
  - [S] Populated
  - [S] Empty (no events)
  - [ ] Error
- **Story Coverage**: None

#### 7.6 Export Center

- **Route**: `/exports`
- **File**: `pages/ExportCenter.tsx`
- **Purpose**: Bulk data export in CSV/Excel/PDF
- **Persona(s)**: P3, P4
- **Layout Pattern**: List of available exports
- **States Covered**:
  - [S] Loading
  - [S] Populated
  - [ ] Error
- **Story Coverage**: None

---

### 8. Automation

#### 8.1 Workflow Center

- **Route**: `/workflows`
- **File**: `pages/WorkflowCenter.tsx`
- **Purpose**: Approval workflows, escalation rules, SLA configuration
- **Persona(s)**: P4 System Admin
- **Layout Pattern**: List + config panels
- **States Covered**:
  - [S] Loading
  - [S] Populated
  - [S] Empty
  - [S] Error
- **Story Coverage**: None

#### 8.2 Compliance Automation

- **Route**: `/compliance-automation`
- **File**: `pages/ComplianceAutomation.tsx`
- **Purpose**: Automated regulatory updates, certificate renewals, RIDDOR reporting
- **Persona(s)**: P2, P3, P4
- **Layout Pattern**: Dashboard + List
- **States Covered**:
  - [S] Loading
  - [S] Populated
  - [ ] Empty
  - [ ] Error
- **Story Coverage**: None

---

### 9. Workforce Development

> All workforce routes are gated by `RequireRole allowed={['admin', 'supervisor']}`.

#### 9.1 Assessments List

- **Route**: `/workforce/assessments`
- **File**: `pages/workforce/Assessments.tsx`
- **Purpose**: Job competency assessment management
- **Persona(s)**: P4 (admin), P2 (supervisor)
- **Layout Pattern**: List with create action
- **States Covered**:
  - [S] Loading
  - [S] Populated
  - [S] Empty
  - [ ] Error
- **Story Coverage**: None
- **Navigation**: Sidebar "Workforce > Assessments"; "New" → `/workforce/assessments/new`; row → `/workforce/assessments/:id/execute`

#### 9.2 Assessment Create

- **Route**: `/workforce/assessments/new`
- **File**: `pages/workforce/AssessmentCreate.tsx`
- **Purpose**: Create new competency assessment
- **Layout Pattern**: Form
- **States Covered**:
  - [S] Default form
  - [S] Submitting
  - [S] Error
- **Story Coverage**: None

#### 9.3 Assessment Execution

- **Route**: `/workforce/assessments/:id/execute`
- **File**: `pages/workforce/AssessmentExecution.tsx`
- **Purpose**: Execute assessment — scoring criteria, evidence, sign-off
- **Layout Pattern**: Form / Wizard
- **States Covered**:
  - [S] Loading
  - [S] Populated
  - [S] Error
- **Story Coverage**: None

#### 9.4 Training List

- **Route**: `/workforce/training`
- **File**: `pages/workforce/Training.tsx`
- **Purpose**: Site induction and training record management
- **Layout Pattern**: List
- **States Covered**:
  - [S] Loading
  - [S] Populated
  - [S] Empty
  - [ ] Error
- **Story Coverage**: None

#### 9.5 Induction Create

- **Route**: `/workforce/training/new`
- **File**: `pages/workforce/InductionCreate.tsx`
- **Purpose**: Create new site induction
- **Layout Pattern**: Form
- **States Covered**:
  - [S] Default form
  - [S] Submitting
  - [S] Error
- **Story Coverage**: None

#### 9.6 Training Execution

- **Route**: `/workforce/training/:id/execute`
- **File**: `pages/workforce/TrainingExecution.tsx`
- **Purpose**: Execute training session with attendee tracking
- **Layout Pattern**: Form / Wizard
- **States Covered**:
  - [S] Loading
  - [S] Populated
  - [S] Error
- **Story Coverage**: None

#### 9.7 Engineers List

- **Route**: `/workforce/engineers`
- **File**: `pages/workforce/Engineers.tsx`
- **Purpose**: Engineer directory with competency status
- **Layout Pattern**: List / Grid
- **States Covered**:
  - [S] Loading
  - [S] Populated
  - [S] Empty
  - [ ] Error
- **Story Coverage**: None
- **Navigation**: Sidebar "Workforce > Engineers"; card/row → `/workforce/engineers/:id`

#### 9.8 Engineer Profile

- **Route**: `/workforce/engineers/:id`
- **File**: `pages/workforce/EngineerProfile.tsx`
- **Purpose**: Individual engineer competency profile — qualifications, assessments, training history
- **Layout Pattern**: Profile / Detail — header + tabbed content
- **States Covered**:
  - [S] Loading
  - [S] Populated
  - [S] Error
  - [ ] Not-found
- **Story Coverage**: None

#### 9.9 Workforce Calendar

- **Route**: `/workforce/calendar`
- **File**: `pages/workforce/Calendar.tsx`
- **Purpose**: Training and assessment scheduling calendar
- **Layout Pattern**: Calendar grid
- **States Covered**:
  - [S] Loading
  - [S] Populated
  - [S] Empty
  - [ ] Error
- **Story Coverage**: None

#### 9.10 Competency Dashboard

- **Route**: `/workforce/dashboard`
- **File**: `pages/workforce/CompetencyDashboard.tsx`
- **Purpose**: Team competency matrix and expiry tracking
- **Layout Pattern**: Dashboard with matrix
- **States Covered**:
  - [S] Loading
  - [S] Populated
  - [ ] Empty
  - [ ] Error
- **Story Coverage**: None

---

### 10. Admin & Configuration

> All admin routes are gated by `RequireRole allowed={['admin']}` or `['admin', 'manager']`.

#### 10.1 Admin Dashboard

- **Route**: `/admin`
- **File**: `pages/admin/AdminDashboard.tsx`
- **Purpose**: Admin landing with system health, user counts, feature flags
- **Persona(s)**: P4
- **Layout Pattern**: Dashboard
- **States Covered**:
  - [S] Loading
  - [S] Populated
  - [ ] Error
- **Story Coverage**: None

#### 10.2 Forms List

- **Route**: `/admin/forms`
- **File**: `pages/admin/FormsList.tsx`
- **Purpose**: Manage dynamic form templates (incident, complaint, etc.)
- **Layout Pattern**: List
- **States Covered**:
  - [S] Loading
  - [S] Populated
  - [S] Empty
  - [ ] Error
- **Story Coverage**: None
- **Navigation**: "New" → `/admin/forms/new`; row → `/admin/forms/:id`

#### 10.3 Form Builder

- **Route**: `/admin/forms/new`, `/admin/forms/:templateId`
- **File**: `pages/admin/FormBuilder.tsx`
- **Purpose**: Visual form builder with field types, validation rules, conditional logic
- **Layout Pattern**: Builder / Canvas
- **States Covered**:
  - [S] Loading
  - [S] Create mode
  - [S] Edit mode
  - [S] Error
  - [ ] Unsaved changes warning
- **Story Coverage**: None

#### 10.4 Contracts Management

- **Route**: `/admin/contracts`
- **File**: `pages/admin/ContractsManagement.tsx`
- **Purpose**: Manage service contracts and renewal tracking
- **Layout Pattern**: List
- **States Covered**:
  - [S] Loading
  - [S] Populated
  - [ ] Error
- **Story Coverage**: None

#### 10.5 System Settings

- **Route**: `/admin/settings`
- **File**: `pages/admin/SystemSettings.tsx`
- **Purpose**: Global platform configuration — branding, features, integrations
- **Persona(s)**: P4 (admin-only)
- **Layout Pattern**: Form with sections
- **States Covered**:
  - [S] Loading
  - [S] Populated
  - [S] Save success
  - [ ] Error
- **Story Coverage**: None

#### 10.6 User Management

- **Route**: `/admin/users`
- **File**: `pages/admin/UserManagement.tsx`
- **Purpose**: User CRUD, role assignment, deactivation
- **Persona(s)**: P4 (superuser-only, feature-flagged)
- **Layout Pattern**: List with create/edit dialog
- **Key Components**: `Button`, `Input`, `Card`, `Badge`, `Dialog`, `Select`
- **States Covered**:
  - [S] Loading
  - [S] Populated
  - [S] Empty
  - [S] Error
  - [S] Create/edit dialogs
  - [ ] Deactivation confirmation
- **Story Coverage**: None
- **UX Patterns**: Feature-flag gated (`admin_user_management`); requires superuser; search/filter by role

#### 10.7 Lookup Tables

- **Route**: `/admin/lookups`
- **File**: `pages/admin/LookupTables.tsx`
- **Purpose**: Manage reference data — departments, locations, categories, severity levels
- **Persona(s)**: P4
- **Layout Pattern**: List with inline editing
- **States Covered**:
  - [S] Loading
  - [S] Populated
  - [S] Error
- **Story Coverage**: None

#### 10.8 Notification Settings

- **Route**: `/admin/notifications`
- **File**: `pages/admin/NotificationSettings.tsx`
- **Purpose**: Configure notification rules, channels, and escalation
- **Persona(s)**: P4
- **Layout Pattern**: Form with sections
- **States Covered**:
  - [S] Loading
  - [S] Populated
  - [ ] Error
- **Story Coverage**: None

#### 10.9 Audit Trail Viewer

- **Route**: `/audit-trail`
- **File**: `pages/AuditTrail.tsx` / `pages/AuditTrailViewer.tsx`
- **Purpose**: Immutable audit log viewer — who changed what, when
- **Persona(s)**: P4, P3
- **Layout Pattern**: List with filters
- **States Covered**:
  - [S] Loading
  - [S] Populated
  - [S] Empty
  - [ ] Error
- **Story Coverage**: None

---

### 11. Tools & Cross-cutting

#### 11.1 Global Search

- **Route**: `/search`
- **File**: `pages/GlobalSearch.tsx`
- **Purpose**: Cross-module search with filters by module, status, date range
- **Persona(s)**: All authenticated personas
- **Layout Pattern**: Search results with facets
- **Key Components**: `Input`, `Button`, `Card`, `CardContent`, `Badge`
- **States Covered**:
  - [S] Default (empty search with suggestions and history)
  - [S] Searching (loading spinner)
  - [S] Results populated (grouped by module with type icons)
  - [S] No results
  - [S] Error (toast notification)
  - [S] Search history
- **Story Coverage**: None
- **UX Patterns**: Auto-focus input; keyboard shortcut hint (Cmd+K from Layout); module filter toggles; status filter chips; date range filter; search history with recent terms; result count; keyboard navigation; results grouped by type
- **Navigation**: Triggered by Cmd+K or search bar in top header; results link to individual records
- **Accessibility**: `aria-label` on filter buttons; `role="listbox"` on suggestions; keyboard event handlers

#### 11.2 Notification Centre

- **Route**: `/notifications`
- **File**: `pages/Notifications.tsx`
- **Purpose**: In-app notification list with read/unread management
- **Persona(s)**: All authenticated personas
- **Layout Pattern**: List with mark-read/dismiss actions
- **States Covered**:
  - [S] Loading
  - [S] Populated
  - [S] Empty
  - [ ] Error
- **Story Coverage**: None
- **Navigation**: Bell icon in header (with unread badge); sidebar via Admin section

#### 11.3 Not Found (404)

- **Route**: `/*` (catch-all)
- **File**: `pages/NotFound.tsx`
- **Purpose**: Friendly 404 page with navigation recovery
- **Persona(s)**: All
- **Layout Pattern**: Centred message
- **Key Components**: Custom (no shared UI primitives used)
- **States Covered**:
  - [S] Default (404 display with "Go back" and "Go to Dashboard" buttons)
- **Story Coverage**: None
- **Accessibility**: Heading hierarchy; button focus management

---

### 12. Employee Portal

> Portal uses a separate `PortalLayout` shell — mobile-first, no sidebar, `max-w-lg` constrained.
> Auth via `PortalAuthProvider` (SSO-based).

#### 12.1 Portal Login

- **Route**: `/portal/login`
- **File**: `pages/PortalLogin.tsx`
- **Purpose**: SSO-based authentication for field workers
- **Persona(s)**: P1 Field Reporter
- **Layout Pattern**: Centred card (mobile-first)
- **States Covered**:
  - [S] Default
  - [S] Loading
  - [S] Error
- **Story Coverage**: None

#### 12.2 Portal Home

- **Route**: `/portal`
- **File**: `pages/Portal.tsx`
- **Purpose**: Mobile-friendly landing with three actions: Submit Report, Track Report, Help
- **Persona(s)**: P1 Field Reporter
- **Layout Pattern**: Action cards (mobile-first)
- **Key Components**: `Card`, `ThemeToggle`, custom action cards
- **States Covered**:
  - [S] Default (user welcome + 3 action cards)
  - [ ] Offline indicator
- **Story Coverage**: None — important for P1 mobile journey
- **UX Patterns**: User welcome with name/email; gradient brand icon; chevron affordance; "Optimized for mobile" badge; admin login footer link; logout button
- **Navigation**: Three primary actions → `/portal/report`, `/portal/track`, `/portal/help`; admin crossover → `/login`
- **Accessibility**: `data-testid` attributes; `useLiveAnnouncer` for "Employee portal loaded" announcement; semantic headings

#### 12.3 Portal Report Type Picker

- **Route**: `/portal/report`
- **File**: `pages/PortalReport.tsx`
- **Purpose**: Choose report type — Incident, Near Miss, Complaint, RTA
- **Persona(s)**: P1
- **Layout Pattern**: Card selection grid
- **States Covered**:
  - [S] Default (type selection)
- **Story Coverage**: None
- **Navigation**: From Portal Home; each type → `/portal/report/<type>`

#### 12.4 Portal Dynamic Forms

- **Routes**: `/portal/report/incident`, `/portal/report/near-miss`, `/portal/report/complaint`
- **File**: `pages/PortalDynamicForm.tsx`
- **Purpose**: Dynamic form driven by admin-configured form templates
- **Persona(s)**: P1
- **Layout Pattern**: Multi-step form (progressive disclosure)
- **States Covered**:
  - [S] Loading (template fetch)
  - [S] Form active
  - [S] Submitting
  - [S] Success (confirmation with reference number)
  - [S] Error
  - [ ] Offline queue
- **Story Coverage**: None — critical for P1 journey
- **UX Patterns**: Step-by-step wizard; field validation; auto-save draft; evidence photo upload; GPS location auto-fill

#### 12.5 Portal RTA Form

- **Route**: `/portal/report/rta`
- **File**: `pages/PortalRTAForm.tsx`
- **Purpose**: Dedicated RTA form with vehicle/person details
- **Persona(s)**: P1
- **Layout Pattern**: Multi-section form
- **States Covered**:
  - [S] Form active
  - [S] Submitting
  - [S] Success
  - [S] Error
- **Story Coverage**: None

#### 12.6 Portal Status Tracker

- **Route**: `/portal/track`, `/portal/track/:referenceNumber`
- **File**: `pages/PortalTrack.tsx`
- **Purpose**: Check report status by reference number
- **Persona(s)**: P1
- **Layout Pattern**: Search → result detail
- **States Covered**:
  - [S] Default (search input)
  - [S] Found (status timeline)
  - [S] Not found
  - [S] Error
- **Story Coverage**: None
- **Navigation**: From Portal Home; deep-link with reference number

#### 12.7 Portal Help

- **Route**: `/portal/help`
- **File**: `pages/PortalHelp.tsx`
- **Purpose**: FAQs and contact information
- **Persona(s)**: P1
- **Layout Pattern**: Static content / FAQ accordion
- **States Covered**:
  - [S] Default
- **Story Coverage**: None

#### 12.8 Legacy Portal Forms

- **Routes**: `/portal/report/incident-legacy`, `/portal/report/near-miss-static`
- **Files**: `pages/PortalIncidentForm.tsx`, `pages/PortalNearMissForm.tsx`
- **Purpose**: Hardcoded legacy forms (superseded by dynamic forms)
- **Story Coverage**: None — low priority (deprecated)

---

## Screen-to-Screen Flow Coverage

### Flow 1: Incident Lifecycle (P1 → P2 → P3)

```
P1: /portal → /portal/report → /portal/report/incident → Submit
                                                            │
P2: /incidents ← notification ←────────────────────────────┘
      │
      └→ /incidents/:id (investigate, update status)
           │
           ├→ /investigations (create investigation from incident)
           │     └→ /investigations/:id (root cause, timeline, actions)
           │
           └→ /actions (create CAPA from finding)
                └→ /actions (track to closure)
```

**Coverage**: All screens exist. Cross-linking between incident detail and investigation detail is implemented. Missing: push notifications to P1 for status updates.

### Flow 2: Audit Lifecycle (P2)

```
/audit-templates → /audit-templates/new (build template)
                     └→ Publish
                          │
/audits → Schedule audit (modal) → /audits/:id/execute
            │                          │
            │                          └→ Record findings → Raise CAPA → /actions
            │
            └→ Import external (modal) → /audits/:id/import-review
                                            └→ OCR + review → promote findings
```

**Coverage**: Complete flow is implemented. Template versioning and publish workflow are in place. External import with OCR queue is functional.

### Flow 3: Risk Management (P3)

```
/risk-register → Create risk (dialog) → Edit risk details
     │                                        │
     ├→ Heatmap view ←───────────────────────┘
     │
     ├→ /actions (linked mitigation actions)
     │
     └→ /analytics/advanced (trend analysis)
```

**Coverage**: Register and heatmap views exist. Action linking is implemented. KRI dashboard is partially covered via `/ims`.

### Flow 4: Admin Configuration (P4)

```
/admin → /admin/users (manage users)
   │  → /admin/forms (manage form templates)
   │       └→ /admin/forms/new or /admin/forms/:id
   │  → /admin/lookups (reference data)
   │  → /admin/settings (system config)
   │  → /admin/notifications (alert rules)
   │  → /admin/contracts (service contracts)
   │
   └→ /audit-trail (audit log verification)
```

**Coverage**: All screens exist. Missing: bulk user import, configuration change impact preview.

### Flow 5: Executive Review (P5)

```
/dashboard → Quick action cards → /audits, /analytics, /compliance, /incidents
     │
     ├→ /ims (IMS compliance posture)
     │
     ├→ /risk-register (top risks + heatmap)
     │
     ├→ /analytics → /analytics/advanced → /analytics/reports (generate board report)
     │
     └→ /ai-intelligence (AI insights)
```

**Coverage**: All screens exist. Missing: one-click board report generation, personalised executive dashboard.

---

## Gap Analysis

### Pages Without ANY Story Coverage

**All 70+ pages lack Storybook stories.** Current stories cover only the 26 shared UI primitives under `components/ui/`.

### Priority Story Backlog

Stories are prioritised by persona journey criticality and page complexity.

#### Tier 1 — Critical Path (P1 & P2 core journeys)

| Page | File | Recommended stories |
|---|---|---|
| Dashboard | `Dashboard.tsx` | `Loading`, `Populated`, `Error`, `EmptyWidgets` |
| Incidents List | `Incidents.tsx` | `Loading`, `Populated`, `Empty`, `Error`, `CreateDialog` |
| Incident Detail | `IncidentDetail.tsx` | `Loading`, `Populated`, `EditMode`, `InvestigationTab`, `ActionsTab` |
| Audit Management | `Audits.tsx` | `KanbanView`, `ListView`, `FindingsView`, `Empty`, `ScheduleModal`, `ImportModal` |
| Audit Execution | `AuditExecution.tsx` | `Loading`, `InProgress`, `SectionComplete`, `AllComplete` |
| Portal Home | `Portal.tsx` | `Default`, `WithUser` |
| Portal Dynamic Form | `PortalDynamicForm.tsx` | `Loading`, `FormActive`, `Submitting`, `Success`, `Error` |

#### Tier 2 — High Value (P3 journey + governance)

| Page | File | Recommended stories |
|---|---|---|
| Risk Register | `RiskRegister.tsx` | `RegisterView`, `HeatmapView`, `CreateDialog`, `DetailPanel`, `Empty` |
| Investigations Detail | `InvestigationDetail.tsx` | `Loading`, `Populated` (all tabs), `Error` |
| Compliance Evidence | `ComplianceEvidence.tsx` | `Loading`, `Populated`, `GapHighlighted` |
| Global Search | `GlobalSearch.tsx` | `EmptySearch`, `Searching`, `Results`, `NoResults`, `WithFilters` |
| Actions Tracker | `Actions.tsx` | `Loading`, `Populated`, `Filtered`, `Empty` |

#### Tier 3 — Supporting (P4 admin + P5 analytics)

| Page | File | Recommended stories |
|---|---|---|
| IMS Dashboard | `IMSDashboard.tsx` | `Loading`, `Populated` |
| AI Intelligence | `AIIntelligence.tsx` | `Loading`, `Populated` |
| Admin Dashboard | `AdminDashboard.tsx` | `Loading`, `Populated` |
| User Management | `admin/UserManagement.tsx` | `Loading`, `Populated`, `CreateDialog`, `EditDialog` |
| Form Builder | `admin/FormBuilder.tsx` | `CreateMode`, `EditMode`, `WithFields` |
| Audit Template Builder | `AuditTemplateBuilder.tsx` | `CreateMode`, `EditMode`, `PublishDialog` |
| Competency Dashboard | `workforce/CompetencyDashboard.tsx` | `Loading`, `Populated` |
| Engineer Profile | `workforce/EngineerProfile.tsx` | `Loading`, `Populated` |

#### Tier 4 — Remaining Pages

All remaining list pages (NearMisses, RTAs, Complaints, Standards, Documents, Policies, etc.) follow a consistent List pattern and can share a story template.

### Missing State Coverage

The following states are systematically under-covered across pages:

| Missing state | Pages affected | Recommendation |
|---|---|---|
| **Not-found** (invalid ID in detail pages) | All `/:id` detail routes (~12 pages) | Add 404-within-page state with "Record not found" + back link |
| **Permission-denied** | All role-gated routes (~15 pages) | `RequireRole` redirects to `/admin` but shows no explanatory UI; add `PermissionDenied` component |
| **Offline indicator** | Portal forms, Audit Execution | `OfflineIndicator` exists in Layout but portal forms lack queued-for-sync feedback |
| **Unsaved changes** | Template Builder, Form Builder | No `beforeunload` guard or dirty-state indicator |
| **Pagination** | All list pages | Client-side pagination via `page_size=50/100` but no pagination UI component exists |

---

## UX Quality Checklist

### Form Validation Patterns

| Pattern | Status | Pages |
|---|---|---|
| Inline validation (on blur) | Not implemented | All form pages use submit-time validation only |
| Submit-time validation | Implemented | Incidents create, Audits schedule/import, Portal forms |
| Required field indicators (`*`) | Implemented | Incident form, Audit form (via `<span className="text-destructive">*</span>`) |
| `aria-required="true"` | Partially | Incident form: yes; Audit form: missing |
| Error message association (`aria-describedby`) | Not implemented | No form fields link to error messages via `aria-describedby` |

**Recommendation**: Adopt inline validation with `aria-describedby` error association. Create a `FormField` wrapper component.

### Empty State Messaging

| Pattern | Status |
|---|---|
| `EmptyState` component used | 6 pages (Incidents, Audits list/kanban, Investigations, others) |
| Custom inline empty messages | ~10 pages (Dashboard widgets, Calendar, Notifications) |
| No empty state handling | ~5 pages (PlanetMark, ComplianceAutomation, AdvancedAnalytics) |

**Recommendation**: Standardise all empty states through the `EmptyState` component with contextual icon, title, description, and CTA.

### Loading Skeleton Patterns

| Pattern | Status |
|---|---|
| `CardSkeleton` | Dashboard |
| `TableSkeleton` | Incidents, Complaints |
| `LoadingSkeleton variant="table"` | Audits |
| Inline shimmer (`animate-pulse`) | Dashboard header skeleton |
| Full-page spinner (`PageLoader`) | All lazy-loaded routes (Suspense fallback) |

**Recommendation**: Standardise on `TableSkeleton` for list pages and `CardSkeleton` for dashboard pages. Avoid full-page spinners for data loading (reserve for code-splitting).

### Error Recovery Guidance

| Pattern | Status |
|---|---|
| Error banner with retry button | Dashboard, Audits |
| Error banner (no retry) | Incidents (load error) |
| Inline form error messages | Incidents create, Audits schedule |
| Toast notifications | Global Search errors |
| `ErrorBoundary` wrapper | All routes (via `RouteErrorBoundary` in App.tsx) |

**Recommendation**: All error states should include a retry action. Form errors should scroll to the first error field.

### Confirmation Before Destructive Actions

| Pattern | Status |
|---|---|
| `AlertDialog` used for confirms | Component exists; usage not found in page code |
| Delete confirmation | Not implemented in any visible page |
| Status change confirmation | Not implemented (status changes are immediate) |

**Recommendation**: Add `AlertDialog` confirmation for: status changes to "closed", record deletion, template publish, user deactivation.

### Toast / Notification Patterns

| Pattern | Status |
|---|---|
| `toast()` function (from `ToastContext`) | Used in Incidents (offline save), GlobalSearch |
| `ToastContainer` + `useToast` | Used in Audits |
| Inline success messages | Audit schedule success (in-dialog) |

**Recommendation**: Unify on a single toast pattern. The dual toast system (`ToastContext` vs `Toast.tsx` `useToast`) should be consolidated.

### Responsive Breakpoints

The platform uses Tailwind responsive utilities consistently:

| Breakpoint | Usage |
|---|---|
| `sm:` (640px) | Form layouts switch from stacked to inline; button labels appear |
| `md:` (768px) | Grid columns increase (2→4 for stat cards) |
| `lg:` (1024px) | Sidebar becomes fixed; grid expands to 3-column |
| `xl:` (1280px) | Kanban expands to 4-column |

Portal pages use `max-w-lg` constraint for mobile-first layout.

**Gap**: No explicit tablet-optimized breakpoint testing in stories. Recommend Chromatic viewport stories at 375px, 768px, 1024px, and 1440px.

### Keyboard Navigation

| Pattern | Status |
|---|---|
| Skip-to-content link | Implemented in `Layout.tsx` |
| `Cmd+K` global search | Implemented in `Layout.tsx` |
| `role="button"` on clickable rows | Implemented in Incidents, Audits |
| `tabIndex={0}` on interactive cards | Implemented in Audits kanban |
| `onKeyDown` (Enter/Space) handlers | Implemented in Incidents, Audits |
| Focus management after modal close | Handled by Radix Dialog |

**Gap**: Focus is not managed when navigating between pages (no focus-on-main-content after route change). Recommend adding focus management to `AnimatedOutlet`.

### Screen Reader Support

| Pattern | Status |
|---|---|
| `aria-label` on icon buttons | Partial (some header icons lack labels) |
| `sr-only` text for visual-only content | Used for actions column header in Audits |
| `aria-pressed` on toggles | Used for Audits view mode toggle |
| `LiveAnnouncer` | Used in Portal home |
| `aria-live` regions | Not used for dynamic content updates |

**Recommendation**: Add `aria-live="polite"` to search results count, form error summaries, and toast regions.

---

## Appendix: Component Usage Heatmap

Components sorted by usage frequency across pages:

| Component | Pages using it | Stories exist |
|---|---|---|
| `Button` | 50+ | Yes |
| `Card` / `CardContent` | 45+ | Yes |
| `Badge` | 40+ | Yes |
| `Input` | 35+ | Yes |
| `Dialog` / `DialogContent` | 25+ | Yes |
| `Select` / `SelectContent` | 20+ | Yes |
| `EmptyState` | 6 | Yes |
| `Tabs` / `TabsList` | 8 | Yes |
| `Breadcrumbs` | 5 | Yes |
| `Textarea` | 10+ | Yes |
| `TableSkeleton` | 6 | Yes |
| `CardSkeleton` | 3 | Yes |
| `LoadingSkeleton` | 3 | Yes |
| `ProgressBar` | 3 | Yes |
| `ToastContainer` | 2 | Yes |
| `ThemeToggle` | 3 | Yes |
| `Avatar` | 2 | Yes |
| `LiveAnnouncer` | 1 | Yes |
| `AlertDialog` | 0 pages | Yes |
| `SetupRequiredPanel` | 1 | Yes |

**Notable**: `AlertDialog` has a story but is not used in any page (see destructive-action confirmation gap above).
