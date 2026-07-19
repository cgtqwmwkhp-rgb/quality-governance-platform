# Answer Integrity Freeze Gap (CUJ-P0-AUDIT-ANSWER-INTEGRITY-01)

## Shipped in this slice (PR-A backend)
- `publish_template()` writes a `template_versions` row with `snapshot_json` of the full question graph.
- `complete_run()` enforces required-question (+ evidence) completion gate via `missing_question_ids`.
- Photo/signature evidence checks use `response_json.evidence_asset_ids` (shared evidence-assets spine).
- Publish rejects `file` and unknown question types until execution support lands.

## Documented gap (parked)
Completion and auto-finding still evaluate **live** `audit_questions` rows keyed by `response.question_id`.

Mid-run edits to live question text/options/scoring can still drift relative to the publish snapshot. Full freeze evaluation (score/find against snapshot only) is intentionally deferred — larger than this overnight slice and needs a dedicated migration of finding generation onto snapshot DTOs.
