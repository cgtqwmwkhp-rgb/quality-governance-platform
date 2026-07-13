import { Navigate } from 'react-router-dom'
import { CUSTOMER_AUDITS_AUDITS_PATH } from '../components/assuranceHubHelpers'

/** Legacy route — Customer Audits is an Assurance filter on Audits (IA-W3). */
export default function CustomerAudits() {
  return <Navigate to={CUSTOMER_AUDITS_AUDITS_PATH} replace />
}
