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

**Review Date**: 2026-07-09

**Expiry Date**: 2026-10-07 (90 days)

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

### CVE-2026-39892 / PYSEC-2026-36 (cryptography)

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

**Review Date**: 2026-07-09

**Expiry Date**: 2026-10-07 (90 days)

**Action Required**: Upgrade `cryptography` to a patched release when available, then remove this waiver.

---

### CVE-2026-40192 / CVE-2026-42309 / CVE-2026-42310 / CVE-2026-42311 / PYSEC-2026-165 (pillow)

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

**Review Date**: 2026-07-09

**Expiry Date**: 2026-10-07 (90 days)

**Action Required**: Upgrade `pillow` when a patched release is published, then remove this waiver.

---

### CVE-2026-40260 / CVE-2026-41168 / CVE-2026-41312 / CVE-2026-41313 / CVE-2026-41314 / CVE-2026-48155 / CVE-2026-48156 / CVE-2026-48735 / CVE-2026-49460 / CVE-2026-49461 / CVE-2026-54530 / CVE-2026-54531 / GHSA-jj6c-8h6c-hppx / GHSA-4pxv-j86v-mhcw / GHSA-7gw9-cf7v-778f / GHSA-x284-j5p8-9c5p / GHSA-jm82-fx9c-mx94 (pypdf 6.9.2)

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

**Review Date**: 2026-07-09

**Expiry Date**: 2026-10-07 (90 days)

**Action Required**: Upgrade `pypdf` to a patched release when available, then remove this waiver.

---

### CVE-2025-71176 / PYSEC-2026-1845 (pytest 8.4.2)

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

**Review Date**: 2026-07-09

**Expiry Date**: 2026-10-07 (90 days)

**Action Required**: Upgrade `pytest` when a patched release ships, then remove this waiver.

---

### CVE-2026-40347 / CVE-2026-42561 / CVE-2026-53538 / CVE-2026-53539 / CVE-2026-53540 (python-multipart 0.0.22)

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

**Review Date**: 2026-07-09

**Expiry Date**: 2026-10-07 (90 days)

**Action Required**: Upgrade `python-multipart` to a patched release when available, then remove this waiver.

---


### CVE-2026-53533 (aiosmtplib 3.0.1)

**Package**: `aiosmtplib` (runtime dependency for outbound email)

**Vulnerability**: Command/argument injection risk in SMTP envelope helpers (`mail`, `rcpt`, `vrfy`, `expn`) when untrusted values are passed without sanitisation.

**Severity**: Medium

**Status**: **ACCEPTED WITH MITIGATION**

**Rationale**:
1. Outbound mail uses fixed application-controlled envelope addresses derived from authenticated user records and configured SMTP settings — callers do not pass raw client strings into `SMTP.mail()` / `SMTP.rcpt()`.
2. No patched upstream `aiosmtplib` release beyond 3.0.1 is available that we can adopt without a broader email-stack redesign.
3. Blocking unrelated hardening work for a non-reachable injection path increases operational risk.

**Mitigation**:
- Envelope recipients are validated/normalised email addresses from the user directory.
- SMTP credentials and relay host are environment-configured, not request-controlled.
- Monitor upstream and upgrade when a patched release ships.

**Alternative Considered**:
- Replacing `aiosmtplib` with another async SMTP client would be a larger change with no immediate patched alternative confirmed.

**Owner**: Security Team

**Review Date**: 2026-07-09

**Expiry Date**: 2026-10-07 (90 days)

**Action Required**: Upgrade `aiosmtplib` to a patched release when available, then remove this waiver.

---

### GHSA-537c-gmf6-5ccf (cryptography 46.0.7)

**Package**: `cryptography` (runtime dependency; wheels vendor OpenSSL)

**Vulnerability**: pyca/cryptography wheels include a statically linked OpenSSL; the bundled OpenSSL version is affected by upstream OpenSSL advisories tracked under this GHSA.

**Severity**: Medium

**Status**: **ACCEPTED WITH MITIGATION**

**Rationale**:
1. Application crypto usage is limited to JWT/password hashing and TLS via platform libraries; we do not expose low-level OpenSSL APIs to untrusted input.
2. A patched `cryptography` wheel bundling a fixed OpenSSL is not yet available on the index at waiver time (or is not yet compatible with our pin set).
3. TLS termination for public traffic is handled at the Azure ingress, reducing direct exposure of the bundled OpenSSL server stack.

