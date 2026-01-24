# Security Vulnerability Waivers

This document tracks security vulnerabilities that have been reviewed and accepted with documented risk mitigation.

## Active Waivers

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

## Waiver Review Process

All security waivers must be reviewed every 90 days. Waivers that remain active beyond their expiry date must either:

1. Have the vulnerability patched and the waiver removed
2. Have the affected package replaced with a secure alternative
3. Have the waiver extended with explicit justification and updated risk assessment

**Last Reviewed**: 2026-01-04
