# ADR-0002: Environment Strategy and Configuration Hardening

**Date**: 2026-01-04

**Status**: Accepted

## Context

The previous configuration management had several weaknesses:

1.  **Insecure Placeholders**: The `.env.example` file contained placeholder values that looked like real secrets (e.g., `your-secret-key-change-in-production`). This increases the risk of developers accidentally using these insecure defaults in a staging or even production environment.
2.  **No Runtime Validation**: The application did not perform any validation on configuration values at startup. This could lead to silent failures or unexpected behavior if critical settings (like `DATABASE_URL` or `SECRET_KEY`) were missing or misconfigured.
3.  **Unclear Environment Strategy**: There was no formal definition of different operating environments (e.g., development, testing, staging, production), making it difficult to manage environment-specific configurations securely.

## Decision

We will implement a robust environment and configuration strategy to ensure the application is secure, easy to configure, and fails fast when misconfigured.

### 1. Environment Strategy

We will adopt a standard four-tier environment strategy:

- **`development`**: For local development on developer machines. Uses local services (e.g., local Postgres or SQLite) and enables debug features.
- **`testing`**: Used by the CI/CD pipeline for running automated tests. Uses ephemeral services (e.g., Docker containers for Postgres).
- **`staging`**: A production-like environment for final testing, user acceptance testing (UAT), and integration validation before a production release. Connects to production-like infrastructure.
- **`production`**: The live environment serving end-users. Must have the highest level of security, monitoring, and performance.

The current environment is determined by the `APP_ENV` environment variable.

### 2. Configuration Hardening

- **Neutral Placeholders**: The `.env.example` file has been updated with neutral, non-functional placeholders (e.g., `__CHANGE_ME__`). This makes it obvious that a real value is required and prevents accidental use of defaults.
- **Clear Instructions**: The `.env.example` now includes comments guiding developers on how to generate secure secrets and which variables are optional.
- **Runtime Validation**: The `core.config.Settings` class now includes a validation method that runs at application startup. This validator will:
    - **Check for Default Secrets**: In production (`APP_ENV=production`), it will raise a `ValueError` if `SECRET_KEY` or `JWT_SECRET_KEY` are still set to the default placeholder values.
    - **Validate Database URL**: It ensures the `DATABASE_URL` is correctly formatted and, in production, is not pointing to a `localhost` address.

This "fail-fast" approach ensures that the application will refuse to start if it detects a critical misconfiguration, preventing potential security vulnerabilities and runtime errors.

## Consequences

### Positive

- **Improved Security**: Reduces the risk of using weak or default secrets in production.
- **Reduced Configuration Errors**: The application provides immediate, clear feedback if the configuration is invalid, saving debugging time.
- **Clearer Developer Workflow**: Developers have a clear template (`.env.example`) and understanding of how to configure the application for different environments.

### Negative

- **Slightly More Verbose Startup**: The application startup process is slightly more complex due to the added validation logic. This is a negligible cost for the significant security and stability benefits.

## Implementation Evidence

- **Hardened `.env.example`**: The updated file is located at the root of the repository.
- **Configuration Validation Logic**: The validation logic is implemented in the `__init__` and `_validate_production_settings` methods of the `Settings` class in `src/core/config.py`.
