import { Navigate } from 'react-router-dom'
import { hasRole } from '../utils/auth'

interface RequireRoleProps {
  allowed: string[]
  children: React.ReactNode
  fallback?: string
}

export default function RequireRole({
  allowed,
  children,
  fallback = '/dashboard',
}: RequireRoleProps) {
  if (!hasRole(...allowed)) {
    return <Navigate to={fallback} replace />
  }
  return <>{children}</>
}
