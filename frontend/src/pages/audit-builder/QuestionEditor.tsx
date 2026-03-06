import { useState } from 'react';
import {
  GripVertical,
  Copy,
  Settings,
  ChevronDown,
  ChevronRight,
  CheckCircle,
  XCircle,
  ToggleLeft,
  ToggleRight,
  Type,
  Hash,
  Calendar,
  Camera,
  FileSignature,
  ListChecks,
  Scale,
  MessageSquare,
  AlertTriangle,
  Star,
  Plus,
  Trash2,
} from 'lucide-react';
import type { Question, QuestionType, QuestionOption } from './types';
import { generateId } from './types';

export const QUESTION_TYPES: { type: QuestionType; label: string; icon: React.ElementType; description: string }[] = [
  { type: 'yes_no', label: 'Yes / No', icon: ToggleLeft, description: 'Binary choice' },
  { type: 'yes_no_na', label: 'Yes / No / N/A', icon: ToggleRight, description: 'With not applicable option' },
  { type: 'pass_fail', label: 'Pass / Fail', icon: CheckCircle, description: 'Compliance check' },
  { type: 'scale_1_5', label: 'Scale 1-5', icon: Star, description: 'Rating scale' },
  { type: 'scale_1_10', label: 'Scale 1-10', icon: Scale, description: 'Detailed rating' },
  { type: 'multi_choice', label: 'Multiple Choice', icon: ListChecks, description: 'Select one option' },
  { type: 'checklist', label: 'Checklist', icon: CheckCircle, description: 'Multiple selections' },
  { type: 'text_short', label: 'Short Text', icon: Type, description: 'Single line response' },
  { type: 'text_long', label: 'Long Text', icon: MessageSquare, description: 'Multi-line response' },
  { type: 'numeric', label: 'Numeric', icon: Hash, description: 'Number input' },
  { type: 'date', label: 'Date', icon: Calendar, description: 'Date picker' },
  { type: 'photo', label: 'Photo', icon: Camera, description: 'Image capture' },
  { type: 'signature', label: 'Signature', icon: FileSignature, description: 'Digital signature' },
];

export interface QuestionEditorProps {
  question: Question;
  onUpdate: (questionId: string, updates: Partial<Question>) => void;
  onDelete: (questionId: string) => void;
  onDuplicate: (questionId: string) => void;
}

