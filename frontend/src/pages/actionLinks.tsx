import { Navigate, useSearchParams } from 'react-router-dom'

/** RESTful permalink for an action detail page (`action_key` is URL-encoded). */
export function buildActionDetailPath(actionKey: string): string {
  const key = actionKey.trim()
  if (!key) return '/actions'
  return `/actions/${encodeURIComponent(key)}`
}

/** Decode `:id` route param from `/actions/:id` into an `action_key`. */
export function parseActionDetailId(id: string | undefined): string {
  if (!id?.trim()) return ''
  try {
    return decodeURIComponent(id.trim())
  } catch {
    return id.trim()
  }
}

/** Legacy `/actions/item?key=` → `/actions/:id` (replace). */
export function LegacyActionItemRedirect() {
  const [searchParams] = useSearchParams()
  const key = searchParams.get('key')?.trim()
  if (!key) return <Navigate to="/actions" replace />
  return <Navigate to={buildActionDetailPath(key)} replace />
}
