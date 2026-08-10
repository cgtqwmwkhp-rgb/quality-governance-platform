import { useTranslation } from 'react-i18next'
import { ArrowLeft, Save, CheckCircle, Sparkles } from 'lucide-react'
import { IconButton } from '../../components/ui/IconButton'
import SaveIssueBanner from './SaveIssueBanner'
import type { SaveIssue } from './saveErrorModel'

export interface TemplateHeaderProps {
  templateName: string
  templateStatus: 'draft' | 'published' | 'archived'
  templateVersion: string
  totalQuestions: number
  activeTab: 'builder' | 'settings' | 'preview'
  onTabChange: (tab: 'builder' | 'settings' | 'preview') => void
  onNameChange: (name: string) => void
  onBack: () => void
  onSave: () => void
  isSaving: boolean
  onPublish: () => void
  canPublish: boolean
  onAIAssist: () => void
  /** Legacy summary string; prefer saveIssues when available. */
  saveError: string | null
  saveIssues?: SaveIssue[] | null
  onShowSaveIssueQuestion?: (questionId: string) => void
}

export default function TemplateHeader({
  templateName,
  templateStatus,
  templateVersion,
  totalQuestions,
  activeTab,
  onTabChange,
  onNameChange,
  onBack,
  onSave,
  isSaving,
  onPublish,
  canPublish,
  onAIAssist,
  saveError,
  saveIssues = null,
  onShowSaveIssueQuestion,
}: TemplateHeaderProps) {
  const { t } = useTranslation()
  const showBanner = (saveIssues && saveIssues.length > 0) || !!saveError

  return (
    <header className="sticky top-0 z-40 bg-card/80 backdrop-blur-xl border-b border-border">
      <div className="max-w-7xl mx-auto px-4 py-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <IconButton
              label={t('common.back')}
              onClick={onBack}
              className="h-auto w-auto p-2 hover:bg-secondary rounded-lg transition-colors"
            >
              <ArrowLeft className="w-5 h-5 text-muted-foreground" aria-hidden="true" />
            </IconButton>
            <div>
              <input
                type="text"
                value={templateName}
                onChange={(e) => onNameChange(e.target.value)}
                placeholder={t('audit_builder.untitled_template')}
                aria-label={t('audit_builder.template_name', 'Template name')}
                className="bg-transparent text-xl font-bold text-foreground placeholder:text-muted-foreground focus:outline-none"
              />
              <div className="flex items-center gap-2 mt-1">
                <span
                  className={`px-2 py-0.5 text-xs rounded ${
                    templateStatus === 'published'
                      ? 'bg-success/20 text-success'
                      : templateStatus === 'archived'
                        ? 'bg-muted text-muted-foreground'
                        : 'bg-warning/20 text-warning'
                  }`}
                >
                  {templateStatus}
                </span>
                <span className="text-xs text-muted-foreground">v{templateVersion}</span>
                <span className="text-xs text-muted-foreground">•</span>
                <span className="text-xs text-muted-foreground">{totalQuestions} questions</span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div className="flex bg-secondary rounded-lg p-1">
              {(['builder', 'settings', 'preview'] as const).map((tab) => (
                <button
                  key={tab}
                  onClick={() => onTabChange(tab)}
                  className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
                    activeTab === tab
                      ? 'bg-primary text-primary-foreground'
                      : 'text-muted-foreground hover:text-foreground'
                  }`}
                >
                  {tab.charAt(0).toUpperCase() + tab.slice(1)}
                </button>
              ))}
            </div>

            <button
              onClick={onAIAssist}
              className="flex items-center gap-2 px-3 py-2 bg-accent border border-primary/30 rounded-lg text-primary hover:bg-primary/30 transition-colors"
            >
              <Sparkles className="w-4 h-4" />
              {t('audit_builder.ai_assist')}
            </button>

            <div className="flex items-center gap-2">
              <button
                onClick={onPublish}
                disabled={!canPublish}
                className="flex items-center gap-2 px-4 py-2 bg-emerald-600 text-white font-medium rounded-lg hover:bg-emerald-700 transition-opacity disabled:opacity-50"
              >
                <CheckCircle className="w-4 h-4" />
                Publish
              </button>
              <button
                onClick={onSave}
                disabled={isSaving}
                className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground font-medium rounded-lg hover:bg-primary/90 transition-opacity disabled:opacity-50"
              >
                {isSaving ? (
                  <div className="w-4 h-4 border-2 border-foreground/30 border-t-foreground rounded-full animate-spin" />
                ) : (
                  <Save className="w-4 h-4" />
                )}
                {t('audit_builder.save')}
              </button>
            </div>
          </div>
        </div>
        {showBanner && (
          <div className="mt-3">
            {saveIssues && saveIssues.length > 0 ? (
              <SaveIssueBanner
                summary={saveError || `Fix ${saveIssues.length} issue(s), then try again.`}
                issues={saveIssues}
                onShowQuestion={onShowSaveIssueQuestion}
              />
            ) : (
              saveError && (
                <p className="text-sm text-destructive" role="alert">
                  {saveError}
                </p>
              )
            )}
          </div>
        )}
      </div>
    </header>
  )
}