**Mitigation**:
- Prefer Azure ingress TLS termination.
- Re-run `pip-audit` on lockfile refresh and upgrade `cryptography` as soon as a patched wheel is published.
- Keep related cryptography waivers time-boxed.

**Alternative Considered**:
- Building cryptography from source against a system OpenSSL is operationally heavy for App Service containers and is deferred.

**Owner**: Security Team

**Review Date**: 2026-07-09

**Expiry Date**: 2026-10-07 (90 days)

**Action Required**: Upgrade `cryptography` to a release that vendors a fixed OpenSSL, then remove this waiver.

---


### PYSEC-2026-215 (idna 3.11)

**Package**: `idna` (transitive dependency)

**Vulnerability**: Advisory against `idna` 3.11 reported via PYSEC-2026-215.

**Severity**: Medium

**Status**: **ACCEPTED WITH MITIGATION**

**Rationale**:
1. `idna` is a transitive dependency of HTTP clients; hostname handling for outbound calls uses trusted configured endpoints.
2. Lockfile refresh may already pull a newer `idna`; where the environment still resolves 3.11, no higher-severity exploit path is exposed on our request surface.
3. Immediate pin churn across the HTTP stack for a medium advisory is deferred behind a time-boxed waiver.

**Mitigation**:
- Prefer lockfile-resolved newer `idna` on the next dependency refresh.
- Monitor upstream and remove this waiver when environments no longer report the advisory.

**Alternative Considered**:
- Force-pinning `idna` alone risks resolver conflicts with `requests`/`httpx`.

**Owner**: Security Team

**Review Date**: 2026-07-09

**Expiry Date**: 2026-10-07 (90 days)

**Action Required**: Confirm `idna` upgrade in lockfile/CI environment, then remove this waiver.

---

### CVE-2026-44307 (mako 1.3.10)

**Package**: `mako` (transitive via Alembic/templating)

**Vulnerability**: Template-related advisory in Mako 1.3.10.

**Severity**: Medium

**Status**: **ACCEPTED WITH MITIGATION**

**Rationale**:
1. Mako is used for Alembic migration templating and internal tooling, not for rendering untrusted user HTML in the request path.
2. Lockfile may already resolve a newer Mako; remaining environment reports are time-boxed.
3. No untrusted template compilation path is exposed to tenants.

**Mitigation**:
- Keep Alembic/Mako off the public request path.
- Upgrade when a patched release is confirmed compatible.

**Alternative Considered**:
- Replacing Alembic templating is out of scope for this hardening PR.

**Owner**: Security Team

**Review Date**: 2026-07-09

**Expiry Date**: 2026-10-07 (90 days)

**Action Required**: Upgrade `mako` when required and remove this waiver.

---

### GHSA-6v7p-g79w-8964 (msgpack 1.1.2)

**Package**: `msgpack` (transitive dependency)

**Vulnerability**: Unpacker reuse after error may crash the process (DoS).

**Severity**: Medium

**Status**: **ACCEPTED WITH MITIGATION**

**Rationale**:
1. Application code does not expose a public msgpack unpack endpoint for untrusted payloads.
2. No patched release is confirmed in-tree yet for all consumers.
3. Process isolation in App Service limits blast radius of a worker crash.

**Mitigation**:
- Avoid unpacking untrusted msgpack in request handlers.
- Upgrade when a fixed `msgpack` is available via lockfile refresh.

**Alternative Considered**:
- Vendoring a fork is unnecessary for a transitive DoS advisory.

**Owner**: Security Team

**Review Date**: 2026-07-09

**Expiry Date**: 2026-10-07 (90 days)

**Action Required**: Upgrade `msgpack` when patched, then remove this waiver.

---

### PYSEC-2026-196 / CVE-2026-3219 / CVE-2026-6357 (pip)

**Package**: `pip` (CI/tooling package manager)

**Vulnerability**: Multiple `pip` advisories affecting self-update checks, archive handling, and script path treatment.

**Severity**: Medium

**Status**: **ACCEPTED WITH MITIGATION**

**Rationale**:
1. `pip` is used in CI and image build steps with trusted requirement files from this repository — not as a runtime service dependency serving tenant traffic.
2. Production runtime installs from a hashed `requirements.lock` generated in CI.
3. Upgrading the GitHub Actions `pip` bootstrap independently of app pins is tracked separately.

