"""Who is allowed to reach an endpoint without an authorisation check, and why.

Why a declaration exists at all
-------------------------------
A census of the mounted app (:mod:`src.domain.authz.census`) can say what every
endpoint demands, but it cannot say whether that is *right*. This module is where
a human says so, for the two answers that need justifying:

:data:`PUBLIC_BY_DESIGN`
    Endpoints that establish no caller identity, or read one only if offered, and
    are meant to. Each carries the reason, written after reading the handler.

:data:`AUTHENTICATED_ONLY_DEBT`
    Endpoints that authenticate the caller and then check nothing. These are not
    justified — they are *recorded*. Every entry is a place where any
    authenticated user of any tenant may perform the operation, and the list is
    the honest measurement of the gap, not an approval of it.

How this fails closed
---------------------
``tests/integration/test_route_authorisation_census.py`` takes the census and
requires that every endpoint is either authorisation-checked or named here. A new
route that is neither fails the build, so it cannot reach production
unclassified. Three properties make that hard to work around:

1. **Exact agreement.** The declared sets must match the census exactly. A route
   that gains a permission check must be removed from the debt list in the same
   change, so the list can never overstate the debt either.
2. **A ceiling on each list.** :data:`MAX_AUTHENTICATED_ONLY_DEBT` and
   :data:`MAX_PUBLIC_BY_DESIGN` record the size at the moment the gap was
   measured, and the test refuses any total above them. The easy way out — adding
   the new route to the debt list — is therefore closed, and the numbers can only
   go down.
3. **No pattern matching.** Entries are exact ``(method, path)`` pairs, never
   prefixes or globs. A new route inside an already-declared module inherits
   nothing, which is the specific failure that let this gap grow: a guard written
   per module is a guard the next route does not get.

Raising a ceiling is possible, and deliberately conspicuous: it is a one-line
diff, with a number in it, in a file whose only purpose is to say what is
unprotected.

Which app this describes
------------------------
The mounted route surface is environment-dependent: ``src/api/__init__.py`` mounts
the ``/testing`` router only when ``settings.is_production`` is false, and
``src/main.py`` disables ``/docs``, ``/redoc`` and ``/openapi.json`` when it is
true. The counts here are the **non-production** surface, which is the larger of
the two and therefore the safe one to hold to a ceiling. The census test asserts it
is not running under production settings, so a smaller measurement cannot be
mistaken for shrinking debt.

What this file is not
---------------------
It is not a tenancy control. Tenant scoping is a separate concern with a separate
owner, and an endpoint in :data:`AUTHENTICATED_ONLY_DEBT` may still be correctly
tenant-scoped. It is also not a statement that a listed endpoint is unsafe: some
enforce ownership inside the handler, and several in :data:`PUBLIC_BY_DESIGN` carry
a credential that is not a session. It records only what refuses a request before
the handler runs.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Mapping

#: How an endpoint is identified: its HTTP method (or ``"WEBSOCKET"``) and the
#: templated path it is served under, exactly as the census reports them.
EndpointKey = tuple[str, str]

_FASTAPI_DOCS = (
    "FastAPI's interactive API documentation. Served as a plain Starlette route, so it has no "
    "dependency graph to gate; src/main.py disables it entirely when settings.is_production."
)

#: Endpoints intended to be reachable without an authorisation check, each with
#: the reason. A reason is required: an entry without one is indistinguishable
#: from a route somebody forgot to gate.
#:
#: "Public" here means only that the request is not refused by a permission or
#: superuser dependency. Several of these carry a different credential entirely —
#: a signing token in the path, an HMAC signature, a CI secret header, or a JWT
#: verified inside a websocket handler — and the reason says which.
PUBLIC_BY_DESIGN: Mapping[EndpointKey, str] = MappingProxyType(
    {
        ("GET", "/"): ("Unauthenticated ops/deployment metadata. Carries no tenant data."),
        ("GET", "/.well-known/security.txt"): ("RFC 9116 requires this to be served unauthenticated."),
        ("POST", "/api/v1/auth/login"): ("Establishes or renews a session, so it cannot require one."),
        ("POST", "/api/v1/auth/password-reset/confirm"): ("Establishes or renews a session, so it cannot require one."),
        ("POST", "/api/v1/auth/password-reset/request"): ("Establishes or renews a session, so it cannot require one."),
        ("POST", "/api/v1/auth/refresh"): ("Establishes or renews a session, so it cannot require one."),
        ("POST", "/api/v1/auth/token-exchange"): ("Establishes or renews a session, so it cannot require one."),
        ("WEBSOCKET", "/api/v1/copilot/ws/{session_id}"): (
            "Websocket handshake. The JWT arrives in the Authorization header or the token query "
            "parameter and is verified in the handler, which closes the socket when it is absent or "
            "invalid, so authentication happens in-protocol rather than as a dependency."
        ),
        ("GET", "/api/v1/evidence-assets/download"): (
            "HMAC-signed download URL for local development storage. The handler refuses with "
            "NOT_AVAILABLE unless the storage backend is LocalFileStorageService, so it is unreachable in "
            "any deployment using blob storage, and it verifies the signature and expiry with "
            "hmac.compare_digest before serving bytes."
        ),
        ("GET", "/api/v1/health"): ("Infrastructure liveness/readiness probe, called before any user exists."),
        ("GET", "/api/v1/health/"): ("Infrastructure liveness/readiness probe, called before any user exists."),
        ("GET", "/api/v1/health/diagnostics"): ("Unauthenticated ops/deployment metadata. Carries no tenant data."),
        ("GET", "/api/v1/health/healthz"): ("Infrastructure liveness/readiness probe, called before any user exists."),
        ("GET", "/api/v1/health/meta/ocr-capabilities"): (
            "Static capability metadata describing which OCR providers are configured. No tenant data."
        ),
        ("GET", "/api/v1/health/meta/ocr-providers"): (
            "Static capability metadata describing which OCR providers are configured. No tenant data."
        ),
        ("GET", "/api/v1/health/metrics/resources"): (
            "Unauthenticated ops/deployment metadata. Carries no tenant data."
        ),
        ("GET", "/api/v1/health/readyz"): ("Infrastructure liveness/readiness probe, called before any user exists."),
        ("GET", "/api/v1/meta/ocr-capabilities"): (
            "Static capability metadata describing which OCR providers are configured. No tenant data."
        ),
        ("GET", "/api/v1/meta/ocr-providers"): (
            "Static capability metadata describing which OCR providers are configured. No tenant data."
        ),
        ("GET", "/api/v1/meta/version"): ("Unauthenticated ops/deployment metadata. Carries no tenant data."),
        ("GET", "/api/v1/notifications/push/vapid-status"): (
            "Reports whether a VAPID key pair is configured and returns the public half, which is public "
            "by construction: the browser needs it to subscribe."
        ),
        ("GET", "/api/v1/portal/qr/{reference_number}/"): (
            "Employee portal is anonymous by design: reporters are not required to hold an account."
        ),
        ("GET", "/api/v1/portal/report-types/"): (
            "Employee portal is anonymous by design: reporters are not required to hold an account."
        ),
        ("POST", "/api/v1/portal/reports/"): (
            "Employee portal is anonymous by design: reporters are not required to hold an account."
        ),
        ("POST", "/api/v1/portal/reports/attachments"): (
            "Employee portal is anonymous by design: reporters are not required to hold an account."
        ),
        ("GET", "/api/v1/portal/reports/{reference_number}/"): (
            "Employee portal is anonymous by design: reporters are not required to hold an account. Reads "
            "are keyed on the reference number issued to the reporter at submission."
        ),
        ("GET", "/api/v1/privacy/contact"): (
            "Statutory public disclosure (UK GDPR Arts 13-14); must be readable without an account."
        ),
        ("GET", "/api/v1/privacy/data-processing-register"): (
            "Statutory public disclosure (UK GDPR Arts 13-14); must be readable without an account."
        ),
        ("WEBSOCKET", "/api/v1/realtime/ws/{user_id}"): (
            "Websocket handshake. The JWT arrives in the Authorization header or the token query "
            "parameter and is verified in the handler, which closes the socket when it is absent or "
            "invalid, so authentication happens in-protocol rather than as a dependency."
        ),
        ("GET", "/api/v1/signatures/sign/{token}"): (
            "Capability URL: the single-use signing token in the path is the credential. Signatories are "
            "external parties with no account."
        ),
        ("POST", "/api/v1/signatures/sign/{token}"): (
            "Capability URL: the single-use signing token in the path is the credential. Signatories are "
            "external parties with no account."
        ),
        ("POST", "/api/v1/signatures/sign/{token}/decline"): (
            "Capability URL: the single-use signing token in the path is the credential. Signatories are "
            "external parties with no account."
        ),
        ("GET", "/api/v1/slo/current"): ("Unauthenticated ops/deployment metadata. Carries no tenant data."),
        ("GET", "/api/v1/slo/metrics"): ("Unauthenticated ops/deployment metadata. Carries no tenant data."),
        ("POST", "/api/v1/telemetry/events"): (
            "Browser beacon, sent without a session and before login on the login page itself."
        ),
        ("POST", "/api/v1/telemetry/events/batch"): (
            "Browser beacon, sent without a session and before login on the login page itself."
        ),
        ("POST", "/api/v1/telemetry/web-vitals"): (
            "Browser beacon, sent without a session and before login on the login page itself."
        ),
        ("POST", "/api/v1/testing/ensure-test-user"): (
            "Refuses unless APP_ENV=staging and the X-CI-Secret header matches CI_TEST_SECRET."
        ),
        ("GET", "/api/v1/testing/health"): (
            "Refuses unless APP_ENV=staging and the X-CI-Secret header matches CI_TEST_SECRET."
        ),
        # FastAPI's own documentation routes, installed by ``FastAPI.__init__`` as
        # plain Starlette routes rather than API routes. src/main.py passes
        # docs_url=None, redoc_url=None and openapi_url=None when
        # settings.is_production, so none of these four is mounted in production;
        # they are reachable in development and staging only. HEAD is listed
        # alongside GET because Starlette serves both.
        ("GET", "/docs"): _FASTAPI_DOCS,
        ("HEAD", "/docs"): _FASTAPI_DOCS,
        ("GET", "/docs/oauth2-redirect"): _FASTAPI_DOCS,
        ("HEAD", "/docs/oauth2-redirect"): _FASTAPI_DOCS,
        ("GET", "/openapi.json"): _FASTAPI_DOCS,
        ("HEAD", "/openapi.json"): _FASTAPI_DOCS,
        ("GET", "/redoc"): _FASTAPI_DOCS,
        ("HEAD", "/redoc"): _FASTAPI_DOCS,
        ("GET", "/health"): ("Infrastructure liveness/readiness probe, called before any user exists."),
        ("GET", "/healthz"): ("Infrastructure liveness/readiness probe, called before any user exists."),
        ("GET", "/readyz"): ("Infrastructure liveness/readiness probe, called before any user exists."),
    }
)

#: Endpoints that authenticate and then authorise nothing.
#:
#: Grouped by the module that serves them, sorted, and exact. This is the C-2
#: measurement: 474 endpoints on which any authenticated user may perform the
#: operation. Reducing it is the follow-up work; the ceiling below is what stops
#: it growing while that happens.
AUTHENTICATED_ONLY_DEBT: frozenset[EndpointKey] = frozenset(
    {
        # src.api.routes.actions
        ("GET", "/api/v1/actions"),
        ("GET", "/api/v1/actions/"),
        ("GET", "/api/v1/actions/by-key"),
        ("GET", "/api/v1/actions/by-key/notes"),
        ("GET", "/api/v1/actions/summary"),
        ("GET", "/api/v1/actions/view-counts"),
        ("GET", "/api/v1/actions/{action_id}"),
        # src.api.routes.ai_intelligence
        ("GET", "/api/v1/ai/anomalies/frequency"),
        ("GET", "/api/v1/ai/anomalies/patterns"),
        ("GET", "/api/v1/ai/audit/evidence/{standard}/{clause}"),
        ("GET", "/api/v1/ai/audit/recurring-findings"),
        ("GET", "/api/v1/ai/audit/trends"),
        ("GET", "/api/v1/ai/audit/{audit_id}/evidence-gaps"),
        ("GET", "/api/v1/ai/audit/{audit_id}/executive-summary"),
        ("GET", "/api/v1/ai/audit/{audit_id}/findings-report"),
        ("GET", "/api/v1/ai/health"),
        ("GET", "/api/v1/ai/predict/risk-factors"),
        ("GET", "/api/v1/ai/root-cause/clusters"),
        # src.api.routes.ai_templates
        ("GET", "/api/v1/ai-templates/challenge/sessions/{session_id}"),
        # src.api.routes.analytics
        ("GET", "/api/v1/analytics/benchmarks"),
        ("GET", "/api/v1/analytics/benchmarks/{metric}"),
        ("GET", "/api/v1/analytics/costs/breakdown"),
        ("GET", "/api/v1/analytics/costs/non-compliance"),
        ("GET", "/api/v1/analytics/dashboards"),
        ("GET", "/api/v1/analytics/dashboards/{dashboard_id}"),
        ("GET", "/api/v1/analytics/drill-down/{data_source}"),
        ("GET", "/api/v1/analytics/kpis"),
        ("GET", "/api/v1/analytics/reports/executive-summary"),
        ("GET", "/api/v1/analytics/reports/{report_id}/status"),
        ("GET", "/api/v1/analytics/roi"),
        ("GET", "/api/v1/analytics/roi/{investment_id}"),
        ("GET", "/api/v1/analytics/trends/{data_source}"),
        ("GET", "/api/v1/analytics/widgets/{widget_id}/data"),
        # src.api.routes.assessments
        ("GET", "/api/v1/assessments/"),
        ("GET", "/api/v1/assessments/{run_id}"),
        # src.api.routes.asset_health_analytics
        ("GET", "/api/v1/asset-health/summary"),
        # src.api.routes.assets
        ("GET", "/api/v1/assets/"),
        ("GET", "/api/v1/assets/asset-types"),
        ("GET", "/api/v1/assets/asset-types/{asset_type_id}"),
        ("GET", "/api/v1/assets/asset-types/{asset_type_id}/templates"),
        ("GET", "/api/v1/assets/locations"),
        ("GET", "/api/v1/assets/locations/{location_id}"),
        ("GET", "/api/v1/assets/my-tools"),
        ("GET", "/api/v1/assets/{asset_id}"),
        # src.api.routes.audit_templates
        ("GET", "/api/v1/audit-templates"),
        ("GET", "/api/v1/audit-templates/"),
        ("GET", "/api/v1/audit-templates/categories"),
        ("GET", "/api/v1/audit-templates/{template_id}"),
        # src.api.routes.audit_trail
        ("GET", "/api/v1/audit-trail/"),
        ("GET", "/api/v1/audit-trail/actions"),
        ("GET", "/api/v1/audit-trail/entity-types"),
        ("GET", "/api/v1/audit-trail/entity/{entity_type}/{entity_id}"),
        ("GET", "/api/v1/audit-trail/stats"),
        ("GET", "/api/v1/audit-trail/user/{user_id}"),
        ("GET", "/api/v1/audit-trail/verifications"),
        ("GET", "/api/v1/audit-trail/{entry_id}"),
        # src.api.routes.auditor_competence
        ("GET", "/api/v1/auditor-competence/certifications/expiring"),
        ("GET", "/api/v1/auditor-competence/dashboard"),
        ("GET", "/api/v1/auditor-competence/find-auditors/{audit_type}"),
        ("GET", "/api/v1/auditor-competence/profiles/{user_id}"),
        ("POST", "/api/v1/auditor-competence/profiles/{user_id}/calculate-score"),
        ("GET", "/api/v1/auditor-competence/profiles/{user_id}/certifications"),
        ("GET", "/api/v1/auditor-competence/profiles/{user_id}/gaps"),
        ("POST", "/api/v1/auditor-competence/training/{training_id}/complete"),
        # src.api.routes.audits
        ("GET", "/api/v1/audits/analytics/critical-queue"),
        ("GET", "/api/v1/audits/analytics/dimensions"),
        ("GET", "/api/v1/audits/analytics/export.csv"),
        ("GET", "/api/v1/audits/analytics/summary"),
        ("GET", "/api/v1/audits/findings"),
        ("GET", "/api/v1/audits/findings/{finding_id}/golden-thread"),
        ("DELETE", "/api/v1/audits/questions/{question_id}"),
        ("PATCH", "/api/v1/audits/questions/{question_id}"),
        ("PATCH", "/api/v1/audits/responses/{response_id}"),
        ("GET", "/api/v1/audits/runs"),
        ("GET", "/api/v1/audits/runs/{run_id}"),
        ("POST", "/api/v1/audits/runs/{run_id}/complete"),
        ("POST", "/api/v1/audits/runs/{run_id}/responses"),
        ("POST", "/api/v1/audits/runs/{run_id}/start"),
        ("DELETE", "/api/v1/audits/sections/{section_id}"),
        ("PATCH", "/api/v1/audits/sections/{section_id}"),
        ("GET", "/api/v1/audits/templates"),
        ("GET", "/api/v1/audits/templates/archived"),
        ("GET", "/api/v1/audits/templates/{template_id}"),
        ("DELETE", "/api/v1/audits/templates/{template_id}/asset-types/{asset_type_id}"),
        ("POST", "/api/v1/audits/templates/{template_id}/asset-types/{asset_type_id}"),
        ("POST", "/api/v1/audits/templates/{template_id}/clone"),
        ("POST", "/api/v1/audits/templates/{template_id}/publish"),
        ("POST", "/api/v1/audits/templates/{template_id}/questions"),
        ("POST", "/api/v1/audits/templates/{template_id}/restore"),
        ("POST", "/api/v1/audits/templates/{template_id}/sections"),
        # src.api.routes.auth
        ("POST", "/api/v1/auth/change-password"),
        ("POST", "/api/v1/auth/logout"),
        ("GET", "/api/v1/auth/me"),
        ("GET", "/api/v1/auth/whoami"),
        # src.api.routes.calendar
        ("GET", "/api/v1/calendar/feed"),
        # src.api.routes.capa
        ("GET", "/api/v1/capa"),
        ("GET", "/api/v1/capa/"),
        ("GET", "/api/v1/capa/stats"),
        ("GET", "/api/v1/capa/{capa_id}"),
        # src.api.routes.competency_requirements
        ("GET", "/api/v1/competency-requirements/"),
        ("GET", "/api/v1/competency-requirements/{requirement_id}"),
        # src.api.routes.complaints
        ("POST", "/api/v1/complaints/{complaint_id}/running-sheet"),
        ("DELETE", "/api/v1/complaints/{complaint_id}/running-sheet/{entry_id}"),
        # src.api.routes.compliance
        ("GET", "/api/v1/compliance/audit-pack"),
        ("GET", "/api/v1/compliance/clauses"),
        ("GET", "/api/v1/compliance/clauses/{clause_id}"),
        ("GET", "/api/v1/compliance/coverage"),
        ("GET", "/api/v1/compliance/evidence/links"),
        ("GET", "/api/v1/compliance/gaps"),
        ("GET", "/api/v1/compliance/report"),
        ("GET", "/api/v1/compliance/soa"),
        ("GET", "/api/v1/compliance/standards"),
        # src.api.routes.compliance_automation
        ("GET", "/api/v1/compliance-automation/certificates"),
        ("GET", "/api/v1/compliance-automation/certificates/expiring-summary"),
        ("GET", "/api/v1/compliance-automation/certificates/shelf"),
        ("GET", "/api/v1/compliance-automation/gap-analyses"),
        ("GET", "/api/v1/compliance-automation/regulatory-updates"),
        ("GET", "/api/v1/compliance-automation/riddor/submissions"),
        ("GET", "/api/v1/compliance-automation/scheduled-audits"),
        ("GET", "/api/v1/compliance-automation/score"),
        ("GET", "/api/v1/compliance-automation/score/trend"),
        # src.api.routes.copilot
        ("GET", "/api/v1/copilot/actions"),
        ("POST", "/api/v1/copilot/actions/execute"),
        ("GET", "/api/v1/copilot/actions/suggest"),
        ("POST", "/api/v1/copilot/knowledge"),
        ("GET", "/api/v1/copilot/knowledge/search"),
        ("POST", "/api/v1/copilot/messages/{message_id}/feedback"),
        ("GET", "/api/v1/copilot/sessions"),
        ("POST", "/api/v1/copilot/sessions"),
        ("GET", "/api/v1/copilot/sessions/active"),
        ("DELETE", "/api/v1/copilot/sessions/{session_id}"),
        ("GET", "/api/v1/copilot/sessions/{session_id}"),
        ("GET", "/api/v1/copilot/sessions/{session_id}/messages"),
        ("POST", "/api/v1/copilot/sessions/{session_id}/messages"),
        # src.api.routes.cross_standard_mappings
        ("GET", "/api/v1/cross-standard-mappings"),
        ("GET", "/api/v1/cross-standard-mappings/standards"),
        ("GET", "/api/v1/cross-standard-mappings/{mapping_id}"),
        # src.api.routes.document_campaign
        ("POST", "/api/v1/document-campaigns/assignments/{assignment_id}/complete"),
        ("GET", "/api/v1/document-campaigns/assignments/{assignment_id}/document-url"),
        ("POST", "/api/v1/document-campaigns/assignments/{assignment_id}/open"),
        ("POST", "/api/v1/document-campaigns/assignments/{assignment_id}/questions"),
        ("GET", "/api/v1/document-campaigns/assignments/{assignment_id}/quiz"),
        ("POST", "/api/v1/document-campaigns/assignments/{assignment_id}/quiz"),
        ("POST", "/api/v1/document-campaigns/assignments/{assignment_id}/signature"),
        ("POST", "/api/v1/document-campaigns/assignments/{assignment_id}/snooze"),
        ("GET", "/api/v1/document-campaigns/campaigns"),
        ("GET", "/api/v1/document-campaigns/campaigns/{campaign_id}"),
        ("GET", "/api/v1/document-campaigns/documents/{document_id}/campaigns"),
        ("GET", "/api/v1/document-campaigns/my-assignments"),
        ("GET", "/api/v1/document-campaigns/my-passport"),
        # src.api.routes.document_categories
        ("GET", "/api/v1/document-categories"),
        ("GET", "/api/v1/document-categories/"),
        ("GET", "/api/v1/document-categories/rbac-catalog"),
        ("GET", "/api/v1/document-categories/tags"),
        # src.api.routes.document_control
        ("GET", "/api/v1/document-control/"),
        ("GET", "/api/v1/document-control/summary"),
        ("GET", "/api/v1/document-control/workflows"),
        ("GET", "/api/v1/document-control/{document_id}"),
        ("GET", "/api/v1/document-control/{document_id}/access-log"),
        ("GET", "/api/v1/document-control/{document_id}/golden-thread"),
        ("GET", "/api/v1/document-control/{document_id}/versions/{version_id}/diff"),
        # src.api.routes.documents
        ("GET", "/api/v1/documents"),
        ("GET", "/api/v1/documents/"),
        ("GET", "/api/v1/documents/index-jobs/{job_id}"),
        ("GET", "/api/v1/documents/search/semantic"),
        ("GET", "/api/v1/documents/stats/overview"),
        ("GET", "/api/v1/documents/{document_id}"),
        ("GET", "/api/v1/documents/{document_id}/annotations"),
        ("GET", "/api/v1/documents/{document_id}/signed-url"),
        ("GET", "/api/v1/documents/{document_id}/versions"),
        # src.api.routes.drivers
        ("GET", "/api/v1/drivers/"),
        ("POST", "/api/v1/drivers/acknowledgements/{ack_id}/respond"),
        ("GET", "/api/v1/drivers/by-user/me"),
        ("GET", "/api/v1/drivers/{driver_id}"),
        ("GET", "/api/v1/drivers/{driver_id}/acknowledgements"),
        # src.api.routes.employee_portal
        ("GET", "/api/v1/portal/my-reports/"),
        ("GET", "/api/v1/portal/stats"),
        ("GET", "/api/v1/portal/stats/"),
        # src.api.routes.engineers
        ("GET", "/api/v1/engineers/"),
        ("GET", "/api/v1/engineers/by-user/me"),
        ("GET", "/api/v1/engineers/{engineer_id}"),
        ("GET", "/api/v1/engineers/{engineer_id}/competencies"),
        ("GET", "/api/v1/engineers/{engineer_id}/skills-matrix"),
        # src.api.routes.evidence_assets
        ("GET", "/api/v1/evidence-assets"),
        ("GET", "/api/v1/evidence-assets/"),
        ("GET", "/api/v1/evidence-assets/{asset_id}"),
        ("GET", "/api/v1/evidence-assets/{asset_id}/signed-url"),
        # src.api.routes.executive_dashboard
        ("GET", "/api/v1/executive-dashboard"),
        ("GET", "/api/v1/executive-dashboard/alerts"),
        ("GET", "/api/v1/executive-dashboard/compliance"),
        ("GET", "/api/v1/executive-dashboard/health-score"),
        ("GET", "/api/v1/executive-dashboard/incidents"),
        ("GET", "/api/v1/executive-dashboard/risks"),
        ("GET", "/api/v1/executive-dashboard/summary"),
        ("GET", "/api/v1/executive-dashboard/vehicle-governance"),
        # src.api.routes.external_audit_records
        ("GET", "/api/v1/external-audit-records"),
        ("GET", "/api/v1/external-audit-records/"),
        ("GET", "/api/v1/external-audit-records/dashboard"),
        ("GET", "/api/v1/external-audit-records/{record_id}"),
        # src.api.routes.feature_flags
        ("GET", "/api/v1/feature-flags"),
        ("GET", "/api/v1/feature-flags/"),
        ("GET", "/api/v1/feature-flags/{key}"),
        ("POST", "/api/v1/feature-flags/{key}/evaluate"),
        # src.api.routes.form_config
        ("GET", "/api/v1/admin/config/contracts"),
        ("GET", "/api/v1/admin/config/contracts/{contract_id}"),
        ("GET", "/api/v1/admin/config/lookup/{category}"),
        ("GET", "/api/v1/admin/config/settings"),
        ("GET", "/api/v1/admin/config/templates"),
        ("GET", "/api/v1/admin/config/templates/by-slug/{slug}"),
        ("GET", "/api/v1/admin/config/templates/{template_id}"),
        # src.api.routes.gdpr
        ("POST", "/api/v1/gdpr/me/data-erasure"),
        ("GET", "/api/v1/gdpr/me/data-erasure/status"),
        ("GET", "/api/v1/gdpr/me/data-export"),
        # src.api.routes.global_search
        ("GET", "/api/v1/search"),
        ("GET", "/api/v1/search/"),
        ("POST", "/api/v1/search/interpret"),
        # src.api.routes.governance
        ("GET", "/api/v1/governance/check-template/{template_id}"),
        ("GET", "/api/v1/governance/competency-gate"),
        ("GET", "/api/v1/governance/scheduling-suggestions/{engineer_id}"),
        ("GET", "/api/v1/governance/validate-supervisor"),
        # src.api.routes.governed_knowledge
        ("GET", "/api/v1/knowledge-bank/documents/{document_id}/discussions"),
        ("GET", "/api/v1/knowledge-bank/documents/{document_id}/evidence"),
        ("GET", "/api/v1/knowledge-bank/entities/{entity_type}/{entity_id}/assessment"),
        ("GET", "/api/v1/knowledge-bank/entities/{entity_type}/{entity_id}/assessment-trail"),
        ("GET", "/api/v1/knowledge-bank/exceptions"),
        ("GET", "/api/v1/knowledge-bank/exceptions/operational-counts"),
        ("GET", "/api/v1/knowledge-bank/regulatory-watch/impacts"),
        # src.api.routes.hs_kpis
        ("GET", "/api/v1/hs-kpis/periods"),
        ("GET", "/api/v1/hs-kpis/summary"),
        # src.api.routes.ims_dashboard
        ("GET", "/api/v1/ims/dashboard"),
        # src.api.routes.incidents
        ("POST", "/api/v1/incidents/{incident_id}/running-sheet"),
        ("DELETE", "/api/v1/incidents/{incident_id}/running-sheet/{entry_id}"),
        # src.api.routes.inductions
        ("GET", "/api/v1/inductions/"),
        ("GET", "/api/v1/inductions/{run_id}"),
        # src.api.routes.investigation_templates
        ("GET", "/api/v1/investigation-templates/"),
        ("GET", "/api/v1/investigation-templates/{template_id}"),
        # src.api.routes.investigations
        ("GET", "/api/v1/investigations"),
        ("GET", "/api/v1/investigations/"),
        ("GET", "/api/v1/investigations/source-coverage"),
        ("GET", "/api/v1/investigations/source-records"),
        ("GET", "/api/v1/investigations/{investigation_id:int}"),
        ("GET", "/api/v1/investigations/{investigation_id:int}/closure-validation"),
        ("GET", "/api/v1/investigations/{investigation_id:int}/comments"),
        ("GET", "/api/v1/investigations/{investigation_id:int}/packs"),
        ("GET", "/api/v1/investigations/{investigation_id:int}/packs/{pack_id:int}/pdf"),
        ("GET", "/api/v1/investigations/{investigation_id:int}/timeline"),
        # src.api.routes.iso27001
        ("GET", "/api/v1/iso27001/access-control"),
        ("GET", "/api/v1/iso27001/assets"),
        ("GET", "/api/v1/iso27001/assets/{asset_id}"),
        ("GET", "/api/v1/iso27001/business-continuity"),
        ("GET", "/api/v1/iso27001/business-continuity/{plan_id}"),
        ("GET", "/api/v1/iso27001/controls"),
        ("GET", "/api/v1/iso27001/dashboard"),
        ("GET", "/api/v1/iso27001/incidents"),
        ("GET", "/api/v1/iso27001/incidents/{incident_id}"),
        ("GET", "/api/v1/iso27001/risks"),
        ("GET", "/api/v1/iso27001/risks/{risk_id}"),
        ("GET", "/api/v1/iso27001/soa"),
        ("GET", "/api/v1/iso27001/suppliers"),
        ("GET", "/api/v1/iso27001/suppliers/{supplier_id}"),
        # src.api.routes.kri
        ("GET", "/api/v1/kri"),
        ("GET", "/api/v1/kri/alerts/pending"),
        ("GET", "/api/v1/kri/dashboard"),
        ("GET", "/api/v1/kri/incidents/{incident_id}/sif-assessment"),
        ("GET", "/api/v1/kri/risks/{risk_id}/trend"),
        ("GET", "/api/v1/kri/{kri_id}"),
        ("GET", "/api/v1/kri/{kri_id}/measurements"),
        # src.api.routes.loler_inspections
        ("GET", "/api/v1/assets/{asset_id}/inspection-history"),
        # src.api.routes.near_miss
        ("POST", "/api/v1/near-misses/{near_miss_id}/running-sheet"),
        ("DELETE", "/api/v1/near-misses/{near_miss_id}/running-sheet/{entry_id}"),
        # src.api.routes.notifications
        ("GET", "/api/v1/notifications/"),
        ("GET", "/api/v1/notifications/mentions/search"),
        ("GET", "/api/v1/notifications/preferences"),
        ("GET", "/api/v1/notifications/unread-count"),
        # src.api.routes.ocr_ops
        ("POST", "/api/v1/health/meta/ocr-artifacts/ack"),
        ("POST", "/api/v1/health/meta/ocr-artifacts/dispute"),
        ("POST", "/api/v1/meta/ocr-artifacts/ack"),
        ("POST", "/api/v1/meta/ocr-artifacts/dispute"),
        # src.api.routes.partner_webhooks
        ("GET", "/api/v1/partner-webhooks/deliveries"),
        ("GET", "/api/v1/partner-webhooks/events"),
        ("GET", "/api/v1/partner-webhooks/subscriptions"),
        ("GET", "/api/v1/partner-webhooks/subscriptions/{subscription_id}"),
        # src.api.routes.planet_mark
        ("GET", "/api/v1/planet-mark/dashboard"),
        ("GET", "/api/v1/planet-mark/import-status/{import_job_id}"),
        ("GET", "/api/v1/planet-mark/iso14001-mapping"),
        ("GET", "/api/v1/planet-mark/years"),
        ("GET", "/api/v1/planet-mark/years/{year_id}"),
        ("GET", "/api/v1/planet-mark/years/{year_id}/actions"),
        ("GET", "/api/v1/planet-mark/years/{year_id}/actions/summary"),
        ("GET", "/api/v1/planet-mark/years/{year_id}/certification"),
        ("GET", "/api/v1/planet-mark/years/{year_id}/data-quality"),
        ("GET", "/api/v1/planet-mark/years/{year_id}/evidence"),
        ("GET", "/api/v1/planet-mark/years/{year_id}/evidence/{evidence_id}/download"),
        ("GET", "/api/v1/planet-mark/years/{year_id}/export"),
        ("GET", "/api/v1/planet-mark/years/{year_id}/fleet/summary"),
        ("GET", "/api/v1/planet-mark/years/{year_id}/scope3"),
        ("GET", "/api/v1/planet-mark/years/{year_id}/sources"),
        # src.api.routes.policies
        ("GET", "/api/v1/policies"),
        ("GET", "/api/v1/policies/{policy_id}"),
        # src.api.routes.policy_acknowledgment
        ("GET", "/api/v1/policy-acknowledgments/dashboard"),
        ("GET", "/api/v1/policy-acknowledgments/my-pending"),
        ("GET", "/api/v1/policy-acknowledgments/policies/{policy_id}/status"),
        ("POST", "/api/v1/policy-acknowledgments/read-logs"),
        ("GET", "/api/v1/policy-acknowledgments/read-logs/document/{document_type}/{document_id}"),
        ("GET", "/api/v1/policy-acknowledgments/read-logs/user/{user_id}"),
        ("GET", "/api/v1/policy-acknowledgments/reminders-needed"),
        ("GET", "/api/v1/policy-acknowledgments/requirements/{requirement_id}"),
        ("GET", "/api/v1/policy-acknowledgments/{acknowledgment_id}"),
        ("POST", "/api/v1/policy-acknowledgments/{acknowledgment_id}/acknowledge"),
        ("POST", "/api/v1/policy-acknowledgments/{acknowledgment_id}/open"),
        ("POST", "/api/v1/policy-acknowledgments/{acknowledgment_id}/reading-time"),
        # src.api.routes.portal_compliance
        ("GET", "/api/v1/portal/drivers/me"),
        ("GET", "/api/v1/portal/my-compliance"),
        ("GET", "/api/v1/portal/my-tools"),
        ("GET", "/api/v1/portal/my-van"),
        # src.api.routes.push_notifications
        ("GET", "/api/v1/notifications/push/preferences"),
        ("PUT", "/api/v1/notifications/push/preferences"),
        ("POST", "/api/v1/notifications/push/subscribe"),
        ("GET", "/api/v1/notifications/push/test"),
        ("DELETE", "/api/v1/notifications/push/unsubscribe"),
        # src.api.routes.rca_tools
        ("GET", "/api/v1/rca-tools/capa/investigation/{investigation_id}"),
        ("GET", "/api/v1/rca-tools/capa/overdue"),
        ("GET", "/api/v1/rca-tools/fishbone/{diagram_id}"),
        ("GET", "/api/v1/rca-tools/five-whys/entity/{entity_type}/{entity_id}"),
        ("GET", "/api/v1/rca-tools/five-whys/{analysis_id}"),
        # src.api.routes.realtime
        ("GET", "/api/v1/realtime/online-users"),
        ("GET", "/api/v1/realtime/presence/{user_id}"),
        ("GET", "/api/v1/realtime/stats"),
        # src.api.routes.risk_register
        ("GET", "/api/v1/risk-register"),
        ("GET", "/api/v1/risk-register/"),
        ("GET", "/api/v1/risk-register/appetite/statements"),
        ("GET", "/api/v1/risk-register/controls"),
        ("GET", "/api/v1/risk-register/forecast"),
        ("GET", "/api/v1/risk-register/heatmap"),
        ("GET", "/api/v1/risk-register/kris/dashboard"),
        ("GET", "/api/v1/risk-register/kris/{kri_id}/history"),
        ("GET", "/api/v1/risk-register/matrix/config"),
        ("GET", "/api/v1/risk-register/summary"),
        ("GET", "/api/v1/risk-register/trends"),
        ("GET", "/api/v1/risk-register/{risk_id}"),
        ("GET", "/api/v1/risk-register/{risk_id}/actions"),
        ("GET", "/api/v1/risk-register/{risk_id}/activity"),
        ("GET", "/api/v1/risk-register/{risk_id}/bowtie"),
        ("GET", "/api/v1/risk-register/{risk_id}/notes"),
        ("GET", "/api/v1/risk-register/{risk_id}/profile"),
        ("GET", "/api/v1/risk-register/{risk_id}/upstream"),
        # src.api.routes.risks
        ("GET", "/api/v1/risks"),
        ("GET", "/api/v1/risks/"),
        ("DELETE", "/api/v1/risks/controls/{control_id}"),
        ("PATCH", "/api/v1/risks/controls/{control_id}"),
        ("GET", "/api/v1/risks/matrix"),
        ("GET", "/api/v1/risks/statistics"),
        ("GET", "/api/v1/risks/{risk_id}"),
        ("GET", "/api/v1/risks/{risk_id}/assessments"),
        ("POST", "/api/v1/risks/{risk_id}/assessments"),
        ("GET", "/api/v1/risks/{risk_id}/assessments/paged"),
        ("GET", "/api/v1/risks/{risk_id}/controls"),
        ("POST", "/api/v1/risks/{risk_id}/controls"),
        # src.api.routes.rtas
        ("GET", "/api/v1/rtas/"),
        ("GET", "/api/v1/rtas/{rta_id}"),
        ("GET", "/api/v1/rtas/{rta_id}/actions"),
        ("GET", "/api/v1/rtas/{rta_id}/investigations"),
        ("GET", "/api/v1/rtas/{rta_id}/running-sheet"),
        ("POST", "/api/v1/rtas/{rta_id}/running-sheet"),
        ("DELETE", "/api/v1/rtas/{rta_id}/running-sheet/{entry_id}"),
        # src.api.routes.safety_insights
        ("GET", "/api/v1/safety-insights/latest"),
        ("GET", "/api/v1/safety-insights/runs"),
        ("GET", "/api/v1/safety-insights/runs/{run_id}"),
        ("POST", "/api/v1/safety-insights/runs/{run_id}/export"),
        ("GET", "/api/v1/safety-insights/themes/{theme_id}/cases"),
        # src.api.routes.signatures
        ("GET", "/api/v1/signatures/requests"),
        ("GET", "/api/v1/signatures/requests/pending"),
        ("GET", "/api/v1/signatures/requests/{request_id}"),
        ("GET", "/api/v1/signatures/requests/{request_id}/audit-log"),
        ("GET", "/api/v1/signatures/stats"),
        ("GET", "/api/v1/signatures/templates"),
        # src.api.routes.standards
        ("GET", "/api/v1/standards"),
        ("GET", "/api/v1/standards/"),
        ("GET", "/api/v1/standards/clauses/{clause_id}"),
        ("GET", "/api/v1/standards/controls/{control_id}"),
        ("GET", "/api/v1/standards/{standard_id}"),
        ("GET", "/api/v1/standards/{standard_id}/clauses"),
        ("GET", "/api/v1/standards/{standard_id}/compliance-score"),
        ("GET", "/api/v1/standards/{standard_id}/controls"),
        # src.api.routes.telemetry
        ("DELETE", "/api/v1/telemetry/metrics/{experiment_id}"),
        ("GET", "/api/v1/telemetry/metrics/{experiment_id}"),
        # src.api.routes.tenants
        ("GET", "/api/v1/tenants/current"),
        ("POST", "/api/v1/tenants/invitations/{token}/accept"),
        ("GET", "/api/v1/tenants/{tenant_id}"),
        ("GET", "/api/v1/tenants/{tenant_id}/features"),
        ("GET", "/api/v1/tenants/{tenant_id}/limits"),
        ("GET", "/api/v1/tenants/{tenant_id}/users"),
        # src.api.routes.training_matrix
        ("GET", "/api/v1/training-matrix/compliance"),
        ("GET", "/api/v1/training-matrix/courses"),
        ("POST", "/api/v1/training-matrix/imports"),
        ("GET", "/api/v1/training-matrix/imports/latest"),
        ("GET", "/api/v1/training-matrix/imports/latest/qa"),
        ("GET", "/api/v1/training-matrix/me"),
        ("GET", "/api/v1/training-matrix/name-maps"),
        ("PUT", "/api/v1/training-matrix/name-maps"),
        ("POST", "/api/v1/training-matrix/name-maps/auto-match"),
        ("POST", "/api/v1/training-matrix/notify"),
        ("PATCH", "/api/v1/training-matrix/people/{person_id}"),
        ("GET", "/api/v1/training-matrix/people/{person_id}/compliance"),
        ("GET", "/api/v1/training-matrix/requirements"),
        ("POST", "/api/v1/training-matrix/requirements"),
        ("POST", "/api/v1/training-matrix/requirements/matrix"),
        ("GET", "/api/v1/training-matrix/requirements/matrix/proposals"),
        ("POST", "/api/v1/training-matrix/requirements/matrix/proposals/{proposal_id}/approve"),
        ("POST", "/api/v1/training-matrix/requirements/matrix/proposals/{proposal_id}/reject"),
        ("POST", "/api/v1/training-matrix/requirements/matrix/propose"),
        ("POST", "/api/v1/training-matrix/requirements/seed"),
        ("DELETE", "/api/v1/training-matrix/requirements/{requirement_id}"),
        ("PATCH", "/api/v1/training-matrix/requirements/{requirement_id}"),
        ("GET", "/api/v1/training-matrix/summary"),
        # src.api.routes.training_tickets
        ("GET", "/api/v1/training-tickets/"),
        ("GET", "/api/v1/training-tickets/{ticket_id}"),
        # src.api.routes.users
        ("GET", "/api/v1/users/me"),
        ("GET", "/api/v1/users/roles/"),
        ("GET", "/api/v1/users/search/"),
        ("GET", "/api/v1/users/{user_id}"),
        # src.api.routes.uvdb
        ("GET", "/api/v1/uvdb/audits"),
        ("GET", "/api/v1/uvdb/audits/{audit_id}"),
        ("GET", "/api/v1/uvdb/audits/{audit_id}/kpis"),
        ("GET", "/api/v1/uvdb/audits/{audit_id}/responses"),
        ("GET", "/api/v1/uvdb/dashboard"),
        ("GET", "/api/v1/uvdb/iso-mapping"),
        ("GET", "/api/v1/uvdb/protocol"),
        ("GET", "/api/v1/uvdb/protocol/export"),
        ("GET", "/api/v1/uvdb/sections"),
        ("GET", "/api/v1/uvdb/sections/scores"),
        ("GET", "/api/v1/uvdb/sections/{section_number}/questions"),
        # src.api.routes.vehicle_checklist_analytics
        ("GET", "/api/v1/vehicle-checklists/analytics/export/daily"),
        ("GET", "/api/v1/vehicle-checklists/analytics/export/defects"),
        ("GET", "/api/v1/vehicle-checklists/analytics/export/monthly"),
        ("GET", "/api/v1/vehicle-checklists/analytics/heatmap"),
        ("GET", "/api/v1/vehicle-checklists/analytics/summary"),
        ("GET", "/api/v1/vehicle-checklists/analytics/trends"),
        # src.api.routes.vehicle_checklists
        ("GET", "/api/v1/vehicle-checklists/daily"),
        ("GET", "/api/v1/vehicle-checklists/daily/{record_id}"),
        ("GET", "/api/v1/vehicle-checklists/defects"),
        ("GET", "/api/v1/vehicle-checklists/defects/{defect_id}"),
        ("GET", "/api/v1/vehicle-checklists/monthly"),
        ("GET", "/api/v1/vehicle-checklists/monthly/{record_id}"),
        ("GET", "/api/v1/vehicle-checklists/schema"),
        # src.api.routes.vehicles
        ("GET", "/api/v1/vehicles/"),
        ("GET", "/api/v1/vehicles/analytics/fleet-health"),
        ("GET", "/api/v1/vehicles/me/status"),
        ("GET", "/api/v1/vehicles/{reg}"),
        ("GET", "/api/v1/vehicles/{reg}/compliance"),
        ("GET", "/api/v1/vehicles/{reg}/safety-assets"),
        # src.api.routes.wdp_analytics
        ("GET", "/api/v1/wdp-analytics/engineer-matrix"),
        ("GET", "/api/v1/wdp-analytics/summary"),
        ("GET", "/api/v1/wdp-analytics/trends"),
        # src.api.routes.workflow
        ("GET", "/api/v1/workflow/escalation-levels"),
        ("GET", "/api/v1/workflow/escalation-levels/{level_id}"),
        ("GET", "/api/v1/workflow/rules"),
        ("GET", "/api/v1/workflow/rules/{rule_id}"),
        ("GET", "/api/v1/workflow/rules/{rule_id}/executions"),
        ("GET", "/api/v1/workflow/sla-configs"),
        ("GET", "/api/v1/workflow/sla-configs/{config_id}"),
        ("GET", "/api/v1/workflow/sla-status/{entity_type}/{entity_id}"),
        # src.api.routes.workflows
        ("GET", "/api/v1/workflows/approvals/pending"),
        ("GET", "/api/v1/workflows/delegations"),
        ("GET", "/api/v1/workflows/escalations/pending"),
        ("GET", "/api/v1/workflows/instances"),
        ("GET", "/api/v1/workflows/instances/{workflow_id}"),
        ("GET", "/api/v1/workflows/routing-rules/{entity_type}"),
        ("GET", "/api/v1/workflows/stats"),
        ("GET", "/api/v1/workflows/templates"),
        ("GET", "/api/v1/workflows/templates/{template_code}"),
        # src.api.routes.workforce_competence_gaps
        ("GET", "/api/v1/workforce/competence-gaps"),
        ("GET", "/api/v1/workforce/competence-gaps/{gap_id}"),
        ("GET", "/api/v1/workforce/competence-gaps/{gap_id}/golden-thread"),
    }
)

#: Ceilings, recorded when the gap was measured against the mounted app. The
#: census test refuses a total above either one.
#:
#: These exist so that the cheapest response to a failing census test is not
#: "add my new route to the list". Lowering one is ordinary progress; raising one
#: is a deliberate decision that a reviewer sees as a changed number in a file
#: about unprotected endpoints.
MAX_AUTHENTICATED_ONLY_DEBT: int = 474
MAX_PUBLIC_BY_DESIGN: int = 50

#: Endpoints gated on ``CurrentSuperuser`` rather than on a named permission,
#: counted when the gap was measured.
#:
#: Ceilinged for a different reason from the two above. Superuser-only is a real
#: authorisation check, so closing the gap by converting endpoints to it would
#: make the census look fixed while making the product usable only by the one
#: account that bypasses every permission — and ``User.has_permission`` returns
#: ``True`` for a superuser before it reads any role, so a superuser gate cannot
#: be narrowed later by editing a role. Raising this is a decision to shrink who
#: can use a feature to the people who can already do everything.
MAX_SUPERUSER_ONLY: int = 29

#: Every endpoint a human has accounted for.
DECLARED_ENDPOINTS: frozenset[EndpointKey] = frozenset(PUBLIC_BY_DESIGN) | AUTHENTICATED_ONLY_DEBT


__all__ = [
    "AUTHENTICATED_ONLY_DEBT",
    "DECLARED_ENDPOINTS",
    "EndpointKey",
    "MAX_AUTHENTICATED_ONLY_DEBT",
    "MAX_PUBLIC_BY_DESIGN",
    "MAX_SUPERUSER_ONLY",
    "PUBLIC_BY_DESIGN",
]
