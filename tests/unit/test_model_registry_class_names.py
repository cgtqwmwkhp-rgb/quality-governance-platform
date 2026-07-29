"""No two mapped classes may share a name on one declarative base (C-69).

SQLAlchemy resolves string-form relationship targets — ``relationship("Role")`` —
by *class name* against the declarative registry. Two classes called ``Role``
(``src.domain.models.user.Role`` on ``roles``, and the ABAC role on
``abac_roles``) made every such reference ambiguous, and ``configure_mappers()``
raised ``Multiple classes found for path "Role"`` for *every* mapper in the
registry, not merely the two involved.

Two assertions, deliberately not one. The name check localises the defect: it
names the two colliding classes, which a mapper-configuration failure does not.
The ``configure_mappers()`` check states the property that actually matters and
would catch a misconfiguration arriving by some other route — it became possible
to assert at all only once the last two blockers were cleared (the duplicate
``Role`` here, and ``RootCauseAnalysis`` in #1429).

Scope: two module sets, deliberately both. The first is the set
``alembic/env.py`` imports — what Alembic compares and what the application can
reach. The second is every model file on disk, swept with ``pkgutil``.

The second exists because #1430 could only assert the first, and that left the
defect it was written to catch sitting one file away from it.
``src/domain/models/audit_template.py`` duplicated four names from ``audit.py``
(``AuditTemplate``, ``AuditRun``, ``AuditFinding``, ``AuditResponse``) and was
outside the import set, so these tests could not see it; it stayed harmless only
for as long as nobody wrote the import, and it differed from the live
``src.api.routes.audit_templates`` by one character. It was deleted for C-70. The
on-disk sweep is what makes the next one of those visible on the day it lands
rather than on the day someone imports it.
"""

from __future__ import annotations

from tests.unit._tenant_scope_support import (
    model_configure_mappers_result,
    model_mapped_class_names,
    on_disk_model_sweep,
)


def test_no_duplicate_mapped_class_names():
    duplicates = {name: sites for name, sites in model_mapped_class_names().items() if len(sites) > 1}
    assert not duplicates, (
        "Two mapped classes share a name on one declarative base, so every "
        'relationship("<name>") that targets it is ambiguous and configure_mappers() '
        f"raises for the entire registry: {duplicates}"
    )


def test_both_role_classes_are_present_and_distinctly_named():
    """Pin the fix itself: the ABAC role kept its table and gave up the name."""
    names = model_mapped_class_names()
    assert names.get("Role") == ["src.domain.models.user.Role -> roles"]
    assert names.get("ABACRole") == ["src.domain.models.permissions.ABACRole -> abac_roles"]


def test_full_model_set_configures_its_mappers():
    """The property the name check exists to protect."""
    result = model_configure_mappers_result()
    assert result["ok"], (
        "configure_mappers() failed on the full model set, so every ORM query in the "
        f"application is broken, not only the mapper named here: {result['error']}"
    )


def test_every_model_file_on_disk_can_be_imported():
    """Without this the sweep below could pass by seeing nothing.

    An unimportable module registers no classes, so it cannot collide with
    anything — and the duplicate-name check would report clean while being blind
    to whatever the module declares.
    """
    unimportable = on_disk_model_sweep()["unimportable"]
    assert not unimportable, (
        "these model modules raise on import, so the duplicate-name sweep below "
        f"cannot see the classes they declare: {unimportable}"
    )


def test_no_duplicate_mapped_class_names_across_every_model_file_on_disk():
    """C-70: the same defect, in a module the import set does not reach.

    A dormant collision is not a lesser one. It becomes live the moment anyone
    writes the import, and the failure it produces then names a mapper that has
    nothing to do with the module that was added.
    """
    names = on_disk_model_sweep()["names"]
    duplicates = {name: sites for name, sites in names.items() if len(sites) > 1}
    assert not duplicates, (
        "Two model files on disk declare a mapped class of the same name. Nothing "
        "need import them together today for this to be a defect: the first "
        'import that does makes every relationship("<name>") in the registry '
        f"ambiguous. Delete the unused declaration or rename it: {duplicates}"
    )


def test_the_on_disk_sweep_is_not_narrower_than_alembic_s_import_set():
    """Pins the widening itself, so the sweep cannot silently stop being wider.

    Both sets happen to be identical today — ``audit_template.py`` was the only
    model file on disk that ``alembic/env.py`` never reached, and it is gone. That
    is a fact about the tree right now, not a property, so what is asserted is the
    containment that must hold either way.
    """
    on_disk = set(on_disk_model_sweep()["names"])
    alembic_visible = set(model_mapped_class_names())

    assert on_disk >= alembic_visible, (
        "the on-disk sweep no longer sees every class the Alembic import set "
        "does, so it has become the weaker of the two checks: "
        f"{sorted(alembic_visible - on_disk)}"
    )


def test_every_model_file_on_disk_configures_its_mappers_together():
    """The C-70 property stated over the wider set.

    ``rta_analysis.py`` (deleted for C-14) declared a relationship against an
    attribute ``Incident`` did not have, and ``audit_template.py`` cross-wired a
    ``VARCHAR(36)`` foreign key to the live ``audit_templates.id``, an
    ``INTEGER``. Both were unreachable, so nothing failed; both would have taken
    the whole registry down on first import. This is the assertion that would have
    said so.
    """
    result = on_disk_model_sweep()["configured"]
    assert result["ok"], (
        "configure_mappers() fails once every model file on disk is imported "
        "together. The module at fault may be one nothing imports yet — that "
        "makes it dormant, not harmless, because the first import takes every "
        f"mapper in the registry with it: {result['error']}"
    )