function QuestionTypeSelector({
  selectedType,
  onSelect,
}: {
  selectedType: QuestionType;
  onSelect: (type: QuestionType) => void;
}) {
  const [isOpen, setIsOpen] = useState(false);
  const selected = QUESTION_TYPES.find(t => t.type === selectedType);

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 px-3 py-2 bg-input border border-input rounded-lg text-sm text-foreground hover:bg-muted transition-colors"
      >
        {selected && <selected.icon className="w-4 h-4 text-primary" />}
        <span>{selected?.label}</span>
        <ChevronDown className={`w-4 h-4 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {isOpen && (
        <div className="absolute z-20 mt-1 w-64 bg-secondary border border-border rounded-xl shadow-xl overflow-hidden">
          <div className="max-h-80 overflow-y-auto p-2 space-y-1">
            {QUESTION_TYPES.map((type) => (
              <button
                key={type.type}
                type="button"
                onClick={() => {
                  onSelect(type.type);
                  setIsOpen(false);
                }}
                className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-left transition-colors ${
                  selectedType === type.type
                    ? 'bg-primary/20 text-primary'
                    : 'hover:bg-muted text-foreground'
                }`}
              >
                <type.icon className="w-4 h-4 text-primary" />
                <div>
                  <p className="text-sm font-medium">{type.label}</p>
                  <p className="text-xs text-muted-foreground">{type.description}</p>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default function QuestionEditor({
  question,
  onUpdate,
  onDelete,
  onDuplicate,
}: QuestionEditorProps) {
  const [showAdvanced, setShowAdvanced] = useState(false);

  const handleOptionAdd = () => {
    const newOptions = [
      ...(question.options || []),
      { id: generateId(), label: '', value: '', score: 0 }
    ];
    onUpdate(question.id, { options: newOptions });
  };

  const handleOptionUpdate = (optionId: string, updates: Partial<QuestionOption>) => {
    const newOptions = (question.options || []).map(opt =>
      opt.id === optionId ? { ...opt, ...updates } : opt
    );
    onUpdate(question.id, { options: newOptions });
  };

  const handleOptionDelete = (optionId: string) => {
    const newOptions = (question.options || []).filter(opt => opt.id !== optionId);
    onUpdate(question.id, { options: newOptions });
  };

  const needsOptions = ['multi_choice', 'checklist'].includes(question.type);

  return (
    <div className="bg-secondary/50 border border-border rounded-xl p-4 group">
      <div className="flex items-start gap-3 mb-4">
        <div className="p-1.5 bg-input rounded cursor-grab hover:bg-muted">
          <GripVertical className="w-4 h-4 text-muted-foreground" />
        </div>

        <div className="flex-1 space-y-3">
          <input
            type="text"
            value={question.text}
            onChange={(e) => onUpdate(question.id, { text: e.target.value })}
            placeholder="Enter question text..."
            className="w-full px-3 py-2 bg-input border border-input rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-ring text-sm"
          />

          <input
            type="text"
            value={question.description || ''}
            onChange={(e) => onUpdate(question.id, { description: e.target.value })}
            placeholder="Optional description or guidance..."
            className="w-full px-3 py-2 bg-muted/50 border border-input/50 rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-ring text-xs"
          />

          <div className="flex flex-wrap items-center gap-3">
            <QuestionTypeSelector
              selectedType={question.type}
              onSelect={(type) => onUpdate(question.id, { type })}
            />

            <label htmlFor={`required-${question.id}`} className="flex items-center gap-2 text-sm text-foreground cursor-pointer">
              <input id={`required-${question.id}`}
                type="checkbox"
                checked={question.required}
                onChange={(e) => onUpdate(question.id, { required: e.target.checked })}
                className="w-4 h-4 rounded border-input bg-input text-primary focus:ring-ring"
              />
              Required
            </label>

            <label htmlFor={`evidence-${question.id}`} className="flex items-center gap-2 text-sm text-foreground cursor-pointer">
              <input id={`evidence-${question.id}`}
                type="checkbox"
                checked={question.evidenceRequired}
                onChange={(e) => onUpdate(question.id, { evidenceRequired: e.target.checked })}
                className="w-4 h-4 rounded border-input bg-input text-primary focus:ring-ring"
              />
              <Camera className="w-4 h-4" />
              Evidence
            </label>

            <label htmlFor={`auto-action-${question.id}`} className="flex items-center gap-2 text-sm text-foreground cursor-pointer">
              <input id={`auto-action-${question.id}`}
                type="checkbox"
                checked={question.failureTriggersAction}
                onChange={(e) => onUpdate(question.id, { failureTriggersAction: e.target.checked })}
                className="w-4 h-4 rounded border-input bg-input text-destructive focus:ring-destructive"
              />
              <AlertTriangle className="w-4 h-4 text-destructive" />
              Auto-Action
            </label>

            <div className="flex items-center gap-2">
              <span className="text-xs text-muted-foreground">Weight:</span>
              <input id={`weight-${question.id}`}
                type="number"
                value={question.weight}
                onChange={(e) => onUpdate(question.id, { weight: parseFloat(e.target.value) || 1 })}
                min="0"
                max="10"
                step="0.5"
                className="w-16 px-2 py-1 bg-input border border-input rounded text-sm text-foreground text-center"
              />
            </div>
          </div>

          {needsOptions && (
            <div className="space-y-2 mt-3 pl-4 border-l-2 border-primary/30">
              <p className="text-xs text-muted-foreground font-medium">Options:</p>
              {(question.options || []).map((option, idx) => (
                <div key={option.id} className="flex items-center gap-2">
                  <span className="text-xs text-muted-foreground w-4">{idx + 1}.</span>
                  <input
                    type="text"
                    value={option.label}
                    onChange={(e) => handleOptionUpdate(option.id, { label: e.target.value, value: e.target.value })}
                    placeholder="Option label..."
                    className="flex-1 px-2 py-1 bg-input border border-input rounded text-sm text-foreground"
                  />
                  <input
                    type="number"
                    value={option.score || 0}
                    onChange={(e) => handleOptionUpdate(option.id, { score: parseInt(e.target.value) || 0 })}
                    placeholder="Score"
                    className="w-16 px-2 py-1 bg-input border border-input rounded text-sm text-foreground text-center"
                  />
                  <button
                    type="button"
                    onClick={() => handleOptionDelete(option.id)}
                    className="p-1 text-muted-foreground hover:text-destructive"
                  >
                    <XCircle className="w-4 h-4" />
                  </button>
                </div>
              ))}
              <button
                type="button"
                onClick={handleOptionAdd}
                className="flex items-center gap-1 text-xs text-primary hover:text-primary"
              >
                <Plus className="w-3 h-3" /> Add Option
              </button>
            </div>
          )}

          <button
            type="button"
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
          >
            <Settings className="w-3 h-3" />
            Advanced Settings
            <ChevronRight className={`w-3 h-3 transition-transform ${showAdvanced ? 'rotate-90' : ''}`} />
          </button>

          {showAdvanced && (
            <div className="grid grid-cols-2 gap-3 p-3 bg-muted rounded-lg">
              <div>
                <label htmlFor={`iso-clause-${question.id}`} className="block text-xs text-muted-foreground mb-1">ISO Clause</label>
                <input id={`iso-clause-${question.id}`}
                  type="text"
                  value={question.isoClause || ''}
                  onChange={(e) => onUpdate(question.id, { isoClause: e.target.value })}
                  placeholder="e.g., 7.1.2"
                  className="w-full px-2 py-1 bg-input border border-input rounded text-sm text-foreground"
                />
              </div>
              <div>
                <label htmlFor={`risk-level-${question.id}`} className="block text-xs text-muted-foreground mb-1">Risk Level</label>
                <select id={`risk-level-${question.id}`}
                  value={question.riskLevel || ''}
                  onChange={(e) => onUpdate(question.id, { riskLevel: e.target.value as Question['riskLevel'] })}
                  className="w-full px-2 py-1 bg-input border border-input rounded text-sm text-foreground"
                >
                  <option value="">None</option>
                  <option value="low">Low</option>
                  <option value="medium">Medium</option>
                  <option value="high">High</option>
                  <option value="critical">Critical</option>
                </select>
              </div>
              <div className="col-span-2">
                <label htmlFor={`guidance-${question.id}`} className="block text-xs text-muted-foreground mb-1">Auditor Guidance</label>
                <textarea id={`guidance-${question.id}`}
                  value={question.guidance || ''}
                  onChange={(e) => onUpdate(question.id, { guidance: e.target.value })}
                  placeholder="Tips for auditors on how to assess this item..."
                  rows={2}
                  className="w-full px-2 py-1 bg-input border border-input rounded text-sm text-foreground resize-none"
                />
              </div>
            </div>
          )}
        </div>

        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          <button
            type="button"
            onClick={() => onDuplicate(question.id)}
            className="p-1.5 text-muted-foreground hover:text-primary rounded"
            title="Duplicate"
          >
            <Copy className="w-4 h-4" />
          </button>
          <button
            type="button"
            onClick={() => onDelete(question.id)}
            className="p-1.5 text-muted-foreground hover:text-destructive rounded"
            title="Delete"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
