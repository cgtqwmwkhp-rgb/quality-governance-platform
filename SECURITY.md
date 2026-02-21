# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| latest  | Yes       |

## Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly:

1. **Do not** create a public GitHub issue
2. Email the security team with details
3. Include steps to reproduce if possible
4. Allow reasonable time for a fix before disclosure

## Security Measures

This platform implements:

- **Authentication**: JWT with token revocation and blacklisting
- **Authorization**: Role-based (RBAC) and attribute-based (ABAC) access control
- **Tenant Isolation**: Verified on every tenant-scoped request
- **Data Protection**: PII scrubbing in logs, field-level encryption for sensitive data
- **File Upload Security**: Magic number verification, extension allowlisting, size limits
- **Dependency Scanning**: Automated via pip-audit, safety, and Bandit in CI
- **Input Validation**: Pydantic schema validation on all API inputs
- **Rate Limiting**: Configurable per-endpoint rate limits
- **Security Headers**: HSTS, X-Frame-Options, X-Content-Type-Options, XSS Protection
- **CORS**: Configurable origin allowlisting

## Security Scanning

Run a local security scan:
```bash
./scripts/security_scan.sh
```
