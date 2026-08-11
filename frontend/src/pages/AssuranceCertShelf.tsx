/**
 * Legacy Certificate shelf route entry.
 * Certificates now live as a Compliance Schedule view — this file redirects
 * so old imports/tests that resolve the page module still resolve, while the
 * App route sends users to `/compliance-schedule?view=certificates`.
 */
import { Navigate } from 'react-router-dom'

export default function AssuranceCertShelf() {
  return <Navigate to="/compliance-schedule?view=certificates" replace />
}
