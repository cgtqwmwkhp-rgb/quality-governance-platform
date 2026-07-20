import type { ReactNode } from 'react'
import { NavLink } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { FileText, FolderOpen, Megaphone } from 'lucide-react'
import { cn } from '../helpers/utils'

export type LibraryView = 'documents' | 'policies' | 'campaigns'

type LibraryShellProps = {
  activeView: LibraryView
  actions?: ReactNode
  children: ReactNode
}

const VIEW_SUBTITLE: Record<LibraryView, string> = {
  documents: 'documents.subtitle',
  policies: 'policies.subtitle',
  campaigns: 'admin.campaign_compliance.subtitle',
}

export function LibraryShell({ activeView, actions, children }: LibraryShellProps) {
  const { t } = useTranslation()

  const tabs: { view: LibraryView; path: string; labelKey: string; defaultLabel: string; icon: typeof FileText }[] = [
    { view: 'documents', path: '/documents', labelKey: 'nav.documents', defaultLabel: 'Documents', icon: FolderOpen },
    { view: 'policies', path: '/policies', labelKey: 'nav.policies', defaultLabel: 'Policies', icon: FileText },
    {
      view: 'campaigns',
      path: '/documents/campaigns',
      labelKey: 'nav.document_campaigns',
      defaultLabel: 'Document campaigns',
      icon: Megaphone,
    },
  ]

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4">
        <div className="space-y-3">
          <div>
            <h1 className="text-3xl font-bold text-foreground">{t('nav.library')}</h1>
            <p className="text-muted-foreground mt-1">{t(VIEW_SUBTITLE[activeView])}</p>
          </div>
          <nav aria-label={t('nav.library')} className="inline-flex rounded-lg bg-muted p-1 gap-1">
            {tabs.map(({ view, path, labelKey, defaultLabel, icon: Icon }) => (
              <NavLink
                key={view}
                to={path}
                aria-current={activeView === view ? 'page' : undefined}
                data-testid={`library-shell-tab-${view}`}
                className={({ isActive }) =>
                  cn(
                    'inline-flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium transition-all',
                    'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
                    isActive
                      ? 'bg-background text-foreground shadow-sm'
                      : 'text-muted-foreground hover:text-foreground',
                  )
                }
              >
                <Icon className="w-4 h-4" aria-hidden="true" />
                {t(labelKey, { defaultValue: defaultLabel })}
              </NavLink>
            ))}
          </nav>
        </div>
        {actions ? <div className="flex-shrink-0">{actions}</div> : null}
      </div>
      {children}
    </div>
  )
}
