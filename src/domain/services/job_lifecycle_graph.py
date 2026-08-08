"""Job Lifecycle graph model (JL-UX-W4) — one edge vocabulary, two views.

The process interaction **map** and the audit **trail** are two readings of the
same structure, so they share one node/edge model rather than each growing its
own shape. Both are projections: every node and edge here is derived on read
from ``job_cell_links`` / ``job_cell_documents`` / the axis tables. Nothing in
this module is persisted, and no ``job_*`` table gains a graph column — the
links a user can see and delete stay the only source of truth for nesting, and
the Library / Document Control record stays the only source of truth for a
document's standing.

Also home to cell **readiness**: whether a cell marked ``requires_evidence``
actually holds evidence. Readiness is classified, never stored, for the same
reason — a stored verdict would go stale the moment a document was withdrawn.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Optional, Sequence

#: Node kinds the map / trail can emit. ``job_type`` is the only kind the map
#: uses; the trail adds the things a cell actually points at.
JOB_GRAPH_NODE_KINDS: tuple[str, ...] = (
    "job_type",
    "cell",
    "document",
    "audit_finding",
    "app",
    "external",
)

#: Edge kinds. ``nests`` is the shared one: it is what the map draws between
#: job cycles and what the trail walks when a path leaves the pack.
JOB_GRAPH_EDGE_KINDS: tuple[str, ...] = (
    "nests",
    "contains",
    "evidences",
    "audits",
    "references",
)

#: Cell readiness states. ``unknown`` is a first-class answer — it means the
#: evidence exists but its standing could not be read, not that it is fine.
CELL_READINESS_STATES: tuple[str, ...] = (
    "not_required",
    "ready",
    "missing_evidence",
    "obsolete_evidence",
    "unknown",
)

#: Depth ceiling for a map walk. Nesting is guarded acyclic, so this is a cost
#: guard on a wide pack rather than a loop guard.
MAX_CYCLE_GRAPH_DEPTH = 5
DEFAULT_CYCLE_GRAPH_DEPTH = 2

#: Trail sampling ceiling. The trail is a *sample* path walk for an auditor,
#: not an export of the whole pack.
MAX_AUDIT_TRAIL_PATHS = 50
DEFAULT_AUDIT_TRAIL_PATHS = 10


def node_key(kind: str, ref_id: int) -> str:
    """Stable node identity. ``kind`` disambiguates ids across tables."""
    return f"{kind}:{int(ref_id)}"


def edge_key(kind: str, source: str, target: str, *, via: Optional[int] = None) -> str:
    """Stable edge identity.

    ``via`` is the cell the edge was read from. Two job cycles can be nested
    through more than one cell, and those are genuinely different edges — the
    map draws one line per link so deleting the link a user can see removes the
    line they expect.
    """
    suffix = "" if via is None else f"@{int(via)}"
    return f"{kind}|{source}|{target}{suffix}"


@dataclass(frozen=True)
class JobGraphNode:
    key: str
    kind: str
    ref_id: int
    label: str
    href: Optional[str] = None
    detail: Optional[str] = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "kind": self.kind,
            "ref_id": self.ref_id,
            "label": self.label,
            "href": self.href,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class JobGraphEdge:
    key: str
    kind: str
    source: str
    target: str
    label: str
    href: Optional[str] = None
    cell_id: Optional[int] = None
    lane_id: Optional[int] = None
    step_id: Optional[int] = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "kind": self.kind,
            "source": self.source,
            "target": self.target,
            "label": self.label,
            "href": self.href,
            "cell_id": self.cell_id,
            "lane_id": self.lane_id,
            "step_id": self.step_id,
        }


@dataclass
class JobGraphBuilder:
    """Accumulates nodes and edges, deduped by key, insertion order preserved.

    Dedupe is by key and *first write wins*: a node reached twice keeps the
    label it was first given, so a walk order change cannot silently relabel
    the graph.
    """

    _nodes: dict[str, JobGraphNode] = field(default_factory=dict)
    _edges: dict[str, JobGraphEdge] = field(default_factory=dict)

    def add_node(self, node: JobGraphNode) -> str:
        self._nodes.setdefault(node.key, node)
        return node.key

    def add_edge(self, edge: JobGraphEdge) -> str:
        self._edges.setdefault(edge.key, edge)
        return edge.key

    def has_node(self, key: str) -> bool:
        return key in self._nodes

    @property
    def nodes(self) -> list[JobGraphNode]:
        return list(self._nodes.values())

    @property
    def edges(self) -> list[JobGraphEdge]:
        return list(self._edges.values())

    def as_dict(self) -> dict[str, Any]:
        return {
            "nodes": [n.as_dict() for n in self.nodes],
            "edges": [e.as_dict() for e in self.edges],
        }


def clamp_cycle_graph_depth(value: Optional[int]) -> int:
    """Depth within ``1..MAX_CYCLE_GRAPH_DEPTH``; ``None`` takes the default."""
    if value is None:
        return DEFAULT_CYCLE_GRAPH_DEPTH
    return max(1, min(MAX_CYCLE_GRAPH_DEPTH, int(value)))


def clamp_audit_trail_limit(value: Optional[int]) -> int:
    """Path count within ``1..MAX_AUDIT_TRAIL_PATHS``; ``None`` takes the default."""
    if value is None:
        return DEFAULT_AUDIT_TRAIL_PATHS
    return max(1, min(MAX_AUDIT_TRAIL_PATHS, int(value)))


def select_trail_cells(
    candidates: Sequence[Mapping[str, Any]],
    *,
    limit: int,
) -> tuple[list[Mapping[str, Any]], int]:
    """Pick the cells a sample audit walk should follow, and say how many exist.

    Two rules, both about not wasting an auditor's attention:

    * A cell that is neither mandatory nor holds anything is not a path — there
      is nothing at the end of it — so it is not a candidate at all.
    * Mandatory cells come first, in pack order. They are the ones where an
      empty cell is a finding rather than a blank, so truncating the sample
      must never drop them in favour of an optional cell that happens to sort
      earlier.

    Returns the selection and the **candidate total**, so the caller can tell
    the user the sample was truncated instead of implying it saw everything.
    """
    required: list[Mapping[str, Any]] = []
    optional: list[Mapping[str, Any]] = []
    for candidate in candidates:
        if candidate.get("requires_evidence"):
            required.append(candidate)
        elif candidate.get("has_content"):
            optional.append(candidate)
    ordered = required + optional
    return ordered[: max(0, int(limit))], len(ordered)


@dataclass(frozen=True)
class CellReadinessVerdict:
    state: str
    reason: str
    evidence_count: int
    obsolete_count: int
    unresolved_count: int

    @property
    def is_ready(self) -> bool:
        return self.state in ("ready", "not_required")

    def as_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "reason": self.reason,
            "evidence_count": self.evidence_count,
            "obsolete_count": self.obsolete_count,
            "unresolved_count": self.unresolved_count,
            "is_ready": self.is_ready,
        }


def classify_cell_readiness(
    *,
    requires_evidence: bool,
    document_ids: Sequence[int],
    obsolete_ids: Optional[Iterable[int]] = None,
    unresolved_ids: Optional[Iterable[int]] = None,
    assure: bool = False,
) -> CellReadinessVerdict:
    """Whether a mandatory-evidence cell is actually satisfied.

    Evidence means an attached library document reference. Cell *links* are
    navigation — an audit outcome or an external URL is a pointer, not the
    controlled record an auditor is owed — so they deliberately do not satisfy
    the requirement.

    With ``assure`` off this is a presence check, which is all the composer can
    honestly claim without reading the document SSOT. With ``assure`` on, an
    obsolete attachment fails the cell (a withdrawn document is not evidence),
    and a document whose standing could not be read reports ``unknown`` rather
    than passing.
    """
    ids = [int(i) for i in document_ids]
    obsolete = {int(i) for i in (obsolete_ids or ())} & set(ids)
    unresolved = {int(i) for i in (unresolved_ids or ())} & set(ids)

    if not requires_evidence:
        return CellReadinessVerdict(
            state="not_required",
            reason="evidence_not_required",
            evidence_count=len(ids),
            obsolete_count=len(obsolete) if assure else 0,
            unresolved_count=len(unresolved) if assure else 0,
        )
    if not ids:
        return CellReadinessVerdict(
            state="missing_evidence",
            reason="no_evidence_attached",
            evidence_count=0,
            obsolete_count=0,
            unresolved_count=0,
        )
    if not assure:
        return CellReadinessVerdict(
            state="ready",
            reason="evidence_attached",
            evidence_count=len(ids),
            obsolete_count=0,
            unresolved_count=0,
        )
    if obsolete:
        return CellReadinessVerdict(
            state="obsolete_evidence",
            reason="evidence_obsolete",
            evidence_count=len(ids),
            obsolete_count=len(obsolete),
            unresolved_count=len(unresolved),
        )
    if unresolved:
        return CellReadinessVerdict(
            state="unknown",
            reason="evidence_status_unreadable",
            evidence_count=len(ids),
            obsolete_count=0,
            unresolved_count=len(unresolved),
        )
    return CellReadinessVerdict(
        state="ready",
        reason="evidence_current",
        evidence_count=len(ids),
        obsolete_count=0,
        unresolved_count=0,
    )


def summarise_readiness(verdicts: Iterable[CellReadinessVerdict]) -> dict[str, int]:
    """Counts per state plus ``required`` — the denominator a banner needs."""
    summary = {state: 0 for state in CELL_READINESS_STATES}
    required = 0
    for verdict in verdicts:
        summary[verdict.state] = summary.get(verdict.state, 0) + 1
        if verdict.state != "not_required":
            required += 1
    summary["required"] = required
    return summary


__all__ = [
    "CELL_READINESS_STATES",
    "DEFAULT_AUDIT_TRAIL_PATHS",
    "DEFAULT_CYCLE_GRAPH_DEPTH",
    "JOB_GRAPH_EDGE_KINDS",
    "JOB_GRAPH_NODE_KINDS",
    "MAX_AUDIT_TRAIL_PATHS",
    "MAX_CYCLE_GRAPH_DEPTH",
    "CellReadinessVerdict",
    "JobGraphBuilder",
    "JobGraphEdge",
    "JobGraphNode",
    "clamp_audit_trail_limit",
    "clamp_cycle_graph_depth",
    "classify_cell_readiness",
    "edge_key",
    "node_key",
    "select_trail_cells",
    "summarise_readiness",
]
