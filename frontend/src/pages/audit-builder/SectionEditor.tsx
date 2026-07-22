import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  GripVertical,
  ChevronDown,
  ChevronRight,
  ListChecks,
  Plus,
  Trash2,
  GitBranch,
} from 'lucide-react'
import type { Section, Question } from './types'
import { ASSESSMENT_MODES } from './types'
import QuestionEditor from './QuestionEditor'
import { safetyAssetsApi, type SafetyAssetType } from '../../api/safetyAssetsClient'

export interface SectionEditorProps {
  section: Section
  onUpdate: (updates: Partial<Section>) => void
  onDelete: () => void
  onAddQuestion: () => void
  onUpdateQuestion: (questionId: string, updates: Partial<Question>) => void
  onDeleteQuestion: (questionId: string) => void
  onDuplicateQuestion: (questionId: string) => void
  sectionValidationErrors?: string[]
  questionValidationErrors?: Record<string, string[]>
  /** All questions across the template (for conditional-logic source pickers). */
  allQuestions?: Question[]
}

function toggleValue<T>(list: T[] | null | undefined, value: T): T[] {
  const current = list ?? []
  return current.includes(value) ? current.filter((v) => v !== value) : [...current, value]
}

/** Simple multi-select applicability editor: which assessment modes / asset types a
 * section applies to. Empty selection on a dimension means "always applicable". */
