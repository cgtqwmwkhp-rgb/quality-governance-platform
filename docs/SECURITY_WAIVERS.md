# Security Vulnerability Waivers

This document tracks security vulnerabilities that have been reviewed and accepted with documented risk mitigation.

## Active Waivers

### CVE-2026-4539 (pygments 2.19.2)

**Package**: `pygments` (transitive development dependency)

**Vulnerability**: CVE-2026-4539 reported against `pygments` 2.19.2.

**Severity**: Medium

**Status**: **ACCEPTED WITH MITIGATION**

**Rationale**:
1. `pygments` is pulled in through developer tooling and documentation dependencies, not the production runtime dependency set.
2. The production container installs `requirements.txt`/`requirements.lock`, while the vulnerable package is introduced through the CI `requirements-dev.txt` toolchain.
3. There is no newer upstream `pygments` release available than 2.19.2, so an immediate package upgrade is not currently possible.

**Mitigation**:
- Keep the vulnerability explicitly documented and time-boxed through this waiver.
- Continue validating that the production image installs runtime dependencies only.
- Monitor upstream for a patched `pygments` release and upgrade immediately when available.

**Alternative Considered**:
- Pinning an older `pygments` release would not remediate the reported CVE and could destabilize the docs/tooling stack.

**Owner**: Security Team

**Review Date**: 2026-03-24

**Expiry Date**: 2026-06-22 (90 days)

**Action Required**: Upgrade `pygments` to a patched version when released, then remove this waiver.

---

### CVE-2026-0994 (protobuf 6.33.4)

**Package**: `protobuf` (transitive dependency)

**Vulnerability**: CVE-2026-0994 reported against `protobuf` 6.33.4.

**Severity**: High (per pip-audit advisory)

**Status**: **ACCEPTED WITH MITIGATION**

**Rationale**:
1. `protobuf` is a transitive dependency and not directly used in any externally exposed request parsing paths in this service.
2. There is currently no fixed upstream release beyond 6.33.4 available in the package index.
3. Blocking production deployment for this workflow fix increases operational risk and user impact.

**Mitigation**:
- Continue monitoring upstream for a fixed version and upgrade immediately once available.
- Restrict and monitor any features that might introduce untrusted protobuf deserialization.
- Security scan remains blocking for any new vulnerabilities not explicitly waived.

**Alternative Considered**:
- Pinning to an older version is not acceptable due to unknown compatibility issues and does not address the CVE.

**Owner**: Security Team

**Review Date**: 2026-01-24

**Expiry Date**: 2026-04-24 (90 days)

**Action Required**: Upgrade `protobuf` to a patched version when released, then remove this waiver.

---

### CVE-2024-23342 (ecdsa 0.19.1)

**Package**: `ecdsa` (transitive dependency via `python-jose`)

**Vulnerability**: Minerva timing attack on P-256 curve that may allow private key discovery through timing analysis of signature operations.

**Severity**: Medium

**Status**: **ACCEPTED WITH MITIGATION**

**Rationale**:
1. The `python-ecdsa` project maintainers consider side-channel attacks out of scope and have stated there is no planned fix.
2. This is a transitive dependency brought in by `python-jose[cryptography]` for JWT token handling.
3. Our application uses JWT tokens for authentication, but the signing operations are not exposed to untrusted input in a way that would allow timing attacks.
4. The vulnerability requires an attacker to have the ability to measure precise timing of signature operations, which is not feasible in our deployment environment.

**Mitigation**:
- JWT signing operations are performed server-side only and are not exposed to client timing analysis.
- We use strong, randomly generated JWT secret keys.
- Token expiration times are kept short (15 minutes for access tokens, 7 days for refresh tokens).
- We monitor for any unusual authentication patterns.

**Alternative Considered**:
- Switching from `python-jose` to `PyJWT` would eliminate the `ecdsa` dependency, but would require significant refactoring of the authentication system.
- This refactoring is planned for a future release but is not blocking for the current release governance milestone.

**Owner**: Security Team

**Review Date**: 2026-01-04

**Expiry Date**: 2026-04-04 (90 days)

**Action Required**: Re-evaluate this waiver by the expiry date. If `python-jose` has not been replaced by then, extend the waiver with updated justification or implement the migration to `PyJWT`.

---

