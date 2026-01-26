# Login UX Contract

**Version**: 2.0  
**Status**: ACTIVE  
**Owner**: Principal Engineer (UX + QA + SRE)  
**P0 Gate**: YES

---

## 1. Overview

This contract defines the required behavior for the login experience. All implementations MUST conform to this contract. Violations are P0 failures.

---

## 2. State Machine

The login flow operates as a deterministic state machine with the following states:

```
┌─────────┐
│  idle   │◄─────────────────────────────────┐
└────┬────┘                                  │
     │ submit                                │
     ▼                                       │
┌─────────────┐                              │
│ submitting  │──── 250ms ────┐              │
└──────┬──────┘               │              │
       │                      ▼              │
       │            ┌─────────────────┐      │
       │            │ spinner_visible │      │
       │            └────────┬────────┘      │
       │                     │               │
       │ ◄───────────────────┘               │
       │                                     │
       │──── 3s ─────► slow_warning ────┐    │
       │                                │    │
       │◄───────────────────────────────┘    │
       │                                     │
       ├──── success ─────► ✅ redirect ─────┤
       │                                     │
       ├──── 401 ─────► error_unauthorized ──┤
       │                                     │
       ├──── 502/503 ─► error_unavailable ───┤
       │                                     │
       ├──── 5xx ─────► error_server ────────┤
       │                                     │
       ├──── network ─► error_network ───────┤
       │                                     │
       └──── 15s ─────► error_timeout ───────┘
```

### State Definitions

| State | Description | Exit Condition |
|-------|-------------|----------------|
| `idle` | Form ready for input | User submits form |
| `submitting` | Request in flight, spinner hidden | 250ms elapsed OR response received |
| `spinner_visible` | Spinner shown to user | Response received OR 15s timeout |
| `slow_warning` | "Still working..." shown | Response received OR 15s timeout |
| `error_timeout` | Timeout error shown | User action (retry/clear) |
| `error_unauthorized` | Invalid credentials shown | User action |
| `error_unavailable` | Service unavailable shown | User action |
| `error_server` | Server error shown | User action |
| `error_network` | Network error shown | User action |
| `success` | Login successful | Redirect to dashboard |

---

## 3. Bounded Error Codes

All errors MUST be classified into exactly one of these codes:

| Error Code | HTTP Status | Description | User Message |
|------------|-------------|-------------|--------------|
| `TIMEOUT` | N/A (15s) | Request timed out | "Request timed out. Please try again." |
| `UNAUTHORIZED` | 401 | Invalid credentials | "Incorrect email or password." |
| `UNAVAILABLE` | 502, 503 | Service temporarily unavailable | "Service temporarily unavailable. Please try again in a few minutes." |
| `SERVER_ERROR` | 500, 5xx | Internal server error | "Something went wrong. Please try again." |
| `NETWORK_ERROR` | N/A | Network/CORS failure | "Unable to connect. Please check your internet connection." |
| `UNKNOWN` | Other | Unclassified error | "An unexpected error occurred. Please try again." |

### Implementation Rule

```typescript
// Bounded error code enum - NO other values allowed
type LoginErrorCode = 
  | 'TIMEOUT'
  | 'UNAUTHORIZED'
  | 'UNAVAILABLE'
  | 'SERVER_ERROR'
  | 'NETWORK_ERROR'
  | 'UNKNOWN';
```

---

## 4. UI Requirements

### 4.1 Spinner Behavior

| Threshold | Behavior |
|-----------|----------|
| 0-250ms | No spinner (prevents flicker) |
| 250ms-3s | Spinner visible |
| 3s-15s | Spinner + "Still working..." message |
| >15s | TIMEOUT error state |

### 4.2 Error Display

Each error state MUST display:

1. **Error icon** (visual indicator)
2. **Error message** (from bounded list above)
3. **Recovery actions** (per error code)

### 4.3 Recovery Actions

