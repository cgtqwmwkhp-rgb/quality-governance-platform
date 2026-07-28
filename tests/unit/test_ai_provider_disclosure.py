"""Sub-processor disclosure invariants (UK GDPR Art. 28 / Art. 30(1)(d)).

The published register once named three sub-processors while production held
credentials for eight, because nothing connected provider *enablement* to
provider *disclosure*. Asserting today's list would drift the same way, so these
tests assert the join instead:

* every AI provider reachable from code is declared in the register;
* every provider-credential field on ``Settings`` is claimed by a declared
  provider, so adding a vendor credential fails until the vendor is disclosed;
* a provider whose credentials are present in the environment but missing from
  the register is reported as a disclosure gap.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from src.api.routes.privacy import _international_transfers, _subprocessors
from src.core.ai_provider_disclosure import (
    AI_PROVIDERS,
    RETAINS_CONTENT,
    TRANSIENT_PROCESSING,
    UNKNOWN,
    claimed_config_fields,
    credentialed_provider_names,
    declared_provider_names,
    provider_by_register_name,
    unclaimed_provider_credential_fields,
    undeclared_providers,
    undisclosed_credentialed_providers,
)
from src.core.config import Settings


class _FakeSettings:
    """Settings stand-in that reports only the credential fields it is given."""

    def __init__(self, **values: object) -> None:
        for field, value in values.items():
            setattr(self, field, value)


def _register_names() -> set[str]:
    return {row["name"] for row in _subprocessors()}


def test_every_declared_ai_provider_appears_in_the_register():
    missing = undeclared_providers(_register_names())
    assert missing == (), (
        "AI providers are reachable from code but absent from the published "
        f"sub-processor register: {missing}. Add a register entry in "
        "src/api/routes/privacy.py::_ai_subprocessor_entries()."
    )


def test_every_provider_credential_setting_is_claimed_by_a_declared_provider():
    unclaimed = unclaimed_provider_credential_fields(Settings)
    assert unclaimed == (), (
        f"Settings carries provider credentials that no declared provider claims: {unclaimed}. "
        "Declare the vendor in src/core/ai_provider_disclosure.py (and disclose it in the "
        "register), or record why the field is not a processor credential in "
        "NON_PROVIDER_CREDENTIAL_FIELDS."
    )


def test_every_api_key_environment_variable_in_source_belongs_to_a_declared_provider():
    """Closes the bypass where a provider is read straight from ``os.getenv``.

    Several services read credentials from the environment rather than
    ``Settings``, so a new vendor could be wired up with no settings field at all.
    This scans ``src/`` for ``*_API_KEY`` names and requires each to belong to a
    declared provider. It cannot catch a credential whose name breaks that
    convention — the settings-field check above is the second net.
    """
    source_root = Path(__file__).resolve().parents[2] / "src"
    pattern = re.compile(r"[A-Z][A-Z0-9_]*_API_KEY")
    found: set[str] = set()
    for path in source_root.rglob("*.py"):
        found |= set(pattern.findall(path.read_text(encoding="utf-8")))

    declared_env_vars = {
        env_var for provider in AI_PROVIDERS for credential in provider.credentials for env_var in credential.env_vars
    }
    undeclared = sorted(found - declared_env_vars)
    assert undeclared == [], (
        f"source reads provider credentials from the environment that no declared provider "
        f"claims: {undeclared}. Declare the vendor in src/core/ai_provider_disclosure.py and "
        "disclose it in the sub-processor register."
    )


def test_claimed_credential_fields_exist_on_settings():
    """Guards the inverse drift: a renamed setting silently stops being checked."""
    settings_fields = set(Settings.model_fields)
    stale = sorted(claimed_config_fields() - settings_fields)
    assert stale == [], f"ai_provider_disclosure claims settings fields that no longer exist: {stale}"


@pytest.mark.parametrize("provider", AI_PROVIDERS, ids=lambda provider: provider.register_name)
def test_provider_credentials_are_detected_and_disclosed(provider):
    """With this provider's credentials present, it must be a named sub-processor."""
    fake_settings = _FakeSettings(
        **{credential.settings_field: "present-not-a-real-value" for credential in provider.credentials}
    )
    detected = credentialed_provider_names(settings_obj=fake_settings, environ={})
    assert provider.register_name in detected

    gaps = undisclosed_credentialed_providers(_register_names(), settings_obj=fake_settings, environ={})
    assert gaps == (), f"{provider.register_name} is credentialed but not disclosed in the register"


@pytest.mark.parametrize("provider", AI_PROVIDERS, ids=lambda provider: provider.register_name)
def test_credentials_supplied_only_via_environment_are_detected(provider):
    """Several services read os.environ directly, so env-only keys must count."""
    environ = {
        env_var: "present-not-a-real-value"
        for credential in provider.credentials
        if credential.required
        for env_var in credential.env_vars
    }
    detected = credentialed_provider_names(settings_obj=_FakeSettings(), environ=environ)
    assert provider.register_name in detected


