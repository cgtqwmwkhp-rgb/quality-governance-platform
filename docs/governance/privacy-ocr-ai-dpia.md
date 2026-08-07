# Governance link — OCR / AI Import DPIA (Path-to-10 S15)

**Status:** LIVE documentation  
**Compliance artifact:** [`../compliance/dpia-ocr-ai-import.md`](../compliance/dpia-ocr-ai-import.md)

## Why this exists

Path-to-10 Stage 15 (Compliance / Privacy) required a **module-specific DPIA** for external audit OCR and AI document processing. The generic platform DPIA and incidents DPIA do not cover third-party document egress.

Scope as of DPIA v2.0 (2026-07-28) is wider than OCR: Mistral OCR/analysis, Gemini multimodal review, Azure AI Document Intelligence failover, Anthropic/OpenAI document and case analysis, Voyage AI embeddings, and **Pinecone, which retains document-derived content in a vendor-hosted index**. Genspark and Perplexity code paths are disclosed but their activation is unconfirmed.

## Operator actions

1. Run the trigger + completeness checklists in [`../privacy/dpia-checklist.md`](../privacy/dpia-checklist.md) before enabling production AI keys.
2. Confirm **every** processor in DPIA §2.0a is on the DPA schedule — not just the OCR pair.
3. Establish each AI vendor's processing region and transfer safeguard; the register currently publishes these as `unknown_not_established_in_repository` because the repository cannot determine them.
4. DPO residual-risk acceptance against EA-03 is recorded for **v2.0** (David Harris, 2026-08-06) in [`../compliance/dpia-ocr-ai-import.md`](../compliance/dpia-ocr-ai-import.md) §8 and [`../evidence/external-attestation-tracker.md`](../evidence/external-attestation-tracker.md). Continue chasing §7 organisational follow-ons (DPA schedule, regions, Pinecone preview necessity).
5. When adding any new AI provider credential, declare it in [`../../src/core/ai_provider_disclosure.py`](../../src/core/ai_provider_disclosure.py) and the register; the build fails otherwise.

## Runtime privacy disclosure

| Surface | Path |
| --- | --- |
| Privacy contact + lifecycle flags | `GET /api/v1/privacy/contact` |
| security.txt (RFC 9116) | `GET /.well-known/security.txt` |
| GDPR export / erasure | `/api/v1/gdpr/me/*` |