function SectionApplicabilityEditor({
  section,
  onUpdate,
}: {
  section: Section
  onUpdate: (updates: Partial<Section>) => void
}) {
  const [assetTypes, setAssetTypes] = useState<SafetyAssetType[]>([])
  const [isOpen, setIsOpen] = useState(false)

  useEffect(() => {
    if (!isOpen || assetTypes.length > 0) return
    safetyAssetsApi
      .listAssetTypes({ page_size: 100, is_active: true })
      .then(({ data }) => setAssetTypes(data.items))
      .catch(() => setAssetTypes([]))
  }, [isOpen, assetTypes.length])

  const rules = section.applicabilityRules
  const selectedModes = rules?.assessmentModes ?? []
  const selectedAssetTypeIds = rules?.assetTypeIds ?? []
  const hasRestrictions = selectedModes.length > 0 || selectedAssetTypeIds.length > 0

  return (
    <div className="mt-3">
      <button
        type="button"
        onClick={() => setIsOpen((open) => !open)}
        className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
        data-testid={`section-applicability-toggle-${section.id}`}
      >
        <GitBranch className="w-3 h-3" />
        Applicability rules
        {hasRestrictions && (
          <span className="px-1.5 py-0.5 bg-primary/20 text-primary rounded text-[10px]">
            Restricted
          </span>
        )}
        <ChevronRight className={`w-3 h-3 transition-transform ${isOpen ? 'rotate-90' : ''}`} />
      </button>

      {isOpen && (
        <div className="mt-2 grid grid-cols-2 gap-3 p-3 bg-muted rounded-lg">
          <div>
            <p className="text-xs text-muted-foreground mb-1">
              Assessment modes (blank = all modes)
            </p>
            <div className="flex flex-wrap gap-1.5">
              {ASSESSMENT_MODES.map((mode) => (
                <button
                  key={mode.value}
                  type="button"
                  data-testid={`section-mode-${section.id}-${mode.value}`}
                  onClick={() =>
                    onUpdate({
                      applicabilityRules: {
                        ...section.applicabilityRules,
                        assessmentModes: toggleValue(selectedModes, mode.value),
                      },
                    })
                  }
                  className={`px-2 py-1 rounded text-xs transition-colors ${
                    selectedModes.includes(mode.value)
                      ? 'bg-primary/20 text-primary border border-primary/40'
                      : 'bg-secondary text-muted-foreground border border-border hover:bg-secondary/70'
                  }`}
                >
                  {mode.label}
                </button>
              ))}
            </div>
          </div>
          <div>
            <p className="text-xs text-muted-foreground mb-1">
              Asset types (blank = all asset types)
            </p>
            <div className="flex flex-wrap gap-1.5 max-h-24 overflow-y-auto">
              {assetTypes.length === 0 ? (
                <p className="text-xs text-muted-foreground italic">No asset types found</p>
              ) : (
                assetTypes.map((assetType) => (
                  <button
                    key={assetType.id}
                    type="button"
                    data-testid={`section-asset-type-${section.id}-${assetType.id}`}
                    onClick={() =>
                      onUpdate({
                        applicabilityRules: {
                          ...section.applicabilityRules,
                          assetTypeIds: toggleValue(selectedAssetTypeIds, assetType.id),
                        },
                      })
                    }
                    className={`px-2 py-1 rounded text-xs transition-colors ${
                      selectedAssetTypeIds.includes(assetType.id)
                        ? 'bg-primary/20 text-primary border border-primary/40'
                        : 'bg-secondary text-muted-foreground border border-border hover:bg-secondary/70'
                    }`}
                  >
                    {assetType.name}
                  </button>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default function SectionEditor({
  section,
  onUpdate,
  onDelete,
  onAddQuestion,
  onUpdateQuestion,
  onDeleteQuestion,
  onDuplicateQuestion,
  sectionValidationErrors = [],
  questionValidationErrors = {},
  allQuestions = [],
}: SectionEditorProps) {
  const { t } = useTranslation()

  return (
    // overflow-visible so question-type dropdowns are not clipped by the section card
    <div className="bg-card/50 border border-border rounded-2xl">
      <div
        className={`rounded-t-2xl overflow-hidden bg-gradient-to-r ${section.color || 'from-blue-500 to-cyan-500'} p-0.5`}
      >
        <div className="bg-card p-4 rounded-t-[0.9rem]">
          <div className="flex items-center gap-3">
            <div className="p-1.5 bg-secondary rounded cursor-grab hover:bg-muted">
              <GripVertical className="w-5 h-5 text-muted-foreground" />
            </div>

            <button
              type="button"
              onClick={() => onUpdate({ isExpanded: !section.isExpanded })}
              className="p-1"
            >
              {section.isExpanded ? (
                <ChevronDown className="w-5 h-5 text-foreground" />
              ) : (
                <ChevronRight className="w-5 h-5 text-foreground" />
              )}
            </button>

            <div className="flex-1">
              <input
                type="text"
                value={section.title}
                onChange={(e) => onUpdate({ title: e.target.value })}
                placeholder="Section title..."
                className="w-full bg-transparent text-lg font-semibold text-foreground placeholder:text-muted-foreground focus:outline-none"
              />
              <input
                type="text"
                value={section.description || ''}
                onChange={(e) => onUpdate({ description: e.target.value })}
                placeholder="Section description..."
                className="w-full bg-transparent text-sm text-muted-foreground placeholder:text-muted-foreground focus:outline-none mt-1"
              />
            </div>

            <div className="flex items-center gap-2">
              <span className="px-2 py-1 bg-secondary rounded-lg text-xs text-foreground">
                {section.questions.length} questions
              </span>
              <div className="flex items-center gap-1">
                <span className="text-xs text-muted-foreground">Weight:</span>
                <input
                  type="number"
                  value={section.weight}
                  onChange={(e) => onUpdate({ weight: parseFloat(e.target.value) || 1 })}
                  min="0"
                  max="10"
                  step="0.5"
                  className="w-14 px-2 py-1 bg-secondary border border-border rounded text-sm text-foreground text-center"
                />
              </div>
              <button
                type="button"
                onClick={onDelete}
                className="p-1.5 text-muted-foreground hover:text-destructive rounded"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          </div>
          <SectionApplicabilityEditor section={section} onUpdate={onUpdate} />
        </div>
      </div>

      {section.isExpanded && (
        <div className="p-4 space-y-3">
          {sectionValidationErrors.length > 0 && (
            <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
              {sectionValidationErrors.map((error) => (
                <p key={error}>{error}</p>
              ))}
            </div>
          )}
          {section.questions.length === 0 ? (
            <div className="text-center py-8">
              <ListChecks className="w-12 h-12 mx-auto text-muted-foreground mb-3" />
              <p className="text-muted-foreground mb-4">No questions in this section</p>
              <button
                type="button"
                onClick={onAddQuestion}
                className="inline-flex items-center gap-2 px-4 py-2 bg-primary/20 text-primary rounded-lg hover:bg-primary/30 transition-colors"
              >
                <Plus className="w-4 h-4" />
                {t('audit_builder.add_question')}
              </button>
            </div>
          ) : (
            <>
              {section.questions.map((question) => (
                <QuestionEditor
                  key={question.id}
                  question={question}
                  onUpdate={onUpdateQuestion}
                  onDelete={onDeleteQuestion}
                  onDuplicate={onDuplicateQuestion}
                  validationErrors={questionValidationErrors[question.id] || []}
                  allQuestions={allQuestions}
                />
              ))}
              <button
                type="button"
                onClick={onAddQuestion}
                className="w-full py-3 border-2 border-dashed border-border rounded-xl text-muted-foreground hover:border-primary hover:text-primary transition-colors flex items-center justify-center gap-2"
              >
                <Plus className="w-4 h-4" />
                {t('audit_builder.add_question')}
              </button>
            </>
          )}
        </div>
      )}
    </div>
  )
}
