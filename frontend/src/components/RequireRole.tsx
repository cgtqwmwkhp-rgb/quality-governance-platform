import { Navigate } from 'react-router-dom'
import { hasRole, isSuperuser } from '../utils/auth'

interface RequireRoleProps {
  allowed: string[]
  children: React.ReactNode
  fallback?: string
  requireSuperuser?: boolean
}

export default function RequireRole({
  allowed,
  children,
  fallback = '/dashboard',
  requireSuperuser = false,
}: RequireRoleProps) {
  const hasAllowedRole = hasRole(...allowed)
  const passesSuperuserGate = !requireSuperuser || isSuperuser()

  if (!hasAllowedRole || !passesSuperuserGate) {
    return <Navigate to={fallback} replace />
  }
  return <>{children}</>
}
