# Audit Lifecycle Contract Freeze

Version: 1.0  
Status: Frozen (breaking changes require governance approval)  
Owner: Governance Platform Engineering

## Purpose

This contract locks the API and UX behaviors required for reliable audit operations:

1. Scheduling must only allow published templates.
2. Audit runs must persist and surface the template version used.
3. Question/template text must render decoded user-facing content (no raw HTML entities like `&amp;`).

## API Contract

### Template Listing for Scheduling

- Endpoint: `GET /api/v1/audits/templates`
- Required query support: `is_published=true|false`
- Scheduling UI must call with `is_published=true`.
- Response item fields required by scheduler:
  - `id`
  - `name`
  - `reference_number`
  - `version`
  - `is_published`
  - `category` or `audit_type`

### Audit Run Creation

- Endpoint: `POST /api/v1/audits/runs`
- Request requires `template_id` referencing a published template.
- Response must include:
  - `id`
  - `reference_number`
  - `template_id`
  - `template_version`
  - `status`

### Template Detail and Question Content

- Endpoint: `GET /api/v1/audits/templates/{template_id}`
- Response text fields must be returned decoded for display:
  - template `name`, `description`, `category`
  - section `title`, `description`
  - question `question_text`, `description`, `help_text`
  - question option `label`, `value`

## UX Contract

### Audits Scheduler (`frontend/src/pages/Audits.tsx`)

- Template picker is a dropdown (`select`) with published templates only.
- Dropdown option format:
  - `Name (v{version}) - {reference_number}`
- Selection panel shows chosen template metadata:
  - `name`, `category/audit_type`, `version`, `reference_number`

### Audits Views

- Kanban card and list view must display `template_version`.
- Version label format: `v{template_version}`.

### Entity Rendering

- Any template/question text displayed in the scheduler must be decoded before render.
- Forbidden user-facing output pattern: raw HTML entities (`&amp;`, `&lt;`, `&gt;`) unless intentionally authored as literal text.

## Change Control

Any breaking change to this contract requires:

1. OpenAPI diff review.
2. Updated contract tests.
3. Governance lead sign-off in release evidence.