### CVE-2026-24486 (python-multipart 0.0.18)

**Package**: `python-multipart` (dependency of FastAPI/Starlette)

**Vulnerability**: Path Traversal vulnerability when using non-default configuration options for file uploads.

**Severity**: High

**Status**: **ACCEPTED WITH MITIGATION**

**Rationale**:
1. This vulnerability only applies when using non-default configuration options (custom upload handlers with path construction).
2. Our application uses the default FastAPI file upload handling without custom path construction.
3. All file uploads are stored in Azure Blob Storage with generated UUIDs, not user-controlled paths.
4. Blocking production deployment for a vulnerability in an unused code path increases operational risk.

**Mitigation**:
- Continue using default FastAPI file upload configuration.
- All file storage uses Azure Blob Storage with generated object keys.
- User-controlled filenames are never used in path construction.
- Monitor upstream for a fixed version and upgrade when available.

**Alternative Considered**:
- Upgrading python-multipart requires testing with FastAPI/Starlette compatibility matrix.

**Owner**: Security Team

**Review Date**: 2026-01-27

**Expiry Date**: 2026-04-27 (90 days)

**Action Required**: Upgrade `python-multipart` to patched version when released, then remove this waiver.

---

### CVE-2026-39892 (cryptography 46.0.6)

**Package**: `cryptography` (runtime dependency)

**Vulnerability**: When a non-contiguous buffer was passed to APIs which accepted Python buffers (e.g. `Hash.update()`), data may be processed incorrectly. Reachability requires application code to pass non-contiguous buffers, which this service does not do — all hash/encrypt inputs are bytes objects produced from JSON, file streams, or `str.encode()`.

**Severity**: Medium

**Status**: **ACCEPTED WITH MITIGATION**

**Rationale**:
1. The vulnerable code path is only triggered for non-contiguous Python buffer objects (e.g. NumPy strided arrays). Our backend never passes such buffers to `cryptography` — all calls operate on `bytes` produced from JWT signing/verification, password hashing, or file reads.
2. No fixed upstream version of `cryptography` is yet available at the time of waiver creation that we have not already pinned.
3. Blocking unrelated frontend auth-resilience work to chase a non-reachable code path increases operational risk.

**Mitigation**:
- All hashing call sites already use `bytes`-typed inputs.
- Monitor upstream `cryptography` releases and upgrade as soon as a patched version is available.
- Re-run `pip-audit` weekly via the lockfile-update workflow.

**Alternative Considered**:
- Pinning an older `cryptography` release would expose us to other previously-patched issues.

**Owner**: Security Team

**Review Date**: 2026-04-07

**Expiry Date**: 2026-07-06 (90 days)

**Action Required**: Upgrade `cryptography` to a patched release when available, then remove this waiver.

---

### CVE-2026-40192 (pillow 12.1.1)

**Package**: `pillow` (runtime dependency for image evidence handling)

**Vulnerability**: Pillow does not limit the amount of GZIP-compressed data read when decoding a FITS image, allowing a memory-amplification denial of service if a crafted FITS file is decoded.

**Severity**: Medium

**Status**: **ACCEPTED WITH MITIGATION**

**Rationale**:
1. This service does not accept or decode FITS image files. All image inputs are limited to JPEG, PNG, HEIC, and WebP (audit photos and signatures) via explicit content-type allowlists in the upload handlers.
2. Pillow's FITS support is not on any reachable path in the application.
3. No patched upstream Pillow release is currently available beyond 12.1.1 with the same compatibility guarantees.

**Mitigation**:
- Image upload allowlists already exclude FITS.
- File-size limits enforced at both the Azure ingress and the API.
- Monitor upstream and upgrade Pillow when a patched release ships.

**Alternative Considered**:
- Disabling Pillow's FITS plugin via `PIL.FitsImagePlugin` patching is fragile and unnecessary given the upload allowlist.

**Owner**: Security Team

**Review Date**: 2026-04-07

**Expiry Date**: 2026-07-06 (90 days)

**Action Required**: Upgrade `pillow` when a patched release is published, then remove this waiver.

---

### CVE-2026-40260 / GHSA-jj6c-8h6c-hppx / GHSA-4pxv-j86v-mhcw / GHSA-7gw9-cf7v-778f / GHSA-x284-j5p8-9c5p (pypdf 6.9.2)

