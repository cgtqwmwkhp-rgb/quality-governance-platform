import { hasRole, isSuperuser } from './auth'

/** Mirrors backend ``_is_workforce_manager`` in ``src/api/routes/engineers.py``."""
export function isWorkforceManager(): boolean {
  return isSuperuser() || hasRole('admin', 'supervisor')
}
