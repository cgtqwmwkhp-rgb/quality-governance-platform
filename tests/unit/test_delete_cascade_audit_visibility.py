"""What the audit trail cannot see: deletes PostgreSQL performs on its own.

Threading tenant_id through ``record_audit_event`` (PX-155 / C-30) makes the
explicit, hand-written audit calls persist. It does nothing for children removed
by a database-level ``ON DELETE CASCADE``, and neither would the obvious
follow-up of adding a SQLAlchemy ``before_delete`` hook: when the parent's
children are deleted by PostgreSQL, no Python event fires, so a hook-based trail
would silently under-report exactly the bulk removals someone reading an audit
log most wants explained.

A child delete is observable to an ORM event hook only when SQLAlchemy itself
issues the per-row DELETE, which requires a mapped relationship whose cascade
includes ``delete`` and which does not set ``passive_deletes=True``. Every pair
below fails that test, so the removal happens with no Python event:

* 87 pairs have no relationship mapped from the parent at all.
* 5 have a relationship without ``delete`` in its cascade — SQLAlchemy will try
  to de-associate the children instead of deleting them, so still no per-child
  delete event (and on a NOT NULL foreign key that attempt errors).
* 0 currently set ``passive_deletes=True``. That is the third way to become
  invisible, so the assertion below pins it at zero rather than assuming it.

This inventory is a record, not a to-do list that has been done. It is asserted
exactly: adding a new ``ondelete="CASCADE"`` foreign key, or fixing one of these
by mapping a delete-cascading relationship, must update this list, so no one can
believe the audit trail covers a cascade that it does not.

The census reflects the model set the application actually loads — importing
``src.main`` is what makes that faithful. Modules under ``src/domain/models``
that nothing imports declare a further ~25 tables and a second ``AuditTemplate``
class, and registering those makes ``configure_mappers()`` fail outright, so
they are not part of the running schema and are excluded here.
"""

from __future__ import annotations

from collections import defaultdict

import pytest
from sqlalchemy.orm import configure_mappers

import src.main  # noqa: F401  -- registers exactly the models the app loads
from src.domain.models.base import Base

