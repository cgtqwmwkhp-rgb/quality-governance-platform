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

Scope, so this suite is not read as more than it is: it covers the module set
``alembic/env.py`` imports, which is the set Alembic compares and the set the
application can reach. It is not every model file on disk.
``src/domain/models/audit_template.py`` is outside it and duplicates four names
from ``audit.py`` (``AuditTemplate``, ``AuditRun``, ``AuditFinding``,
``AuditResponse``); nothing imports that module, so the collision is latent and
these tests will not see it. Reported, not fixed here.
"""

from __future__ import annotations

from tests.unit._tenant_scope_support import model_configure_mappers_result, model_mapped_class_names


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
