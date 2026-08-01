"""Third-party AI provider disclosure SSOT (UK GDPR Art. 28 / Art. 30).

The published sub-processor register drifted out of step with production because
nothing tied *provider enablement* to *provider disclosure*: credentials were
added to configuration and Key Vault while the register kept naming three
processors.

This module is the join between those two facts. Every configuration input that
lets application code reach a third-party AI provider is declared here against
the name that provider must appear under in
``src.api.routes.privacy._subprocessors()``.

Two invariants are enforced by ``tests/unit/test_ai_provider_disclosure.py``:

1. Every provider declared here has a register entry — so a provider cannot be
   wired up in code and left out of the published register.
2. Every provider-credential field on ``Settings`` is claimed by a provider here
   (or explicitly recorded as not a processor credential) — so adding
   ``some_vendor_api_key`` to configuration fails the build until the vendor is
   disclosed.

No secret values are read, logged or returned by this module: it reports only
whether a credential is *present*.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Mapping

# ---------------------------------------------------------------------------
# Retention posture vocabulary (Art. 30(1)(f) — storage / retention periods)
# ---------------------------------------------------------------------------

#: Provider receives content, returns a result, and is not configured by this
#: platform to store it. Vendor-side retention terms are a contractual question
#: this repository cannot answer.
TRANSIENT_PROCESSING = "transient_processing_only"

#: Provider *stores* content (or content-derived data) that this platform writes
#: to it and must later delete. A persistent transfer, not a transient one.
RETAINS_CONTENT = "retains_content_until_deleted_by_platform"

#: Primary platform hosting (database, blob, logs) rather than an AI recipient.
HOSTS_PLATFORM_DATA = "hosts_platform_data"

#: Value used wherever the repository does not establish a fact. Never replaced
#: with a lawful-sounding guess.
UNKNOWN = "unknown_not_established_in_repository"


@dataclass(frozen=True)
class ProviderCredential:
    """One configuration input that lets code reach a provider.

    ``env_vars`` records the environment variables read *directly* by service
    code (several services fall back to ``os.getenv`` rather than ``Settings``),
    so presence detection matches what the services actually see.
    """

    settings_field: str
    env_vars: tuple[str, ...] = ()
    required: bool = True

    def is_present(self, settings_obj: Any, environ: Mapping[str, str]) -> bool:
        value = getattr(settings_obj, self.settings_field, None)
        if isinstance(value, str) and value.strip():
            return True
        if isinstance(value, bool) and value:
            return True
        return any((environ.get(env_var) or "").strip() for env_var in self.env_vars)


@dataclass(frozen=True)
class AIProvider:
    """A third-party AI provider reachable from application code."""

    register_name: str
    role: str
    retention_posture: str
    credentials: tuple[ProviderCredential, ...]
    code_paths: tuple[str, ...]

    @property
    def retains_content(self) -> bool:
        return self.retention_posture == RETAINS_CONTENT

    @property
    def config_fields(self) -> frozenset[str]:
        return frozenset(credential.settings_field for credential in self.credentials)

    def is_credentialed(self, settings_obj: Any, environ: Mapping[str, str]) -> bool:
        """True when every *required* credential for this provider is present."""
        required = [credential for credential in self.credentials if credential.required]
        return bool(required) and all(credential.is_present(settings_obj, environ) for credential in required)


AI_PROVIDERS: tuple[AIProvider, ...] = (
    AIProvider(
        register_name="Mistral AI",
        role="ai_ocr_processor",
        retention_posture=TRANSIENT_PROCESSING,
        credentials=(ProviderCredential("mistral_api_key", ("MISTRAL_API_KEY",)),),
        code_paths=(
            "src/domain/services/mistral_ocr_service.py",
            "src/domain/services/mistral_analysis_service.py",
            "src/domain/services/document_intelligence_service.py",
        ),
    ),
    AIProvider(
        register_name="Google Gemini",
        role="ai_review_processor",
        retention_posture=TRANSIENT_PROCESSING,
        credentials=(ProviderCredential("google_gemini_api_key", ("GOOGLE_GEMINI_API_KEY", "GEMINI_API_KEY")),),
        code_paths=("src/domain/services/gemini_review_service.py",),
    ),
    AIProvider(
        register_name="Azure AI Document Intelligence",
        role="ai_ocr_processor",
        retention_posture=TRANSIENT_PROCESSING,
        credentials=(
            ProviderCredential(
                "azure_document_intelligence_endpoint",
                ("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT",),
            ),
            ProviderCredential(
                "azure_document_intelligence_key",
                ("AZURE_DOCUMENT_INTELLIGENCE_KEY",),
            ),
            ProviderCredential(
                "azure_document_intelligence_enable_prod",
                ("AZURE_DOCUMENT_INTELLIGENCE_ENABLE_PROD",),
                required=False,
            ),
        ),
        code_paths=(
            "src/domain/services/azure_document_intelligence_service.py",
            "src/domain/services/document_intelligence_service.py",
        ),
    ),
    AIProvider(
        register_name="Anthropic",
        role="ai_analysis_processor",
        retention_posture=TRANSIENT_PROCESSING,
        credentials=(ProviderCredential("anthropic_api_key", ("ANTHROPIC_API_KEY",)),),
        code_paths=(
            "src/domain/services/document_ai_service.py",
            "src/domain/services/governed_knowledge_service.py",
            "src/domain/services/ai_models.py",
            "src/domain/services/ai_predictive_service.py",
            "src/domain/services/safety_insights_analyst.py",
            "src/domain/services/audit_challenge_pipeline.py",
            "src/domain/services/audit_builder_generation_pipeline.py",
            "src/domain/services/iso_compliance_service.py",
            "src/domain/services/copilot_grounding.py",
        ),
    ),
    AIProvider(
        register_name="OpenAI",
        role="ai_analysis_processor",
        retention_posture=TRANSIENT_PROCESSING,
        credentials=(ProviderCredential("openai_api_key", ("OPENAI_API_KEY",)),),
        code_paths=(
            "src/domain/services/ai_models.py",
            "src/domain/services/document_ai_service.py",
            "src/domain/services/governed_knowledge_service.py",
            "src/domain/services/copilot_grounding.py",
        ),
    ),
    AIProvider(
        register_name="Voyage AI",
        role="ai_embedding_processor",
        retention_posture=TRANSIENT_PROCESSING,
        credentials=(ProviderCredential("voyage_api_key", ("VOYAGE_API_KEY",)),),
        code_paths=(
            "src/domain/services/document_ai_service.py",
            "src/domain/services/index_job_service.py",
        ),
    ),
    AIProvider(
        register_name="Pinecone",
        role="vector_database_processor",
        retention_posture=RETAINS_CONTENT,
        credentials=(
            ProviderCredential("pinecone_api_key", ("PINECONE_API_KEY",)),
            ProviderCredential("pinecone_host", ("PINECONE_HOST",), required=False),
            ProviderCredential("pinecone_index", ("PINECONE_INDEX",), required=False),
            ProviderCredential("pinecone_environment", ("PINECONE_ENVIRONMENT",), required=False),
        ),
        code_paths=(
            "src/domain/services/document_ai_service.py",
            "src/domain/services/index_job_service.py",
            "src/domain/services/document_library_disposal_service.py",
            "src/domain/services/governed_knowledge_service.py",
            "src/api/routes/documents.py",
        ),
    ),
    AIProvider(
        register_name="Genspark.ai",
        role="ai_analysis_processor",
        retention_posture=TRANSIENT_PROCESSING,
        credentials=(ProviderCredential("genspark_api_key", ("GENSPARK_API_KEY",)),),
        code_paths=("src/domain/services/ai_models.py",),
    ),
    AIProvider(
        register_name="Perplexity",
        role="ai_research_processor",
        retention_posture=TRANSIENT_PROCESSING,
        credentials=(ProviderCredential("perplexity_api_key", ("PERPLEXITY_API_KEY",)),),
        code_paths=(
            "src/domain/services/library_horizon_adapter.py",
            "src/domain/services/audit_builder_orchestrator.py",
        ),
    ),
)

#: Configuration-field name suffixes that mark a third-party provider credential.
PROVIDER_CREDENTIAL_SUFFIXES: tuple[str, ...] = ("_api_key",)

#: Provider configuration fields that do not end in a credential suffix but still
#: select or unlock a third-party recipient (endpoints, index/host targets, the
#: Azure DI production gate). Kept explicit so the coverage test can see them.
EXTRA_PROVIDER_CONFIG_FIELDS: frozenset[str] = frozenset(
    {
        "azure_document_intelligence_endpoint",
        "azure_document_intelligence_key",
        "azure_document_intelligence_enable_prod",
        "pinecone_host",
        "pinecone_index",
        "pinecone_environment",
    }
)

#: Fields that match the credential heuristic but are **not** a third-party AI
#: recipient. Each entry needs a reason, so silently excusing a new vendor is a
#: visible act rather than an omission.
NON_PROVIDER_CREDENTIAL_FIELDS: Mapping[str, str] = {}


def ai_providers() -> tuple[AIProvider, ...]:
    return AI_PROVIDERS


def provider_by_register_name(register_name: str) -> AIProvider | None:
    for provider in AI_PROVIDERS:
        if provider.register_name == register_name:
            return provider
    return None


def declared_provider_names() -> frozenset[str]:
    return frozenset(provider.register_name for provider in AI_PROVIDERS)


def claimed_config_fields() -> frozenset[str]:
    """Every ``Settings`` field claimed by a declared provider."""
    claimed: set[str] = set()
    for provider in AI_PROVIDERS:
        claimed |= provider.config_fields
    return frozenset(claimed)


def _resolve_settings(settings_obj: Any | None) -> Any:
    if settings_obj is not None:
        return settings_obj
    from src.core.config import get_settings

    return get_settings()


def credentialed_provider_names(
    settings_obj: Any | None = None,
    environ: Mapping[str, str] | None = None,
) -> frozenset[str]:
    """Providers whose required credentials are present in this environment.

    Reflects presence only — never a secret value — and reads the same
    ``Settings`` fields and environment variables the services read, so a
    provider that is reachable at runtime is reported here.
    """
    resolved_settings = _resolve_settings(settings_obj)
    resolved_environ = environ if environ is not None else os.environ
    return frozenset(
        provider.register_name
        for provider in AI_PROVIDERS
        if provider.is_credentialed(resolved_settings, resolved_environ)
    )


def undisclosed_credentialed_providers(
    register_names: frozenset[str] | set[str] | list[str],
    settings_obj: Any | None = None,
    environ: Mapping[str, str] | None = None,
) -> tuple[str, ...]:
    """Providers that are credentialed here but missing from the register.

    A non-empty result is a live Art. 30 disclosure gap: something can send
    personal data to a processor that the published register does not name.
    """
    present = credentialed_provider_names(settings_obj=settings_obj, environ=environ)
    return tuple(sorted(present - set(register_names)))


def undeclared_providers(register_names: frozenset[str] | set[str] | list[str]) -> tuple[str, ...]:
    """Declared providers with no register entry, regardless of credentials.

    This is the check that holds in CI, where no provider credentials exist.
    """
    return tuple(sorted(declared_provider_names() - set(register_names)))


def provider_credential_fields(settings_cls: Any | None = None) -> frozenset[str]:
    """Fields on ``Settings`` that look like a third-party provider credential."""
    if settings_cls is None:
        from src.core.config import Settings

        settings_cls = Settings
    fields = getattr(settings_cls, "model_fields", {}) or {}
    return frozenset(
        name for name in fields if name in EXTRA_PROVIDER_CONFIG_FIELDS or name.endswith(PROVIDER_CREDENTIAL_SUFFIXES)
    )


def unclaimed_provider_credential_fields(settings_cls: Any | None = None) -> tuple[str, ...]:
    """Credential-shaped settings fields that no declared provider claims."""
    candidates = provider_credential_fields(settings_cls)
    accounted = claimed_config_fields() | set(NON_PROVIDER_CREDENTIAL_FIELDS)
    return tuple(sorted(candidates - accounted))


__all__ = [
    "AI_PROVIDERS",
    "AIProvider",
    "EXTRA_PROVIDER_CONFIG_FIELDS",
    "HOSTS_PLATFORM_DATA",
    "NON_PROVIDER_CREDENTIAL_FIELDS",
    "PROVIDER_CREDENTIAL_SUFFIXES",
    "ProviderCredential",
    "RETAINS_CONTENT",
    "TRANSIENT_PROCESSING",
    "UNKNOWN",
    "ai_providers",
    "claimed_config_fields",
    "credentialed_provider_names",
    "declared_provider_names",
    "provider_by_register_name",
    "provider_credential_fields",
    "unclaimed_provider_credential_fields",
    "undeclared_providers",
    "undisclosed_credentialed_providers",
]
