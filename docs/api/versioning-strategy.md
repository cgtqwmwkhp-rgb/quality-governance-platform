# API versioning strategy

This document complements [API style guide](./style-guide.md), which describes how the live FastAPI app structures URLs, errors, pagination, and OpenAPI. Here we define **how API versions evolve**, what counts as breaking, how deprecations work, and how consumers prove compatibility.

---

## Versioning approach

- **URI versioning** is the single source of truth for the product API: all major application routers are mounted under **`/api/v1/`** (see `src/main.py` and `docs/api/style-guide.md`).
- **No header-based API versioning** (for example `Accept: application/vnd...`) is used for choosing major API shape. Clients rely on the path prefix.
- Operational and meta endpoints (for example `/health`, `/healthz`, `/readyz`, and some meta routes) may live outside `/api/v1/`; treat them as **platform contracts** documented separately, not as substitutes for versioned product APIs.

New major versions (for example `/api/v2/`) would be introduced alongside v1 only after deprecation policy has been satisfied for endpoints slated for removal or incompatible change.

---

## Breaking change policy

The following are **breaking** for public API consumers (they require a new major version segment or a new endpoint while keeping the old one):

| Change | Breaking? |
|--------|-----------|
| Removing a path or HTTP method | **Yes** |
| Removing a response field clients may rely on | **Yes** |
| Removing a request field that was accepted | **Yes** |
| Changing JSON type of a field (e.g. string → number, scalar → object) | **Yes** |
| Renaming a field without keeping the old name | **Yes** |
| Changing status code for the same success/failure scenario | **Yes** (unless documented as a bugfix and coordinated) |
| Tightening validation (rejecting payloads previously accepted) | **Usually yes** |
| Adding optional request fields | **No** |
| Adding response fields | **No** (clients should ignore unknown fields) |
| Adding new endpoints under the same version | **No** |

Breaking changes **must not** ship only under `/api/v1/` without following the deprecation process below.

---

## Deprecation process

1. **Signal sunset**  
   For deprecated routes or fields, responses should include a **`Sunset`** (or agreed successor) header and/or deprecation metadata as documented in release notes, consistent with team standards.

2. **Document in changelog**  
   Record the deprecation in the [API changelog](#api-changelog) (and product changelog if applicable): what is deprecated, replacement, and timeline.

3. **Minimum notice**  
   Maintain the deprecated surface for at least **90 days** after the first release that advertises the deprecation, unless a security or compliance exception is approved.

4. **Removal in next major**  
   Remove deprecated contracts in the **next major API version** (e.g. move removal to `/api/v2/` rollout), or remove in v1 only after the notice window and consumer sign-off if majors are not yet in use.

During the notice window, implementations should prefer **additive** v1 changes and dual support where feasible.

---

## API changelog

Use this template for each release (or grouped weekly) to track HTTP API changes:

```markdown
## API changelog — YYYY-MM-DD (release tag or version)

### Added
- `METHOD /api/v1/...` — short description
- Response field `...` on `...` (optional)

### Changed (non-breaking)
- Description; confirm no breaking criteria above

### Deprecated
- `METHOD /api/v1/...` — removal after YYYY-MM-DD; use `...` instead
- Field `...` — ignore after migration; replacement `...`

### Removed / Breaking (major only)
- N/A or list (only in major version bumps)

### Security / compliance
- Any auth, rate limit, or CORS-related changes

### References
- PR links, ADR links, OpenAPI diff summary
```

Keep entries aligned with **`openapi-baseline.json`** updates and contract tests.

---

## Consumer contract testing

- **Schemathesis / consumer tests** live under **`tests/contract/`**. They validate that the running app matches expectations derived from the published contract.
- **OpenAPI baseline** is tracked in repository root **`openapi-baseline.json`**. CI (**OpenAPI Contract Stability** job in `.github/workflows/ci.yml`) generates the current schema from `src.main:app` and checks compatibility with the baseline via `scripts/check_openapi_compatibility.py`.
- **Workflow**: when making intentional contract changes, update the baseline in a dedicated commit/PR after review; ensure **`tests/contract/`** passes locally and in CI.

---

## References

- [API style guide](./style-guide.md) — paths, errors, pagination, auth
- OpenAPI baseline: `openapi-baseline.json`
- Contract tests: `tests/contract/`
- CI: `.github/workflows/ci.yml` (openapi-contract-check, api-path-drift)
