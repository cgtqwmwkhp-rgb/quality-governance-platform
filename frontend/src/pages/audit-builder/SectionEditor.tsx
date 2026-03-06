import { useTranslation } from 'react-i18next';
import {
  GripVertical,
  ChevronDown,
  ChevronRight,
  ListChecks,
  Plus,
  Trash2,
} from 'lucide-react';
import type { Section, Question } from './types';
import QuestionEditor from './QuestionEditor';

export interface SectionEditorProps {
  section: Section;
  onUpdate: (updates: Partial<Section>) => void;
  onDelete: () => void;
  onAddQuestion: () => void;
  onUpdateQuestion: (questionId: string, updates: Partial<Question>) => void;
  onDeleteQuestion: (questionId: string) => void;
  onDuplicateQuestion: (questionId: string) => void;
}

export default function SectionEditor({
  section,
  onUpdate,
  onDelete,
  onAddQuestion,
  onUpdateQuestion,
  onDeleteQuestion,
  onDuplicateQuestion,
}: SectionEditorProps) {
  const { t } = useTranslation();

  return (
    <div className="bg-card/50 border border-border rounded-2xl overflow-hidden">
      <div
        className={`bg-gradient-to-r ${section.color || 'from-blue-500 to-cyan-500'} p-0.5`}
      >
        <div className="bg-card p-4">
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
        </div>
      </div>

      {section.isExpanded && (
        <div className="p-4 space-y-3">
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
  );
}