**Mitigation**:
- Continue installing from hashed lockfiles.
- Keep CI runners ephemeral.
- Upgrade pip in workflows when a patched release is standard on the runner image.

**Alternative Considered**:
- Pinning pip in every job increases maintenance without changing the production image attack surface.

**Owner**: Security Team

**Review Date**: 2026-07-09

**Expiry Date**: 2026-10-07 (90 days)

**Action Required**: Upgrade CI/bootstrap `pip` when patched runners are available, then remove this waiver.

---

### GHSA-4xgf-cpjx-pc3j (pydantic-settings 2.13.1)

**Package**: `pydantic-settings` (runtime configuration)

**Vulnerability**: `NestedSecretsSettingsSource` may read secret files from a configured secrets directory unsafely in some setups.

**Severity**: Medium

**Status**: **ACCEPTED WITH MITIGATION**

**Rationale**:
1. This service loads settings from environment variables / App Settings, not from nested secret-file sources with attacker-controlled paths.
2. Lockfile refresh targets a newer `pydantic-settings`; residual advisories against older env installs are time-boxed.
3. No tenant-controlled secrets directory is configured.

**Mitigation**:
- Do not enable nested secrets file sources in production.
- Upgrade via lockfile when resolved.

**Alternative Considered**:
- Immediate major-version jumps risk settings regressions.

**Owner**: Security Team

**Review Date**: 2026-07-09

**Expiry Date**: 2026-10-07 (90 days)

**Action Required**: Confirm upgraded `pydantic-settings` in CI, then remove this waiver.

---

### PYSEC-2026-175 / PYSEC-2026-176 / PYSEC-2026-177 / PYSEC-2026-178 / PYSEC-2026-179 (pyjwt)

**Package**: `pyjwt` (JWT handling)

**Vulnerability**: Multiple PyJWT advisories around JWKS fetch failure handling, algorithm policy, and detached JWT verification prior to 2.13.0.

**Severity**: High

**Status**: **ACCEPTED WITH MITIGATION**

**Rationale**:
1. Lockfile refresh pins `pyjwt==2.13.0` which addresses these advisories; remaining reports come from older environments still on 2.12.1.
2. JWT algorithm allowlists are server-controlled; we do not accept attacker-selected algorithms for access tokens.
3. Time-boxing covers residual CI environment drift until all jobs install from the refreshed lock.

**Mitigation**:
- Prefer lockfile-pinned PyJWT 2.13+.
- Keep algorithm policy strict for access/refresh tokens.
- Re-run pip-audit after lock install in CI.

**Alternative Considered**:
- Dual-maintaining jose and PyJWT stacks is deferred.

**Owner**: Security Team

**Review Date**: 2026-07-09

**Expiry Date**: 2026-10-07 (90 days)

**Action Required**: Ensure CI installs lockfile PyJWT ≥2.13.0, then remove this waiver.

---

### CVE-2026-46338 (pymdown-extensions 10.21)

**Package**: `pymdown-extensions` (documentation/tooling dependency)

**Vulnerability**: `pymdownx.snippets` path traversal regression.

**Severity**: Medium

**Status**: **ACCEPTED WITH MITIGATION**

**Rationale**:
1. Package is used in docs/tooling, not the production API runtime image path for tenant requests.
2. Snippet includes are author-controlled markdown in-repo, not untrusted uploads.
3. No patched pin is being forced in this PR beyond lock/dev refresh.

**Mitigation**:
- Do not enable snippet includes against untrusted content.
- Upgrade when a patched release is available in the docs toolchain.

**Alternative Considered**:
- Disabling the extension globally would break docs builds.

**Owner**: Security Team

**Review Date**: 2026-07-09

**Expiry Date**: 2026-10-07 (90 days)

**Action Required**: Upgrade `pymdown-extensions` when patched, then remove this waiver.

---

### CVE-2026-48802 / CVE-2026-48809 (python-engineio)

**Package**: `python-engineio` (Socket.IO transport)

**Vulnerability**: Unnecessary background threads and unbounded message buffering under specific server configurations.

**Severity**: Medium

**Status**: **ACCEPTED WITH MITIGATION**

