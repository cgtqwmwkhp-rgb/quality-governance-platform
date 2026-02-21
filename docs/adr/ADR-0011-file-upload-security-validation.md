# ADR-0011: Multi-Layer File Upload Security Validation

**Status:** Accepted
**Date:** 2026-02-21
**Authors:** Platform Engineering Team

## Context

The platform accepts file uploads for document control, audit evidence, and incident attachments. File uploads are a well-known attack vector: malicious files can be disguised with false extensions, oversized uploads can cause denial of service, and executable content can compromise downstream systems. A single validation check (e.g., extension only) is easily bypassed and insufficient for an enterprise compliance platform.

## Decision

We implement three-layer file upload validation. **Layer 1 (Extension Allowlist):** Only files with explicitly permitted extensions (`.pdf`, `.docx`, `.xlsx`, `.png`, `.jpg`, `.csv`) are accepted; all others are rejected immediately. **Layer 2 (Magic Number Verification):** The file's binary header is inspected to confirm its actual type matches the declared extension, preventing extension spoofing attacks. **Layer 3 (Size Limits):** Per-file and per-request size limits are enforced (configurable, default 10MB per file, 50MB per request) to prevent resource exhaustion.

## Consequences

### Positive
- Defense-in-depth approach catches attacks that bypass any single validation layer
- Magic number verification prevents the most common file type spoofing attacks
- Size limits protect against denial-of-service via large upload payloads
- Allowlist approach is more secure than denylist — only known-safe types are permitted

### Negative
- Legitimate files with unusual headers may be rejected by magic number verification
- The extension allowlist requires maintenance as new document types are needed
- Binary header inspection adds processing time to every upload

### Neutral
- Uploaded files are stored in Azure Blob Storage with randomized names, preventing path traversal
- Antivirus scanning is deferred to Azure Defender for Storage (out of application scope)
- Upload validation configuration is centralized in `src/core/config.py`
