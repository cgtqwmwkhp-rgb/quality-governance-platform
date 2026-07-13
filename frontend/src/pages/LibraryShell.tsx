import type { ReactNode } from 'react'
import { NavLink } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { FileText, FolderOpen } from 'lucide-react'
import { cn } from '../helpers/utils'

export type LibraryView = 'documents' | 'policies'

type LibraryShellProps = {
  activeView: LibraryView
  actions?: ReactNode
  children: ReactNode
}

const VIEW_SUBTITLE: Record<LibraryView, string> = {
  documents: 'documents.subtitle',
  policies: 'policies.subtitle',
}

export function LibraryShell({ activeView, actions, children }: LibraryShellProps) {
  const { t } = useTranslation()

  const tabs: { view: LibraryView; path: string; labelKey: string; icon: typeof FileText }[] = [
    { view: 'documents', path: '/documents', labelKey: 'nav.documents', icon: FolderOpen },
    { view: 'policies', path: '/policies', labelKey: 'nav.policies', icon: FileText },
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
            {tabs.map(({ view, path, labelKey, icon: Icon }) => (
              <NavLink
                key={view}
                to={path}
                aria-current={activeView === view ? 'page' : undefined}
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
                {t(labelKey)}
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
