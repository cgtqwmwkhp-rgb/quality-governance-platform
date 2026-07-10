import { Brain } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Button } from '../components/ui/Button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/Card'

/**
 * Honest unavailable state — no illustrative/demo analytics theatre.
 * Route kept so deep links and future wiring do not break.
 */
export default function AIIntelligence() {
  return (
    <div className="min-h-screen bg-background text-foreground p-6">
      <div className="mx-auto max-w-2xl space-y-6">
        <div>
          <h1 className="text-3xl font-bold text-foreground mb-2 flex items-center gap-3">
            <Brain className="w-8 h-8 text-primary" />
            AI Intelligence Hub
          </h1>
          <p className="text-muted-foreground">Predictive analytics are not available in production yet.</p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Not available yet</CardTitle>
            <CardDescription>
              This workspace will surface live predictions, anomalies, and recommendations when the
              backend intelligence services are ready. No sample or illustrative data is shown here.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            <Button asChild variant="outline">
              <Link to="/risk-register">Open Risk Register</Link>
            </Button>
            <Button asChild variant="outline">
              <Link to="/dashboard">Back to Dashboard</Link>
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