def test_disclosure_gap_is_reported_when_a_provider_is_removed_from_the_register():
    """The invariant itself must fail loudly — otherwise it guards nothing."""
    withheld = "Pinecone"
    fake_settings = _FakeSettings(pinecone_api_key="present-not-a-real-value")
    truncated = _register_names() - {withheld}

    assert undisclosed_credentialed_providers(truncated, settings_obj=fake_settings, environ={}) == (withheld,)
    assert withheld in undeclared_providers(truncated)


def test_all_provider_credentials_present_leaves_no_disclosure_gap():
    fake_settings = _FakeSettings(
        **{field: "present-not-a-real-value" for field in claimed_config_fields()},
    )
    assert credentialed_provider_names(settings_obj=fake_settings, environ={}) == declared_provider_names()
    assert undisclosed_credentialed_providers(_register_names(), settings_obj=fake_settings, environ={}) == ()


def test_register_entries_state_retention_posture():
    for row in _subprocessors():
        assert "retention_posture" in row, f"{row['name']} does not state a retention posture"
        assert isinstance(row["retains_content"], bool)
        assert row["retention_note"], f"{row['name']} has no retention note"


def test_pinecone_is_declared_as_retaining_document_content():
    pinecone = next(row for row in _subprocessors() if row["name"] == "Pinecone")

    assert pinecone["retention_posture"] == RETAINS_CONTENT
    assert pinecone["retains_content"] is True
    assert pinecone["retained_data"], "a retaining processor must enumerate what it holds"
    assert any("content_preview" in item for item in pinecone["retained_data"]), (
        "Pinecone metadata carries verbatim chunk previews — the register must say so, "
        "because 'only vectors' would understate the transfer"
    )
    assert pinecone["index_scope"] == "library_documents_table_only_not_case_register_records"
    assert pinecone["deletion_paths"]

    transfers = _international_transfers()
    assert "Pinecone" in transfers["retaining_subprocessors"]


def test_transient_ai_processors_are_not_marked_as_retaining():
    for row in _subprocessors():
        if row["retention_posture"] == TRANSIENT_PROCESSING:
            assert row["retains_content"] is False
            assert row["retained_data"] == []


def test_a_concrete_region_claim_must_cite_repository_evidence():
    """A confidently false region is worse than an admitted unknown.

    Every sub-processor either publishes ``regions == [UNKNOWN]`` — with the
    unknown recorded — or cites the document that establishes the region. There is
    no third option in which a lawful-sounding region appears unsourced.
    """
    for row in _subprocessors():
        if row["regions"] == [UNKNOWN]:
            assert "regions" in row["unknown_fields"], f"{row['name']} hides an unknown region"
            assert (
                row["transfer_mechanism"] == UNKNOWN
            ), f"{row['name']} cannot state a transfer mechanism while its region is unknown"
            continue
        assert row.get("region_evidence"), (
            f"{row['name']} claims regions {row['regions']} without citing the document that " "establishes them"
        )


def test_no_ai_processor_claims_a_uk_eea_mechanism_without_evidence():
    for row in _subprocessors():
        if row["transfer_mechanism"].startswith("uk_eea"):
            assert row.get("region_evidence"), f"{row['name']} claims UK/EEA transfer with no cited evidence"


def test_every_ai_register_entry_links_back_to_code_and_configuration():
    for row in _subprocessors():
        if not row["optional"]:
            continue
        provider = provider_by_register_name(row["name"])
        assert provider is not None, f"{row['name']} is in the register but not in the disclosure SSOT"
        assert row["credential_settings_fields"] == sorted(provider.config_fields)
        assert row["code_paths"], f"{row['name']} does not point at the code that transmits data"
        assert row["data_transmitted"], f"{row['name']} does not state what it receives"
        assert row["dpa_doc"]


def test_activation_status_distinguishes_confirmed_from_unconfirmed_providers():
    rows = {row["name"]: row for row in _subprocessors()}

    assert rows["Pinecone"]["activation"]["controller_confirmed"] is True
    assert rows["Azure AI Document Intelligence"]["activation"]["status"] == "active_in_production_e4_gate_closed"
    for name in ("Genspark.ai", "Perplexity"):
        assert rows[name]["activation"]["controller_confirmed"] is False
        assert rows[name]["activation"]["status"] == "code_path_present_activation_not_confirmed"


def test_register_activities_name_the_processors_that_receive_their_data():
    from src.api.routes.privacy import _processing_activities

    activities = {row["activity_id"]: row for row in _processing_activities()}
    register_names = _register_names()

    library_index = activities["library-document-index"]
    assert library_index["third_country_retention"] is True
    assert "Pinecone" in library_index["subprocessors"]
    assert "Voyage AI" in library_index["subprocessors"]

    for activity in activities.values():
        for name in activity.get("subprocessors", []):
            assert name in register_names, f"activity {activity['activity_id']} names undisclosed processor {name}"
