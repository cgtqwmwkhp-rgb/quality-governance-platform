import { useNavigate } from 'react-router-dom'
import { ArrowLeft, HelpCircle } from 'lucide-react'
import { Button } from '../components/ui/Button'

/** Portal-scoped 404 — keeps employees inside portal chrome (PX-311). */
export default function PortalNotFound() {
  const navigate = useNavigate()

  return (
    <div
      data-testid="portal-not-found"
      className="min-h-screen bg-surface flex flex-col items-center justify-center px-4 text-center"
    >
      <div className="text-6xl font-bold text-muted-foreground/30 mb-4">404</div>
      <h1 className="text-2xl font-semibold text-foreground mb-2">Page not found</h1>
      <p className="text-muted-foreground mb-8 max-w-md">
        That portal link is not valid. Return to the Employee Portal home or open Help if you
        need assistance.
      </p>
      <div className="flex flex-col sm:flex-row gap-3 w-full max-w-sm">
        <Button variant="outline" className="flex-1" onClick={() => navigate(-1)}>
          <ArrowLeft className="w-4 h-4" />
          Go back
        </Button>
        <Button className="flex-1" onClick={() => navigate('/portal')}>
          Back to Employee Portal
        </Button>
        <Button variant="outline" className="flex-1" onClick={() => navigate('/portal/help')}>
          <HelpCircle className="w-4 h-4" />
          Help & Support
        </Button>
      </div>
    </div>
  )
}