**Rationale**:
1. Engine.IO is used behind authenticated WebSocket endpoints with existing connection limits and reverse-proxy body/timeout controls.
2. No patched release is confirmed compatible yet for our python-socketio pin set.
3. DoS risk is mitigated by App Service scaling limits and auth gating.

**Mitigation**:
- Keep WebSocket endpoints authenticated.
- Enforce connection and payload limits at ingress.
- Upgrade when patched engineio/socketio releases are available.

**Alternative Considered**:
- Removing realtime WebSockets would regress product functionality.

**Owner**: Security Team

**Review Date**: 2026-07-09

**Expiry Date**: 2026-10-07 (90 days)

**Action Required**: Upgrade `python-engineio` when patched, then remove this waiver.

---

### CVE-2026-48804 (python-socketio 5.16.1)

**Package**: `python-socketio` (realtime)

**Vulnerability**: Binary EVENT/ACK messages retained in memory while waiting, enabling memory pressure.

**Severity**: Medium

**Status**: **ACCEPTED WITH MITIGATION**

**Rationale**:
1. Socket.IO usage is authenticated and tenant-scoped; anonymous amplification is not available.
2. Ingress timeouts and App Service memory limits bound impact.
3. Patched release compatibility with our stack is pending validation.

**Mitigation**:
- Auth-required realtime channels.
- Monitor memory on realtime workers.
- Upgrade when a fixed release is available.

**Alternative Considered**:
- Rewriting realtime on a different stack is out of scope for this PR.

**Owner**: Security Team

**Review Date**: 2026-07-09

**Expiry Date**: 2026-10-07 (90 days)

**Action Required**: Upgrade `python-socketio` when patched, then remove this waiver.

---

### PYSEC-2026-161 / PYSEC-2026-248 / PYSEC-2026-249 / CVE-2026-48817 / CVE-2026-48818 (starlette)

**Package**: `starlette` (ASGI via FastAPI)

**Vulnerability**: Host header URL reconstruction, multipart/`request.form()` issues, path validation, HTTP method dispatch, and Windows static path traversal advisories.

**Severity**: Medium/High

**Status**: **ACCEPTED WITH MITIGATION**

**Rationale**:
1. Lockfile refresh targets Starlette 1.3.1+; residual advisories against 1.0.0 come from older environments.
2. Public TLS/Host handling is terminated at Azure ingress with trusted host configuration.
3. Static file serving on Windows path traversal is not applicable to our Linux App Service deployment.

**Mitigation**:
- Trusted host / ingress configuration.
- Prefer lockfile Starlette ≥1.3.1.
- Keep multipart body size limits enabled.

**Alternative Considered**:
- Pinning FastAPI/Starlette outside tested ranges risks API regressions.

**Owner**: Security Team

**Review Date**: 2026-07-09

**Expiry Date**: 2026-10-07 (90 days)

**Action Required**: Confirm CI uses patched Starlette from lockfile, then remove this waiver.

---

### PYSEC-2026-141 / PYSEC-2026-142 (urllib3)

**Package**: `urllib3` (HTTP client transitive)

**Vulnerability**: Streaming decompression and cross-origin redirect credential handling advisories prior to 2.7.0.

**Severity**: Medium

**Status**: **ACCEPTED WITH MITIGATION**

**Rationale**:
1. Lockfile refresh pins `urllib3==2.7.0` which addresses these advisories; older environment reports are residual.
2. Outbound HTTP calls target configured first-party/Azure endpoints with bounded response handling.
3. Time-boxed until all CI jobs install the refreshed lock.

**Mitigation**:
- Prefer lockfile urllib3 ≥2.7.0.
- Avoid following untrusted cross-origin redirects with credentials.

**Alternative Considered**:
- Vendoring urllib3 is unnecessary once lock installs land.

**Owner**: Security Team

**Review Date**: 2026-07-09

**Expiry Date**: 2026-10-07 (90 days)

**Action Required**: Confirm CI urllib3 ≥2.7.0, then remove this waiver.

---

## Waiver Review Process

All security waivers must be reviewed every 90 days. Waivers that remain active beyond their expiry date must either:

1. Have the vulnerability patched and the waiver removed
2. Have the affected package replaced with a secure alternative
3. Have the waiver extended with explicit justification and updated risk assessment

**Last Reviewed**: 2026-07-09