# (parent table, child table) removed by PostgreSQL with no Python event.
CASCADES_INVISIBLE_TO_AN_ORM_HOOK: frozenset[tuple[str, str]] = frozenset(
    {
        ("asset_types", "competency_requirements"),
        ("assets", "asset_assignment_events"),
        ("audit_challenge_sessions", "audit_challenge_proposals"),
        ("audit_challenge_sessions", "audit_challenge_turns"),
        ("audit_findings", "audit_finding_risks"),
        # AUD-F5 capture join. A link row says "this evidence answers this
        # question", so it cannot outlive the answer; deleting a run already
        # removes its answers, and this follows them. No relationship is mapped
        # from AuditResponse on purpose — a lazy collection hanging off an answer
        # row loads on any attribute touch outside a greenlet, which is the
        # MissingGreenlet failure AUD-F4 met on asyncpg — so PostgreSQL removes
        # the links with no per-row event. The evidence_assets side of the join
        # declares no ondelete at all, so it is not a cascade and is absent here:
        # a physical delete of cited evidence is refused instead.
        ("audit_responses", "audit_response_evidence"),
        ("audit_runs", "external_audit_import_drafts"),
        ("audit_runs", "external_audit_import_jobs"),
        ("audit_templates", "template_asset_types"),
        # CB-PR4 assessment binds. A bind is configuration pointing one template
        # at one PAMS characteristic, so it cannot outlive the template; no
        # relationship is mapped from AuditTemplate, and PostgreSQL removes the
        # bind on a physical template delete with no per-row event. The
        # demonstrations the bind produced carry no foreign key and survive as
        # history, which is the behaviour that matters for competence evidence.
        ("audit_templates", "competence_assessment_binds"),
        ("carbon_reporting_year", "carbon_evidence"),
        ("carbon_reporting_year", "carbon_improvement_action"),
        ("carbon_reporting_year", "data_quality_assessment"),
        ("carbon_reporting_year", "emission_source"),
        ("carbon_reporting_year", "fleet_emission_record"),
        ("carbon_reporting_year", "scope3_category_data"),
        ("carbon_reporting_year", "supplier_emission_data"),
        ("carbon_reporting_year", "utility_meter_reading"),
        ("competency_areas", "auditor_competencies"),
        ("complaints", "complaint_running_sheet_entries"),
        ("compliance_requirements", "compliance_schedule_ocr_drafts"),
        ("controlled_documents", "controlled_document_versions"),
        ("controlled_documents", "document_access_logs"),
        ("controlled_documents", "document_approval_instances"),
        ("controlled_documents", "document_distributions"),
        ("controlled_documents", "document_training_links"),
        ("controlled_documents", "obsolete_document_records"),
        ("dashboards", "dashboard_widgets"),
        ("document_approval_instances", "document_approval_actions"),
        ("document_approval_workflows", "document_approval_instances"),
        # ("document_categories", "pel_doc_ref_counters") was here until WA-2.
        # The counter now hangs off document_functions with ondelete=RESTRICT,
        # so deleting its parent is refused outright rather than silently
        # cascading — there is no longer an invisible delete to record.
        ("document_discussion_threads", "document_discussion_messages"),
        ("documents", "document_edges"),
        ("documents", "job_cell_documents"),
        ("documents", "library_document_access_logs"),
        ("documents", "library_review_packs"),
        ("driver_profiles", "driver_acknowledgements"),
        ("engineers", "onboarding_checklists"),
        ("engineers", "training_matrix_name_maps"),
        ("enterprise_risk_controls", "risk_control_mappings"),
        ("evidence_assets", "external_audit_import_jobs"),
        ("external_audit_import_jobs", "external_audit_import_drafts"),
        ("ims_controls", "ims_control_requirement_mappings"),
        ("ims_requirements", "cross_standard_mappings"),
        ("ims_requirements", "ims_control_requirement_mappings"),
        ("incidents", "incident_running_sheet_entries"),
        ("investigation_runs", "barrier_analyses"),
        ("investigation_runs", "fishbone_diagrams"),
        ("investigation_runs", "five_whys_analyses"),
        # Not a new cascade, a newly visible one. The physical constraint
        # soa_control_entry_control_id_fkey has been ON DELETE CASCADE since
        # 20260120_add_iso27001_isms; SoAControlEntry simply did not declare it,
        # so this census could not see it. 20260908_soa_align made the model say
        # what the database has always done, which is what surfaced the pair.
        ("iso27001_controls", "soa_control_entries"),
        # JL-1 (ADR-0022) axes. The cells and their document memberships are
        # derived structure, not authored records, so no relationship is mapped
        # from the axis parents and PostgreSQL removes them on its own. JL-3
        # cell links join that set for the same reason; their audit_run_id /
        # audit_finding_id parents are ON DELETE SET NULL, so those two do not
        # cascade and are absent here.
        #
        # ("job_types", "job_cell_links") is the JL-UX-W2 nesting target. It
        # cascades rather than nulling because a job_cycle link whose target
        # job type is gone cannot resolve an href — a nest link must not
        # outlive the cycle it points at. Job types are soft-deleted in normal
        # operation, so this fires only on a physical delete.
        ("job_cells", "job_cell_documents"),
        ("job_cells", "job_cell_links"),
        ("job_lanes", "job_cells"),
        ("job_steps", "job_cells"),
        ("job_types", "job_cell_links"),
        ("job_types", "job_cells"),
        ("job_types", "job_lanes"),
        ("job_types", "job_steps"),
        # JL-UX-W5 cycle baselines. Snapshots of the live tip; no ORM relationship
        # from JobType, so a physical job_types delete removes them via FK CASCADE
        # with no per-row audit event. Soft-delete is the normal path.
        ("job_types", "job_type_baselines"),
        # CB-PR5 coverage quotas. A quota is the duty "this site keeps two
        # appointed first aiders"; with the site gone the duty is meaningless,
        # so the foreign key cascades. No relationship is mapped from Location —
        # a quota is competence-board configuration, not part of the location
        # aggregate — so PostgreSQL removes it with no per-row event. Deleting a
        # location is not the normal path; retiring the obligation is.
        ("locations", "competence_coverage_quotas"),
        ("management_reviews", "management_review_inputs"),
        # WA-2 PR-C. Alignment edges are the derived output of a 5064 matrix
        # import, not authored records, so no relationship is mapped from the
        # version and PostgreSQL removes them on its own. Superseding is the
        # normal path — the import service marks the prior version superseded
        # and never deletes it — so this fires only on a physical delete such as
        # a tenant purge. Mapping a delete-cascading relationship would load
        # every edge of a version into memory to delete it a row at a time.
        ("matrix_versions", "alignment_edges"),
        ("near_misses", "near_miss_running_sheet_entries"),
        ("policies", "policy_acknowledgment_requirements"),
        ("policies", "policy_acknowledgments"),
        ("risks", "risk_score_history"),
        ("risks_v2", "audit_finding_risks"),
        ("risks_v2", "bow_tie_elements"),
        ("risks_v2", "case_risk_links"),
        ("risks_v2", "key_risk_indicators"),
        ("risks_v2", "risk_activity_events"),
        ("risks_v2", "risk_assessment_history"),
        ("risks_v2", "risk_control_mappings"),
        ("risks_v2", "risk_notes"),
        ("road_traffic_collisions", "rta_running_sheet_entries"),
        ("roles", "user_roles"),
        ("safety_insight_runs", "safety_insight_dimensions"),
        ("safety_insight_runs", "safety_insight_theme_cases"),
        ("safety_insight_runs", "safety_insight_themes"),
        ("safety_insight_themes", "safety_insight_theme_cases"),
        ("statement_of_applicability", "soa_control_entries"),
        ("training_matrix_courses", "training_matrix_cells"),
        ("training_matrix_imports", "training_matrix_cells"),
        ("training_matrix_people", "training_matrix_cells"),
        ("users", "auditor_profiles"),
        ("users", "campaign_assignments"),
        ("users", "document_read_logs"),
        ("users", "driver_profiles"),
        ("users", "engineer_group_members"),
        ("users", "policy_acknowledgments"),
        ("users", "user_roles"),
        ("uvdb_audit", "uvdb_audit_response"),
        ("uvdb_audit", "uvdb_kpi_record"),
        ("webhook_subscriptions", "webhook_delivery_logs"),
    }
)

