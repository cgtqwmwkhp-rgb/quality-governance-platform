import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { ArrowUpRight, X } from 'lucide-react'
import { Badge, Button, Card, CardContent } from '../../components/ui'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/Tabs'
import { EvidencePanelSlot } from './workspace/EvidencePanelSlot'
import { AuditsNcPanelSlot } from './workspace/AuditsNcPanelSlot'
import { ActionsPanelSlot } from './workspace/ActionsPanelSlot'
import { RisksPanelSlot } from './workspace/RisksPanelSlot'
import { CertsPanelSlot } from './workspace/CertsPanelSlot'
import { ExactShareBanner } from './workspace/ExactShareBanner'
import { useStandardsCellAggregate } from './workspace/useStandardsCellAggregate'
import type { FrameworkId } from './standardsMatrixFilters'
import { STANDARDS_MATRIX_FRAMEWORKS } from './standardsMatrixFilters'
import { scheduleProgrammeHref } from './scheduleProgrammeContext'

export type WorkspaceTabId = 'evidence' | 'audits' | 'actions' | 'risks' | 'certs'

export interface EvidenceWorkspaceSelection {
  frameworkId: FrameworkId
  clauseNumber: string
  clauseTitle: string
}

interface EvidenceWorkspaceHostProps {
  selection: EvidenceWorkspaceSelection
  onClose: () => void
}

/**
 * Full-page workspace host (not a drawer/Sheet) for a selected matrix cell/clause.
 * Fetches cell aggregate once and shares it across extracted panels (PR-B).
 */
export function EvidenceWorkspaceHost({ selection, onClose }: EvidenceWorkspaceHostProps) {
  const { t } = useTranslation()
  const [tab, setTab] = useState<WorkspaceTabId>('evidence')
  const framework =
    STANDARDS_MATRIX_FRAMEWORKS.find((f) => f.id === selection.frameworkId) ?? null
  const { data, loading, error, refetch } = useStandardsCellAggregate(
    selection.frameworkId,
    selection.clauseNumber,
  )
  const panelProps = {
    data,
    loading,
    error,
    frameworkId: selection.frameworkId,
    clauseNumber: selection.clauseNumber,
  }

  return (
    <Card data-testid="evidence-workspace-host" className="border-primary/20">
      <CardContent className="p-4 sm:p-6 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
          <div>
            <p className="text-xs uppercase tracking-wide text-muted-foreground">
              {t('compliance.standards_workspace.title', { defaultValue: 'Evidence workspace' })}
            </p>
            <h2 className="text-lg font-semibold text-foreground mt-1">
              {framework?.label ?? selection.frameworkId} · {selection.clauseNumber}
            </h2>
            <p className="text-sm text-muted-foreground mt-0.5">{selection.clauseTitle}</p>
            {data ? (
              <div className="flex flex-wrap items-center gap-2 mt-2">
                <Badge variant="secondary" data-testid="workspace-live-verdict">
                  {t(`compliance.standards_matrix.verdict.${data.verdict}`, {
                    defaultValue: String(data.verdict),
                  })}
                </Badge>
                {data.cover_blocked ? (
                  <Badge variant="destructive" data-testid="workspace-cover-blocked">
                    {t('compliance.standards_workspace.cover_blocked_badge', {
                      defaultValue: 'Cover blocked',
                    })}
                  </Badge>
                ) : null}
                {data.recurrence_red_flag ? (
                  <Badge variant="destructive" data-testid="workspace-recurrence-badge">
                    {t('compliance.standards_workspace.recurrence_badge', {
                      defaultValue: 'Recurrence',
                    })}
                  </Badge>
                ) : null}
              </div>
            ) : null}
            <div className="mt-3">
              <Button variant="outline" size="sm" asChild>
                <Link
                  to={scheduleProgrammeHref(selection.frameworkId, selection.clauseNumber)}
                  data-testid="workspace-deep-link-schedule"
                >
                  {t('compliance.standards_workspace.open_schedule', {
                    defaultValue: 'Open Compliance Schedule',
                  })}
                  <ArrowUpRight className="w-3.5 h-3.5 ml-1" aria-hidden="true" />
                </Link>
              </Button>
            </div>
          </div>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={onClose}
            aria-label={t('compliance.standards_workspace.close', { defaultValue: 'Close workspace' })}
            data-testid="evidence-workspace-close"
          >
            <X className="w-4 h-4" aria-hidden="true" />
          </Button>
        </div>

        <ExactShareBanner
          frameworkId={selection.frameworkId}
          clauseNumber={selection.clauseNumber}
          exactShare={data?.exact_share}
          onShared={refetch}
        />

        <Tabs
          value={tab}
          onValueChange={(next) => setTab(next as WorkspaceTabId)}
          data-testid="evidence-workspace-tabs"
        >
          <TabsList aria-label={t('compliance.standards_workspace.tabs_aria', { defaultValue: 'Workspace sections' })}>
            <TabsTrigger value="evidence">
              {t('compliance.standards_workspace.tab.evidence', { defaultValue: 'Evidence' })}
            </TabsTrigger>
            <TabsTrigger value="audits">
              {t('compliance.standards_workspace.tab.audits', { defaultValue: 'Audits & NC' })}
            </TabsTrigger>
            <TabsTrigger value="actions">
              {t('compliance.standards_workspace.tab.actions', { defaultValue: 'Actions' })}
            </TabsTrigger>
            <TabsTrigger value="risks">
              {t('compliance.standards_workspace.tab.risks', { defaultValue: 'Risks' })}
            </TabsTrigger>
            <TabsTrigger value="certs">
              {t('compliance.standards_workspace.tab.certs', { defaultValue: 'Certs' })}
            </TabsTrigger>
          </TabsList>

          <TabsContent value="evidence">
            <EvidencePanelSlot {...panelProps} />
          </TabsContent>
          <TabsContent value="audits">
            <AuditsNcPanelSlot {...panelProps} />
          </TabsContent>
          <TabsContent value="actions">
            <ActionsPanelSlot {...panelProps} />
          </TabsContent>
          <TabsContent value="risks">
            <RisksPanelSlot {...panelProps} />
          </TabsContent>
          <TabsContent value="certs">
            <CertsPanelSlot {...panelProps} />
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  )
}
