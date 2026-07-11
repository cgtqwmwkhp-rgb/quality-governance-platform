# Governance link — OCR / AI Import DPIA (Path-to-10 S15)

**Status:** LIVE documentation  
**Compliance artifact:** [`../compliance/dpia-ocr-ai-import.md`](../compliance/dpia-ocr-ai-import.md)

## Why this exists

Path-to-10 Stage 15 (Compliance / Privacy) required a **module-specific DPIA** for external audit OCR and AI document processing (Mistral OCR/analysis, Gemini multimodal review). The generic platform DPIA and incidents DPIA do not cover third-party document egress.

## Operator actions

1. Run the trigger + completeness checklists in [`../privacy/dpia-checklist.md`](../privacy/dpia-checklist.md) before enabling production AI keys.
2. Confirm sub-processors are on the DPA schedule.
3. Record DPO residual-risk acceptance against EA-03 in [`../evidence/external-attestation-tracker.md`](../evidence/external-attestation-tracker.md).

## Runtime privacy disclosure

| Surface | Path |
| --- | --- |
| Privacy contact + lifecycle flags | `GET /api/v1/privacy/contact` |
| security.txt (RFC 9116) | `GET /.well-known/security.txt` |
| GDPR export / erasure | `/api/v1/gdpr/me/*` |