# Case registers a user would expect a delete of to be explained in full.
CASE_REGISTER_TABLES = (
    "complaints",
    "incidents",
    "near_misses",
    "road_traffic_collisions",
    "audit_runs",
)


@pytest.fixture(scope="module")
def census() -> dict[str, object]:
    configure_mappers()
    metadata = Base.metadata

    db_cascade: dict[str, set[str]] = defaultdict(set)
    for table in metadata.tables.values():
        for fk in table.foreign_keys:
            if (fk.ondelete or "").upper() == "CASCADE":
                db_cascade[fk.column.table.name].add(table.name)

    orm_deletes: dict[str, set[str]] = defaultdict(set)
    passive: dict[str, set[str]] = defaultdict(set)
    for mapper in Base.registry.mappers:
        if mapper.local_table is None:
            continue
        for rel in mapper.relationships:
            if not rel.cascade.delete:
                continue
            target = passive if rel.passive_deletes else orm_deletes
            target[mapper.local_table.name].add(rel.target.name)

    invisible = {
        (parent, child)
        for parent, children in db_cascade.items()
        for child in children
        if child not in orm_deletes.get(parent, set())
    }
    return {
        "tables": metadata.tables,
        "db_cascade": db_cascade,
        "orm_deletes": orm_deletes,
        "passive": passive,
        "invisible": invisible,
    }


def test_the_census_reflects_a_fully_loaded_schema(census) -> None:
    """Guard against a vacuous pass from a half-registered model set."""
    assert len(census["tables"]) > 200, "models did not register; the census below would be meaningless"
    pairs = sum(len(children) for children in census["db_cascade"].values())
    assert pairs > 100, f"only {pairs} ON DELETE CASCADE foreign keys found; expected the full schema"


def test_db_level_cascades_are_recorded_as_outside_the_audit_trail(census) -> None:
    actual = census["invisible"]
    newly_invisible = sorted(actual - CASCADES_INVISIBLE_TO_AN_ORM_HOOK)
    now_visible = sorted(CASCADES_INVISIBLE_TO_AN_ORM_HOOK - actual)

    assert not newly_invisible, (
        f"new database-level cascade(s) with no audit coverage: {newly_invisible}. "
        "PostgreSQL will remove these children with no Python event, so no audit "
        "row is written for them. Add them to CASCADES_INVISIBLE_TO_AN_ORM_HOOK "
        "and to the audit-coverage statement, or map a delete-cascading "
        "relationship so the ORM issues the per-row deletes."
    )
    assert not now_visible, (
        f"{now_visible} are no longer invisible to an ORM hook. Remove them from "
        "CASCADES_INVISIBLE_TO_AN_ORM_HOOK so the record stays true."
    )


def test_no_relationship_hides_a_delete_behind_passive_deletes(census) -> None:
    """The third route to invisibility, pinned at zero rather than assumed."""
    passive = {(parent, child) for parent, children in census["passive"].items() for child in children}
    assert not passive, (
        f"{sorted(passive)} delete via passive_deletes=True, so SQLAlchemy defers "
        "to the database and no per-child event fires. Record them in "
        "CASCADES_INVISIBLE_TO_AN_ORM_HOOK."
    )


@pytest.mark.parametrize("parent", CASE_REGISTER_TABLES)
def test_case_register_children_removed_without_audit_are_enumerated(census, parent: str) -> None:
    """Deleting a case removes children the trail cannot account for.

    Named explicitly because these are the deletes this PR's own audit rows sit
    next to: the row says the case was deleted, and says nothing about the
    running-sheet entries or import jobs that went with it.
    """
    invisible_children = sorted(child for p, child in census["invisible"] if p == parent)
    assert invisible_children, f"{parent} unexpectedly has no uncovered cascade children"
    for child in invisible_children:
        assert (parent, child) in CASCADES_INVISIBLE_TO_AN_ORM_HOOK
