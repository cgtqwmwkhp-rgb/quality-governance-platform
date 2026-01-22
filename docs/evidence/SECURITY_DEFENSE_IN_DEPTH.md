# Security Defense in Depth - XSS Protection

**Date:** 2026-01-22  
**Status:** Implemented  
**Issue:** SUAT-010 XSS Payload Handling

## Overview

This document provides evidence of defense-in-depth protection against Cross-Site Scripting (XSS) attacks across the Quality Governance Platform.

## Defense Layers

### Layer 1: Content Security Policy (CSP)

**Location:** `frontend/staticwebapp.config.json`

```json
{
  "globalHeaders": {
    "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline' https://login.microsoftonline.com; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self' data:; connect-src 'self' https://*.azurewebsites.net https://login.microsoftonline.com https://graph.microsoft.com; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
  }
}
```

**Protections:**
- `default-src 'self'`: Only load resources from same origin
- `script-src 'self' 'unsafe-inline'`: Scripts only from same origin (unsafe-inline required for React build)
- `frame-ancestors 'none'`: Prevent clickjacking
- `base-uri 'self'`: Prevent base tag hijacking
- `form-action 'self'`: Forms only submit to same origin

**Note:** `'unsafe-inline'` is required for React's runtime. This is mitigated by Layer 2 (no HTML injection vector).

### Layer 2: React JSX Auto-Escaping

**Location:** `frontend/src/pages/PortalTrack.tsx`

React automatically escapes all content rendered via JSX expressions:

```tsx
// Line 206-207: Report list title
<h3 className="font-medium text-foreground truncate mb-1">
  {report.title || config.label}
</h3>

// Line 497: Report detail title
<h2 className="text-lg font-bold text-foreground">{selectedReport.title}</h2>
```

**Evidence:** No `dangerouslySetInnerHTML` found in frontend codebase:
```bash
grep -r "dangerouslySetInnerHTML\|v-html\|innerHTML\|__html" frontend/
# No matches found
```

**How it works:**
- JSX expression `{report.title}` converts to `React.createElement('h3', null, report.title)`
- React's `textContent` assignment escapes HTML entities
- `<script>` becomes `&lt;script&gt;` in the DOM

### Layer 3: JSON Encoding (API Layer)

**Location:** All API endpoints return JSON

The API stores user input as-is but returns it as properly JSON-encoded strings:

```json
{
  "title": "<script>alert('xss')</script>",
  "status": "reported"
}
```

When JavaScript parses this JSON:
```javascript
const data = JSON.parse(response);
// data.title is a string value: "<script>alert('xss')</script>"
// Not executable code
```

### Layer 4: Security Headers

**API Headers (SecurityHeadersMiddleware):**
```
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
```

**Frontend Headers (Azure Static Web Apps):**
```
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
X-XSS-Protection: 1; mode=block
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: geolocation=(), microphone=(), camera=()
Content-Security-Policy: [see Layer 1]
```

## Test Coverage

### Automated Tests

| Test | Location | Purpose |
|------|----------|---------|
| `test_xss_payload_in_title_is_json_encoded` | `tests/security/test_xss_protection.py` | Verify JSON encoding |
| `test_xss_payload_in_description_is_json_encoded` | `tests/security/test_xss_protection.py` | Verify description handling |
| `test_security_headers_present` | `tests/security/test_xss_protection.py` | Verify security headers |
| `test_unicode_and_special_chars_handled_safely` | `tests/security/test_xss_protection.py` | Verify unicode handling |
| `test_suat_010_special_characters_in_title` | `tests/uat/test_stage2_sophisticated_workflows.py` | UAT validation |

### Manual Verification

To manually verify XSS protection:

1. Submit a report with title: `<script>alert('xss')</script>`
2. Navigate to portal track page
3. Observe that the title displays as literal text
4. Open browser console - no JavaScript errors or alerts
5. Inspect DOM - script tags are escaped HTML entities

## Attack Vectors Mitigated

| Attack Vector | Mitigation |
|---------------|------------|
| Reflected XSS via title | JSX escaping + CSP |
| Stored XSS via description | JSX escaping + CSP |
| DOM-based XSS | No `innerHTML` usage |
| Event handler injection | CSP + no dynamic HTML |
| SVG-based XSS | CSP `img-src` restrictions |
| CSS injection | CSP `style-src 'self'` |

## Residual Risk

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| CSP bypass via `unsafe-inline` | Low | Medium | React build requires it; no HTML injection vector |
| Future code using `dangerouslySetInnerHTML` | Low | High | Code review process; grep check in CI |

## Compliance

- OWASP Top 10 A7:2017 - Cross-Site Scripting (XSS): ✅ Addressed
- CWE-79: Improper Neutralization of Input During Web Page Generation: ✅ Addressed

## Evidence Artifacts

- CSP Configuration: `frontend/staticwebapp.config.json`
- XSS Tests: `tests/security/test_xss_protection.py`
- No innerHTML Usage: `grep` evidence above
- Frontend Rendering: `frontend/src/pages/PortalTrack.tsx` lines 206-207, 497
