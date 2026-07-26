import { Link } from 'react-router-dom'
import { BookOpen, Keyboard, LifeBuoy, Mail } from 'lucide-react'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'

/**
 * Staff help destination for /help (PX-161).
 * Intentionally separate from the employee Portal Help Centre.
 */
export default function StaffHelp() {
  return (
    <div className="min-h-screen bg-surface" data-testid="staff-help-page">
      <header className="bg-card border-b border-border">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 py-8">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-primary/10 text-primary">
              <LifeBuoy className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-foreground">Help</h1>
              <p className="text-muted-foreground mt-1">
                Staff guidance for the Quality Governance Platform
              </p>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 sm:px-6 py-8 space-y-4">
        <Card className="p-5 space-y-2">
          <div className="flex items-center gap-2 font-semibold text-foreground">
            <Keyboard className="w-4 h-4" />
            Keyboard shortcuts
          </div>
          <p className="text-sm text-muted-foreground">
            Press <kbd className="px-1.5 py-0.5 rounded border border-border text-xs">Shift</kbd> +{' '}
            <kbd className="px-1.5 py-0.5 rounded border border-border text-xs">?</kbd> anywhere in
            the staff app for the shortcut overlay.
          </p>
        </Card>

        <Card className="p-5 space-y-2">
          <div className="flex items-center gap-2 font-semibold text-foreground">
            <BookOpen className="w-4 h-4" />
            Document library
          </div>
          <p className="text-sm text-muted-foreground">
            Policies, procedures and campaigns live in the Document Library.
          </p>
          <Button asChild variant="outline" size="sm">
            <Link to="/documents">Open Documents</Link>
          </Button>
        </Card>

        <Card className="p-5 space-y-2">
          <div className="flex items-center gap-2 font-semibold text-foreground">
            <Mail className="w-4 h-4" />
            Support contact
          </div>
          <p className="text-sm text-muted-foreground">
            Platform support details are configured under Admin → System Settings → Contact Details.
            If those fields are empty, ask your administrator to set them before go-live.
          </p>
          <Button asChild variant="outline" size="sm">
            <Link to="/admin/settings">Open System Settings</Link>
          </Button>
        </Card>

        <p className="text-xs text-muted-foreground pt-2">
          Looking for the employee portal help centre? That lives at{' '}
          <Link className="underline" to="/portal/help">
            /portal/help
          </Link>
          .
        </p>
      </main>
    </div>
  )
}
