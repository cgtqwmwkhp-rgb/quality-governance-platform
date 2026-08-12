import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { X } from 'lucide-react'
import { Button, Card, CardContent } from '../../components/ui'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/Tabs'
import { EvidencePanelSlot } from './workspace/EvidencePanelSlot'
import { AuditsNcPanelSlot } from './workspace/AuditsNcPanelSlot'
import { ActionsPanelSlot } from './workspace/ActionsPanelSlot'
import { RisksPanelSlot } from './workspace/RisksPanelSlot'
import { CertsPanelSlot } from './workspace/CertsPanelSlot'
import type { FrameworkId } from './standardsMatrixFilters'
import { STANDARDS_MATRIX_FRAMEWORKS } from './standardsMatrixFilters'

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
 * Tab bodies are honest stubs until PR-B live graph joins land.
 */
export function EvidenceWorkspaceHost({ selection, onClose }: EvidenceWorkspaceHostProps) {
  const { t } = useTranslation()
  const [tab, setTab] = useState<WorkspaceTabId>('evidence')
  const framework =
    STANDARDS_MATRIX_FRAMEWORKS.find((f) => f.id === selection.frameworkId) ?? null

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
            <EvidencePanelSlot clauseNumber={selection.clauseNumber} />
          </TabsContent>
          <TabsContent value="audits">
            <AuditsNcPanelSlot clauseNumber={selection.clauseNumber} />
          </TabsContent>
          <TabsContent value="actions">
            <ActionsPanelSlot />
          </TabsContent>
          <TabsContent value="risks">
            <RisksPanelSlot />
          </TabsContent>
          <TabsContent value="certs">
            <CertsPanelSlot />
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  )
}
