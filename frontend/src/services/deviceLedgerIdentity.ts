/**
 * Who the device ledger belongs to.
 *
 * The audit device ledger is keyed by `tenant:user`, not by run id, because a
 * field tablet is shared. Keying by run id alone means the next auditor to open
 * AUD-2026-0087 on the same handset is offered the previous auditor's answers
 * and can restore them over their own — a signed record attributed to the wrong
 * person.
 *
 * The user id comes from the access token's `sub` claim, which is readable
 * synchronously and without a network call. The tenant id is **not** in the
 * token (`build_access_token_claims` only issues `is_superuser` / `roles`), so
 * it has to come from `GET /api/v1/auth/me` once and then be remembered:
 * resolving the namespace must not require the network, or the ledger would be
 * unavailable in exactly the situation it exists for.
 *
 * The remembered value is stored as `{userId}:{tenantId}` so a cached tenant can
 * never be handed to a different user — if the signed-in `sub` does not match,
 * the cache is treated as absent rather than reused.
 *
 * Nothing here is PII: two integers. No name, no email, no entity label.
 */
import { API_BASE_URL } from '../config/apiBase'
import { getCurrentUserId, getPlatformToken } from '../utils/auth'

/** Both halves of the namespace. Either one missing means "no namespace". */
export interface DeviceLedgerIdentity {
  tenantId: number
  userId: number
}

const IDENTITY_KEY = 'qgp_audit_ledger_identity'

/**
 * Deliberately `localStorage`, not `sessionStorage`: an auditor who closes the
 * tab and reopens it later in the shift must land on the same namespace, or
 * their own draft becomes unreadable to them.
 */
function readCached(): DeviceLedgerIdentity | null {
  try {
    const raw = localStorage.getItem(IDENTITY_KEY)
    if (!raw) return null
    const [rawUser, rawTenant] = raw.split(':')
    const userId = Number(rawUser)
    const tenantId = Number(rawTenant)
    if (!Number.isInteger(userId) || userId <= 0) return null
    if (!Number.isInteger(tenantId) || tenantId <= 0) return null
    return { tenantId, userId }
  } catch {
    return null
  }
}

function writeCached(identity: DeviceLedgerIdentity): void {
  try {
    localStorage.setItem(IDENTITY_KEY, `${identity.userId}:${identity.tenantId}`)
  } catch {
    // A private-mode quota failure means the namespace stays unresolved, which
    // the caller reports as "not durable on this device". It must not throw
    // into an audit save path.
  }
}

/** Forget the remembered tenant (deliberate sign-out). */
export function clearDeviceLedgerIdentity(): void {
  inFlight = null
  try {
    localStorage.removeItem(IDENTITY_KEY)
  } catch {
    // A missing entry is the desired end state anyway.
  }
}

/**
 * The current namespace, or null when it cannot be resolved without a network
 * call. Synchronous on purpose: the auth-loss flush in `api/client.ts` has to
 * resolve the namespace before `clearAuthState()` removes the token, and that
 * happens in the same tick as a hard redirect.
 */
export function getDeviceLedgerIdentity(): DeviceLedgerIdentity | null {
  const userId = getCurrentUserId()
  if (userId === null || userId <= 0) return null
  const cached = readCached()
  if (cached && cached.userId === userId) return cached
  return null
}

/** `t{tenant}:u{user}` — the key prefix every ledger row carries. */
export function deviceLedgerNamespace(identity: DeviceLedgerIdentity): string {
  return `t${identity.tenantId}:u${identity.userId}`
}

/**
 * Resolve and remember the tenant id if it is not known yet.
 *
 * Uses bare `fetch` rather than the axios client because `api/client.ts`
 * imports the draft store (for the auth-loss flush) and the draft store imports
 * this module — going through the client would close that cycle at module-init
 * time. `revokeSession()` in `utils/auth.ts` calls `/auth/logout` the same way
 * for the same reason.
 *
 * Never throws. A failure leaves the namespace unresolved, which the ledger
 * reports honestly as "not durable on this device" rather than writing under a
 * guessed tenant.
 */
export async function primeDeviceLedgerIdentity(): Promise<DeviceLedgerIdentity | null> {
  const existing = getDeviceLedgerIdentity()
  if (existing) return existing
  // Single-flight: the execute page primes from two effects (durability check and
  // draft recovery) that both mount in the same tick, and neither should cost a
  // second round trip.
  if (!inFlight) {
    inFlight = resolveIdentity().finally(() => {
      inFlight = null
    })
  }
  return inFlight
}

let inFlight: Promise<DeviceLedgerIdentity | null> | null = null

async function resolveIdentity(): Promise<DeviceLedgerIdentity | null> {
  const userId = getCurrentUserId()
  if (userId === null || userId <= 0) return null

  const token = getPlatformToken()
  if (!token) return null

  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (!response.ok) return null
    const body = (await response.json()) as { id?: unknown; tenant_id?: unknown }
    const tenantId = Number(body?.tenant_id)
    if (!Number.isInteger(tenantId) || tenantId <= 0) return null
    // Trust the token's `sub` over the body's id: the namespace must match what
    // the synchronous path will compute later.
    const identity: DeviceLedgerIdentity = { tenantId, userId }
    writeCached(identity)
    return identity
  } catch {
    return null
  }
}