| Error Code | Primary Action | Secondary Action |
|------------|----------------|------------------|
| `TIMEOUT` | Retry | Clear Session |
| `UNAUTHORIZED` | (none - user fixes input) | (none) |
| `UNAVAILABLE` | Retry | Status Page (optional) |
| `SERVER_ERROR` | Retry | Clear Session |
| `NETWORK_ERROR` | Retry | Clear Session |
| `UNKNOWN` | Retry | Clear Session |

### 4.4 Button States

| State | Submit Button |
|-------|---------------|
| `idle` | Enabled, shows "Sign In" |
| `submitting` | Disabled, shows spinner |
| `spinner_visible` | Disabled, shows spinner |
| `slow_warning` | Disabled, shows spinner |
| `error_*` | Enabled, shows "Sign In" |
| `success` | Disabled (redirecting) |

---

## 5. Performance Targets (P0)

### 5.1 Response Time Thresholds

| Environment | P50 Target | P95 Target | Hard Limit |
|-------------|------------|------------|------------|
| Staging | <2s | <5s | 15s (timeout) |
| Production | <3s | <7s | 15s (timeout) |

### 5.2 Duration Buckets (for telemetry)

| Bucket | Range | Classification |
|--------|-------|----------------|
| `fast` | 0-1s | Excellent |
| `normal` | 1-3s | Acceptable |
| `slow` | 3-7s | Warning |
| `very_slow` | 7-15s | Critical |
| `timeout` | >15s | Failure |

---

## 6. Telemetry Requirements

### 6.1 Bounded Events

All login telemetry MUST use these exact event names and dimensions:

```typescript
// Event: Login attempt completed
{
  name: 'login_completed',
  dimensions: {
    result: 'success' | 'error',
    errorCode?: LoginErrorCode,  // Only if result='error'
    durationBucket: 'fast' | 'normal' | 'slow' | 'very_slow' | 'timeout'
  }
}

// Event: Error shown to user
{
  name: 'login_error_shown',
  dimensions: {
    errorCode: LoginErrorCode
  }
}

// Event: Recovery action taken
{
  name: 'login_recovery_action',
  dimensions: {
    action: 'retry' | 'clear_session'
  }
}
```

### 6.2 No-PII Policy

**NEVER log:**
- Email addresses
- Passwords (even hashed)
- IP addresses
- Session tokens
- User agents (except browser family)
- Stack traces with user data

---

## 7. Test Requirements

### 7.1 E2E Tests (P0)

| Scenario | Expected Outcome |
|----------|------------------|
| Valid credentials | Redirect to dashboard |
| Invalid credentials | `UNAUTHORIZED` error shown |
| Slow response (3-7s) | `slow_warning` shown, then success/error |
| Timeout (>15s) | `TIMEOUT` error shown |
| 503 response | `UNAVAILABLE` error shown |
| Network failure | `NETWORK_ERROR` shown |
| Recovery: Retry | Error clears, form reset |
| Recovery: Clear Session | Page reloads, storage cleared |

### 7.2 Invariants (MUST always hold)

1. **No infinite spinner**: Spinner MUST clear within 15s
2. **Terminal state**: Every request ends in success OR error UI
3. **Button re-enabled**: After error, submit button is enabled
4. **Bounded errors**: Only defined error codes displayed

---

## 8. UX Coverage Gate

Login is a **P0 workflow** in the UX Coverage Gate:

```yaml
# WORKFLOW_REGISTRY.yaml
login:
  priority: P0
  page: /login
  actions:
    - id: login_submit
      priority: P0
      success_criteria:
        - redirect_to: /dashboard OR error_state_visible
        - spinner_cleared: true
        - button_enabled: true (on error)
```

### Gate Criteria

| Signal | GO | HOLD |
|--------|-----|------|
| Login loads | Page renders <2s | Fails to render |
| Login submit | Terminal state reached | Infinite spinner |
| Error handling | Bounded error shown | Unhandled error |

---

## 9. Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-26 | Principal Engineer | Initial: 15s timeout, basic retry |
| 2.0 | 2026-01-26 | Principal Engineer | Bounded error codes, state machine, telemetry, slow warning |

---

## 10. Attestation

This contract is binding. Violations are P0 incidents.

**Approved by**: Principal Engineer (UX + QA + SRE)  
**Effective date**: 2026-01-26
