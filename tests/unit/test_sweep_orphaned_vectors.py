"""Classification rules for the pre-#1289 orphaned-vector sweep.

The sweep deletes from Pinecone based purely on ``classify``, so a mistake here
removes vectors for live documents and nothing downstream notices — the document
stays listed and simply stops being found by semantic search. These tests pin the
decision for each class of ID the index can contain.
"""

from __future__ import annotations

import inspect

from scripts.maintenance.sweep_orphaned_vectors import classify, list_vector_ids


def _classify(vector_ids, *, live_chunks=frozenset(), live_documents=frozenset(), skip_documents=frozenset()):
    return classify(
        vector_ids,
        live_chunks=set(live_chunks),
        live_documents=set(live_documents),
        skip_documents=set(skip_documents),
    )


def test_a_vector_backed_by_a_chunk_row_is_kept() -> None:
    plan = _classify(["doc_1_chunk_0"], live_chunks={(1, 0)}, live_documents={1})

    assert plan.orphans == {}
    assert plan.kept == 1


def test_vector_for_a_deleted_document_is_an_orphan() -> None:
    """Disposal before #1289 removed the rows and left the vectors behind."""
    plan = _classify(["doc_9_chunk_0", "doc_9_chunk_1"], live_documents={1})

    assert plan.orphans == {"doc_9_chunk_0": "missing-document", "doc_9_chunk_1": "missing-document"}
    assert plan.reasons["missing-document"] == 2


def test_high_index_vector_of_a_shrunken_reindex_is_an_orphan() -> None:
    """The document survives; only its tail vectors were abandoned."""
    plan = _classify(
        ["doc_1_chunk_0", "doc_1_chunk_1", "doc_1_chunk_2"],
        live_chunks={(1, 0)},
        live_documents={1},
    )

    assert plan.orphans == {"doc_1_chunk_1": "missing-chunk", "doc_1_chunk_2": "missing-chunk"}
    assert plan.kept == 1


def test_documents_with_an_unfinished_job_are_left_completely_alone() -> None:
    """Mid-reindex, absent chunk rows mean "being rewritten", not "abandoned"."""
    plan = _classify(
        ["doc_5_chunk_0", "doc_5_chunk_7"],
        live_chunks=set(),
        live_documents={5},
        skip_documents={5},
    )

    assert plan.orphans == {}
    assert plan.kept == 2
    assert plan.skipped_documents == {5}


def test_a_skipped_document_is_spared_even_when_the_document_row_is_gone() -> None:
    """The skip must win over every other rule, or the race it guards reopens."""
    plan = _classify(["doc_5_chunk_0"], live_documents=set(), skip_documents={5})

    assert plan.orphans == {}


def test_ids_this_app_did_not_write_are_never_deleted() -> None:
    """Another writer may share the index; an unexplained ID is not ours to remove."""
    plan = _classify(["some-other-writer-abc", "doc_1_chunkX", "doc__chunk_1"], live_documents={1})

    assert plan.orphans == {}
    assert plan.unrecognised == ["some-other-writer-abc", "doc_1_chunkX", "doc__chunk_1"]


def test_an_empty_index_yields_an_empty_plan() -> None:
    plan = _classify([])

    assert plan.orphans == {}
    assert plan.kept == 0
    assert plan.unrecognised == []


def test_chunk_index_is_matched_exactly_not_by_document_alone() -> None:
    """A live chunk 0 must not vouch for chunk 10 of the same document."""
    plan = _classify(["doc_2_chunk_10"], live_chunks={(2, 0)}, live_documents={2})

    assert plan.orphans == {"doc_2_chunk_10": "missing-chunk"}


def test_listing_takes_no_namespace() -> None:
    """Listing one namespace while deleting from another would destroy live vectors.

    ``delete_vectors_by_id`` sends no namespace, so it always deletes from the default
    one. Because vector IDs are deterministic, the same ID exists in every namespace
    holding that document — so enumerating namespace "x" and deleting its orphan IDs
    would remove the *live* copies from the default namespace and leave the real
    orphans in place. The app never sets a namespace, so there is nothing to support:
    if this parameter comes back, thread it through the delete path in the same change.
    """
    assert "namespace" not in inspect.signature(list_vector_ids).parameters
