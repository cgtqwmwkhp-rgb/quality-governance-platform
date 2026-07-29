"""Census of delete cascades, by whether an ORM hook can observe them.

Read-only analysis helper for finding C-30. Touches no database: it reflects on
the SQLAlchemy metadata that the application itself declares.

The distinction that matters for audit coverage:

  * ORM-visible cascade -- a mapped relationship with ``delete`` in its cascade
    and ``passive_deletes`` not set to True. SQLAlchemy loads the children and
    issues one DELETE per child, so a ``before_delete`` / ``after_delete`` event
    fires for each one and the audit hook sees it.

  * DB-only cascade -- a ``ForeignKey(..., ondelete="CASCADE")`` where either no
    relationship is mapped from the parent, or the relationship sets
    ``passive_deletes=True``. PostgreSQL removes the child rows itself; no
    Python event fires and an application-layer hook is blind to it.

Usage:
    python scripts/analysis/scan_cascades.py
"""

from __future__ import annotations

import sys
from collections import defaultdict

from sqlalchemy.orm import configure_mappers

import src.main  # noqa: F401  -- registers exactly the models the app loads
from src.domain.models.base import Base

# Importing src.main rather than src.domain.models is deliberate: the package's
# re-exports alone under-count the cascade graph, while a blanket import of every
# module under src/domain/models over-counts it with tables the app never loads
# (and declares a duplicate AuditTemplate, on which configure_mappers() fails).
# tests/unit/test_delete_cascade_audit_visibility.py asserts the same census, so
# the two must agree.


def main() -> int:
    configure_mappers()
    metadata = Base.metadata

    # --- FK-level: which child tables does the DB cascade-delete? -------
    db_cascade: dict[str, list[str]] = defaultdict(list)  # parent table -> child cols
    for table in metadata.tables.values():
        for fk in table.foreign_keys:
            if (fk.ondelete or "").upper() == "CASCADE":
                db_cascade[fk.column.table.name].append(f"{table.name}.{fk.parent.name}")

    # --- ORM-level: which relationships delete children in Python? ------
    orm_cascade: dict[str, list[tuple[str, str, bool]]] = defaultdict(list)
    for mapper in Base.registry.mappers:
        parent_table = mapper.local_table.name if mapper.local_table is not None else mapper.class_.__name__
        for rel in mapper.relationships:
            if not rel.cascade.delete:
                continue
            target = rel.target.name
            orm_cascade[parent_table].append((rel.key, target, bool(rel.passive_deletes)))

    orm_covered: set[tuple[str, str]] = {
        (parent, target) for parent, rels in orm_cascade.items() for _key, target, passive in rels if not passive
    }

    all_parents = sorted(set(db_cascade) | set(orm_cascade))

    print("=" * 78)
    print("CASCADE CENSUS")
    print("=" * 78)
    print(f"tables in metadata                     : {len(metadata.tables)}")
    print(f"parent tables with a CASCADE dependency: {len(all_parents)}")
    print(f"DB-level ON DELETE CASCADE foreign keys : {sum(len(v) for v in db_cascade.values())}")
    print(f"ORM relationships with delete cascade   : {sum(len(v) for v in orm_cascade.values())}")
    print()

    blind: list[tuple[str, str]] = []
    for parent in all_parents:
        children_db = sorted(db_cascade.get(parent, []))
        rels = sorted(orm_cascade.get(parent, []))
        for child_col in children_db:
            child_table = child_col.split(".")[0]
            if (parent, child_table) not in orm_covered:
                blind.append((parent, child_table))

    print("DB-only cascades an ORM event hook CANNOT observe")
    print("(parent -> child removed by PostgreSQL with no Python event):")
    if not blind:
        print("  none")
    for parent, child in sorted(set(blind)):
        print(f"  {parent:<34} -> {child}")
    print(f"\n  distinct blind parent/child pairs: {len(set(blind))}")
    print()

    print("ORM-visible delete cascades (hook sees one event per child row):")
    total_visible = 0
    for parent in sorted(orm_cascade):
        for key, target, passive in sorted(orm_cascade[parent]):
            if passive:
                continue
            total_visible += 1
            print(f"  {parent:<34} -> {target:<34} (.{key})")
    print(f"\n  total: {total_visible}")
    print()

    print("Relationships that declare delete cascade AND passive_deletes=True")
    print("(SQLAlchemy defers to the DB, so no per-child event fires):")
    passive_any = False
    for parent in sorted(orm_cascade):
        for key, target, passive in sorted(orm_cascade[parent]):
            if passive:
                passive_any = True
                print(f"  {parent:<34} -> {target:<34} (.{key})")
    if not passive_any:
        print("  none")
    print()

    # --- focused: the case registers named in the finding ---------------
    print("=" * 78)
    print("FOCUS: case-register parents named in C-30")
    print("=" * 78)
    for parent in ("incidents", "near_misses", "risks", "complaints", "road_traffic_collisions", "audit_runs"):
        if parent not in metadata.tables:
            print(f"{parent}: NOT IN METADATA")
            continue
        children_db = sorted({c.split(".")[0] for c in db_cascade.get(parent, [])})
        visible = sorted({t for _k, t, p in orm_cascade.get(parent, []) if not p})
        print(f"\n{parent}:")
        print(f"  DB cascade children ({len(children_db)}): {children_db}")
        print(f"  ORM-visible children ({len(visible)}): {visible}")
        invisible = sorted(set(children_db) - set(visible))
        print(f"  BLIND to an ORM hook ({len(invisible)}): {invisible}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
