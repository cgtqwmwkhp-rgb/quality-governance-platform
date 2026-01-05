# OpenAPI Schema

This directory contains the OpenAPI schema for the Quality Governance Platform API.

## Regeneration

To regenerate the `openapi.json` file, run the following command from the project root:

```bash
python3.11 scripts/generate_openapi.py
```

## Contract Gate

OpenAPI drift detection is a contract gate in the CI pipeline. It is designed to detect changes to the API surface and ensure that the OpenAPI schema is kept up to date. This gate is never transient or overridable; it is a permanent part of the quality governance process.

The `openapi-drift` job in the CI pipeline performs the following checks:

1.  **Determinism Proof:** It generates the OpenAPI schema twice and verifies that the checksums match. This is a **blocking** check.
2.  **Contract Invariants:** It runs a script to validate invariants on the OpenAPI schema, such as pagination parameters and authentication security. This is a **blocking** check.
3.  **Drift Detection:** It compares the generated schema with the committed snapshot and fails if there is a difference. This is a **blocking** check.
