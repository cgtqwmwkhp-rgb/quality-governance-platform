import api from '../api/client'

export interface PlatformReporterIdentity {
  reporter_name?: string
  reporter_email?: string
}

let cachedReporter: PlatformReporterIdentity | null | undefined

/** Test hook — reset module cache between Vitest cases. */
export function clearPlatformReporterCache(): void {
  cachedReporter = undefined
}

/**
 * Resolve the signed-in platform user as incident reporter metadata (PX-015).
 * Caches the first successful /auth/me response for the session.
 */
export async function resolvePlatformReporterIdentity(): Promise<PlatformReporterIdentity> {
  if (cachedReporter !== undefined) {
    return cachedReporter ?? {}
  }

  try {
    const response = await api.get<{
      full_name?: string | null
      email?: string | null
      first_name?: string | null
      last_name?: string | null
    }>('/api/v1/auth/me')
    const user = response.data
    const reporter_name =
      user.full_name?.trim() ||
      [user.first_name, user.last_name].filter(Boolean).join(' ').trim() ||
      user.email?.trim() ||
      undefined
    cachedReporter = {
      reporter_name,
      reporter_email: user.email?.trim() || undefined,
    }
  } catch {
    cachedReporter = {}
  }

  return cachedReporter ?? {}
}