**Package**: `pypdf` (runtime dependency for PDF text extraction during external audit imports)

**Vulnerability**: Five related advisories on `pypdf` 6.9.2 covering crafted PDFs that can cause large memory usage, long runtimes, or RAM exhaustion when parsed.

**Severity**: Medium

**Status**: **ACCEPTED WITH MITIGATION**

**Rationale**:
1. PDF parsing only runs inside the external audit import worker, which has a per-request timeout and a Celery worker with bounded memory.
2. PDF inputs are uploaded by authenticated tenant users only — there is no anonymous PDF ingestion path.
3. File-size limits are enforced at the upload boundary (Azure Blob ingress) before the PDF reaches `pypdf`.
4. No patched upstream `pypdf` release is yet available that we have not pinned.

**Mitigation**:
- Per-tenant rate limiting on the audit import endpoint.
- Celery worker memory limits and per-task wall-clock timeouts terminate runaway parses.
- Upload size cap rejects oversized PDFs before parsing.
- Monitor upstream and upgrade `pypdf` when a patched release ships.

**Alternative Considered**:
- Replacing `pypdf` with `pdfplumber` or `pdfminer.six` would be a larger refactor and would not resolve the parser-amplification class of issue without similar mitigations.

**Owner**: Security Team

**Review Date**: 2026-04-07

**Expiry Date**: 2026-07-06 (90 days)

**Action Required**: Upgrade `pypdf` to a patched release when available, then remove this waiver.

---

### CVE-2025-71176 (pytest 8.4.2)

**Package**: `pytest` (development dependency only)

**Vulnerability**: `pytest` through 9.0.2 on UNIX relies on `/tmp/pytest-of-{user}` directories whose permissions can allow a local attacker to interfere with test artifacts.

**Severity**: Low

**Status**: **ACCEPTED WITH MITIGATION**

**Rationale**:
1. `pytest` is a development-only dependency. It is not installed in the production container (`requirements.lock` for runtime is separate from `requirements-dev.txt`).
2. Exploitation requires local shell access on the same UNIX host as the test runner. CI runs each job in an ephemeral GitHub-hosted runner with a single user.
3. There is no production exposure.

**Mitigation**:
- Ensure `pytest` is excluded from production images (already enforced).
- CI runners are ephemeral and isolated.
- Track upstream `pytest` for a patched release.

**Alternative Considered**:
- Forcing a `pytest` major upgrade today risks invalidating existing test fixtures with no production-security benefit.

**Owner**: Security Team

**Review Date**: 2026-04-07

**Expiry Date**: 2026-07-06 (90 days)

**Action Required**: Upgrade `pytest` when a patched release ships, then remove this waiver.

---

### CVE-2026-40347 (python-multipart 0.0.22)

**Package**: `python-multipart` (transitive dependency of FastAPI/Starlette)

**Vulnerability**: A denial-of-service vulnerability exists when parsing crafted `multipart/form-data` requests — pathological inputs can cause excessive parser CPU usage.

**Severity**: Medium

**Status**: **ACCEPTED WITH MITIGATION**

**Rationale**:
1. The application enforces a request body size limit at the Azure ingress and at the FastAPI middleware layer, bounding the worst-case input size before the multipart parser is invoked.
2. Multipart endpoints are authenticated and tenant-scoped — no anonymous DoS amplification surface.
3. No patched upstream `python-multipart` release is currently available beyond 0.0.22.

**Mitigation**:
- Body-size limit enforced at the edge.
- Per-tenant rate limiting on file-upload endpoints.
- Monitor upstream for a fixed release and upgrade immediately when available.

**Alternative Considered**:
- Downgrading would re-introduce previously waived CVE-2026-24486 (path traversal), which is strictly worse.

**Owner**: Security Team

**Review Date**: 2026-04-07

**Expiry Date**: 2026-07-06 (90 days)

**Action Required**: Upgrade `python-multipart` to a patched release when available, then remove this waiver.

---

## Waiver Review Process

All security waivers must be reviewed every 90 days. Waivers that remain active beyond their expiry date must either:

1. Have the vulnerability patched and the waiver removed
2. Have the affected package replaced with a secure alternative
3. Have the waiver extended with explicit justification and updated risk assessment

**Last Reviewed**: 2026-04-07
