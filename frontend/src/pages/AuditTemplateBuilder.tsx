import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  ArrowLeft,
  Save,
  Plus,
  Trash2,
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
  Shield,
  Leaf,
  HardHat,
  Zap,
  Star,
  Lock,
  Unlock,
  History,
  Download,
  Upload,
  Layers,
  Award,
  FileText,
  Sparkles,
} from 'lucide-react';
import AITemplateGenerator from '../components/AITemplateGenerator';

// ============================================================================
// TYPES
// ============================================================================

type QuestionType = 
  | 'yes_no' 
  | 'yes_no_na' 
  | 'scale_1_5' 
  | 'scale_1_10' 
  | 'text_short' 
  | 'text_long' 
  | 'numeric' 
  | 'date' 
  | 'photo' 
  | 'signature' 
  | 'multi_choice' 
  | 'checklist'
  | 'pass_fail';

type ScoringMethod = 'weighted' | 'equal' | 'pass_fail' | 'points';

interface QuestionOption {
  id: string;
  label: string;
  value: string;
  score?: number;
  isCorrect?: boolean;
}

interface ConditionalLogic {
  enabled: boolean;
  showWhen: 'equals' | 'not_equals' | 'contains' | 'greater_than' | 'less_than';
  dependsOnQuestionId: string;
  value: string;
}

interface Question {
  id: string;
  text: string;
  description?: string;
  type: QuestionType;
  required: boolean;
  weight: number;
  options?: QuestionOption[];
  conditionalLogic?: ConditionalLogic;
  evidenceRequired: boolean;
  evidenceType?: 'photo' | 'document' | 'signature' | 'any';
  isoClause?: string;
  riskLevel?: 'critical' | 'high' | 'medium' | 'low';
  guidance?: string;
  failureTriggersAction: boolean;
  tags?: string[];
}

interface Section {
  id: string;
  title: string;
  description?: string;
  icon?: string;
  color?: string;
  questions: Question[];
  isExpanded: boolean;
  weight: number;
  order: number;
}

interface AuditTemplate {
  id: string;
  name: string;
  description: string;
  version: string;
  status: 'draft' | 'published' | 'archived';
  category: string;
  subcategory?: string;
  isoStandards: string[];
  sections: Section[];
  scoringMethod: ScoringMethod;
  passThreshold: number;
  createdAt: string;
  updatedAt: string;
  createdBy: string;
  tags: string[];
  estimatedDuration: number; // minutes
  isLocked: boolean;
}

// ============================================================================
// CONSTANTS
// ============================================================================

const QUESTION_TYPES: { type: QuestionType; label: string; icon: React.ElementType; description: string }[] = [
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

const CATEGORIES = [
  { id: 'quality', label: 'Quality Management', icon: Award, color: 'blue' },
  { id: 'safety', label: 'Health & Safety', icon: HardHat, color: 'orange' },
  { id: 'environment', label: 'Environmental', icon: Leaf, color: 'green' },
  { id: 'security', label: 'Security', icon: Shield, color: 'purple' },
  { id: 'compliance', label: 'Regulatory Compliance', icon: FileText, color: 'red' },
  { id: 'operational', label: 'Operational', icon: Zap, color: 'yellow' },
  { id: 'custom', label: 'Custom', icon: Layers, color: 'gray' },
];

const ISO_STANDARDS = [
  { id: 'iso9001', label: 'ISO 9001:2015', description: 'Quality Management' },
  { id: 'iso14001', label: 'ISO 14001:2015', description: 'Environmental Management' },
  { id: 'iso45001', label: 'ISO 45001:2018', description: 'Occupational Health & Safety' },
  { id: 'iso27001', label: 'ISO 27001:2022', description: 'Information Security' },
  { id: 'iso22000', label: 'ISO 22000:2018', description: 'Food Safety' },
  { id: 'iso50001', label: 'ISO 50001:2018', description: 'Energy Management' },
];

const SECTION_COLORS = [
  'from-blue-500 to-cyan-500',
  'from-purple-500 to-pink-500',
  'from-emerald-500 to-green-500',
  'from-orange-500 to-amber-500',
  'from-red-500 to-rose-500',
  'from-indigo-500 to-violet-500',
];

// ============================================================================
// HELPER FUNCTIONS
// ============================================================================

const generateId = () => Math.random().toString(36).substring(2, 11);

const createNewQuestion = (): Question => ({
  id: generateId(),
  text: '',
  type: 'yes_no',
  required: true,
  weight: 1,
  evidenceRequired: false,
  failureTriggersAction: false,
});

const createNewSection = (order: number): Section => ({
  id: generateId(),
  title: `Section ${order}`,
  questions: [],
  isExpanded: true,
  weight: 1,
  order,
  color: SECTION_COLORS[order % SECTION_COLORS.length],
});

// ============================================================================
// COMPONENTS
// ============================================================================

// Question Type Selector
const QuestionTypeSelector = ({ 
  selectedType, 
  onSelect 
}: { 
  selectedType: QuestionType; 
  onSelect: (type: QuestionType) => void;
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const selected = QUESTION_TYPES.find(t => t.type === selectedType);

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-sm text-white hover:bg-slate-600 transition-colors"
      >
        {selected && <selected.icon className="w-4 h-4 text-purple-400" />}
        <span>{selected?.label}</span>
        <ChevronDown className={`w-4 h-4 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {isOpen && (
        <div className="absolute z-20 mt-1 w-64 bg-slate-800 border border-slate-700 rounded-xl shadow-xl overflow-hidden">
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
                    ? 'bg-purple-500/20 text-purple-300'
                    : 'hover:bg-slate-700 text-white'
                }`}
              >
                <type.icon className="w-4 h-4 text-purple-400" />
                <div>
                  <p className="text-sm font-medium">{type.label}</p>
                  <p className="text-xs text-slate-400">{type.description}</p>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

// Question Editor
const QuestionEditor = ({
  question,
  onUpdate,
  onDelete,
  onDuplicate,
}: {
  question: Question;
  onUpdate: (questionId: string, updates: Partial<Question>) => void;
  onDelete: (questionId: string) => void;
  onDuplicate: (questionId: string) => void;
}) => {
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
    <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-4 group">
      {/* Header */}
      <div className="flex items-start gap-3 mb-4">
        <div className="p-1.5 bg-slate-700 rounded cursor-grab hover:bg-slate-600">
          <GripVertical className="w-4 h-4 text-slate-400" />
        </div>
        
        <div className="flex-1 space-y-3">
          {/* Question Text */}
          <input
            type="text"
            value={question.text}
            onChange={(e) => onUpdate(question.id, { text: e.target.value })}
            placeholder="Enter question text..."
            className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-400 focus:outline-none focus:border-purple-500 text-sm"
          />

          {/* Description */}
          <input
            type="text"
            value={question.description || ''}
            onChange={(e) => onUpdate(question.id, { description: e.target.value })}
            placeholder="Optional description or guidance..."
            className="w-full px-3 py-2 bg-slate-700/50 border border-slate-600/50 rounded-lg text-slate-300 placeholder-slate-500 focus:outline-none focus:border-purple-500 text-xs"
          />

          {/* Type and Settings Row */}
          <div className="flex flex-wrap items-center gap-3">
            <QuestionTypeSelector
              selectedType={question.type}
              onSelect={(type) => onUpdate(question.id, { type })}
            />

            <label className="flex items-center gap-2 text-sm text-slate-300 cursor-pointer">
              <input
                type="checkbox"
                checked={question.required}
                onChange={(e) => onUpdate(question.id, { required: e.target.checked })}
                className="w-4 h-4 rounded border-slate-600 bg-slate-700 text-purple-500 focus:ring-purple-500"
              />
              Required
            </label>

            <label className="flex items-center gap-2 text-sm text-slate-300 cursor-pointer">
              <input
                type="checkbox"
                checked={question.evidenceRequired}
                onChange={(e) => onUpdate(question.id, { evidenceRequired: e.target.checked })}
                className="w-4 h-4 rounded border-slate-600 bg-slate-700 text-purple-500 focus:ring-purple-500"
              />
              <Camera className="w-4 h-4" />
              Evidence
            </label>

            <label className="flex items-center gap-2 text-sm text-slate-300 cursor-pointer">
              <input
                type="checkbox"
                checked={question.failureTriggersAction}
                onChange={(e) => onUpdate(question.id, { failureTriggersAction: e.target.checked })}
                className="w-4 h-4 rounded border-slate-600 bg-slate-700 text-red-500 focus:ring-red-500"
              />
              <AlertTriangle className="w-4 h-4 text-red-400" />
              Auto-Action
            </label>

            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-400">Weight:</span>
              <input
                type="number"
                value={question.weight}
                onChange={(e) => onUpdate(question.id, { weight: parseFloat(e.target.value) || 1 })}
                min="0"
                max="10"
                step="0.5"
                className="w-16 px-2 py-1 bg-slate-700 border border-slate-600 rounded text-sm text-white text-center"
              />
            </div>
          </div>

          {/* Options for multi-choice/checklist */}
          {needsOptions && (
            <div className="space-y-2 mt-3 pl-4 border-l-2 border-purple-500/30">
              <p className="text-xs text-slate-400 font-medium">Options:</p>
              {(question.options || []).map((option, idx) => (
                <div key={option.id} className="flex items-center gap-2">
                  <span className="text-xs text-slate-500 w-4">{idx + 1}.</span>
                  <input
                    type="text"
                    value={option.label}
                    onChange={(e) => handleOptionUpdate(option.id, { label: e.target.value, value: e.target.value })}
                    placeholder="Option label..."
                    className="flex-1 px-2 py-1 bg-slate-700 border border-slate-600 rounded text-sm text-white"
                  />
                  <input
                    type="number"
                    value={option.score || 0}
                    onChange={(e) => handleOptionUpdate(option.id, { score: parseInt(e.target.value) || 0 })}
                    placeholder="Score"
                    className="w-16 px-2 py-1 bg-slate-700 border border-slate-600 rounded text-sm text-white text-center"
                  />
                  <button
                    type="button"
                    onClick={() => handleOptionDelete(option.id)}
                    className="p-1 text-slate-400 hover:text-red-400"
                  >
                    <XCircle className="w-4 h-4" />
                  </button>
                </div>
              ))}
              <button
                type="button"
                onClick={handleOptionAdd}
                className="flex items-center gap-1 text-xs text-purple-400 hover:text-purple-300"
              >
                <Plus className="w-3 h-3" /> Add Option
              </button>
            </div>
          )}

          {/* Advanced Settings */}
          <button
            type="button"
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="flex items-center gap-1 text-xs text-slate-400 hover:text-slate-300"
          >
            <Settings className="w-3 h-3" />
            Advanced Settings
            <ChevronRight className={`w-3 h-3 transition-transform ${showAdvanced ? 'rotate-90' : ''}`} />
          </button>

          {showAdvanced && (
            <div className="grid grid-cols-2 gap-3 p-3 bg-slate-700/30 rounded-lg">
              <div>
                <label className="block text-xs text-slate-400 mb-1">ISO Clause</label>
                <input
                  type="text"
                  value={question.isoClause || ''}
                  onChange={(e) => onUpdate(question.id, { isoClause: e.target.value })}
                  placeholder="e.g., 7.1.2"
                  className="w-full px-2 py-1 bg-slate-700 border border-slate-600 rounded text-sm text-white"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-1">Risk Level</label>
                <select
                  value={question.riskLevel || ''}
                  onChange={(e) => onUpdate(question.id, { riskLevel: e.target.value as Question['riskLevel'] })}
                  className="w-full px-2 py-1 bg-slate-700 border border-slate-600 rounded text-sm text-white"
                >
                  <option value="">None</option>
                  <option value="low">Low</option>
                  <option value="medium">Medium</option>
                  <option value="high">High</option>
                  <option value="critical">Critical</option>
                </select>
              </div>
              <div className="col-span-2">
                <label className="block text-xs text-slate-400 mb-1">Auditor Guidance</label>
                <textarea
                  value={question.guidance || ''}
                  onChange={(e) => onUpdate(question.id, { guidance: e.target.value })}
                  placeholder="Tips for auditors on how to assess this item..."
                  rows={2}
                  className="w-full px-2 py-1 bg-slate-700 border border-slate-600 rounded text-sm text-white resize-none"
                />
              </div>
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          <button
            type="button"
            onClick={() => onDuplicate(question.id)}
            className="p-1.5 text-slate-400 hover:text-purple-400 rounded"
            title="Duplicate"
          >
            <Copy className="w-4 h-4" />
          </button>
          <button
            type="button"
            onClick={() => onDelete(question.id)}
            className="p-1.5 text-slate-400 hover:text-red-400 rounded"
            title="Delete"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
};

// Section Editor
const SectionEditor = ({
  section,
  onUpdate,
  onDelete,
  onAddQuestion,
  onUpdateQuestion,
  onDeleteQuestion,
  onDuplicateQuestion,
}: {
  section: Section;
  onUpdate: (updates: Partial<Section>) => void;
  onDelete: () => void;
  onAddQuestion: () => void;
  onUpdateQuestion: (questionId: string, updates: Partial<Question>) => void;
  onDeleteQuestion: (questionId: string) => void;
  onDuplicateQuestion: (questionId: string) => void;
}) => {
  return (
    <div className="bg-slate-900/50 border border-slate-800 rounded-2xl overflow-hidden">
      {/* Section Header */}
      <div 
        className={`bg-gradient-to-r ${section.color || 'from-purple-500 to-pink-500'} p-0.5`}
      >
        <div className="bg-slate-900 p-4">
          <div className="flex items-center gap-3">
            <div className="p-1.5 bg-slate-800 rounded cursor-grab hover:bg-slate-700">
              <GripVertical className="w-5 h-5 text-slate-400" />
            </div>
            
            <button
              type="button"
              onClick={() => onUpdate({ isExpanded: !section.isExpanded })}
              className="p-1"
            >
              {section.isExpanded ? (
                <ChevronDown className="w-5 h-5 text-white" />
              ) : (
                <ChevronRight className="w-5 h-5 text-white" />
              )}
            </button>

            <div className="flex-1">
              <input
                type="text"
                value={section.title}
                onChange={(e) => onUpdate({ title: e.target.value })}
                placeholder="Section title..."
                className="w-full bg-transparent text-lg font-semibold text-white placeholder-slate-400 focus:outline-none"
              />
              <input
                type="text"
                value={section.description || ''}
                onChange={(e) => onUpdate({ description: e.target.value })}
                placeholder="Section description..."
                className="w-full bg-transparent text-sm text-slate-400 placeholder-slate-500 focus:outline-none mt-1"
              />
            </div>

            <div className="flex items-center gap-2">
              <span className="px-2 py-1 bg-slate-800 rounded-lg text-xs text-slate-300">
                {section.questions.length} questions
              </span>
              <div className="flex items-center gap-1">
                <span className="text-xs text-slate-400">Weight:</span>
                <input
                  type="number"
                  value={section.weight}
                  onChange={(e) => onUpdate({ weight: parseFloat(e.target.value) || 1 })}
                  min="0"
                  max="10"
                  step="0.5"
                  className="w-14 px-2 py-1 bg-slate-800 border border-slate-700 rounded text-sm text-white text-center"
                />
              </div>
              <button
                type="button"
                onClick={onDelete}
                className="p-1.5 text-slate-400 hover:text-red-400 rounded"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Section Content */}
      {section.isExpanded && (
        <div className="p-4 space-y-3">
          {section.questions.length === 0 ? (
            <div className="text-center py-8">
              <ListChecks className="w-12 h-12 mx-auto text-slate-600 mb-3" />
              <p className="text-slate-400 mb-4">No questions in this section</p>
              <button
                type="button"
                onClick={onAddQuestion}
                className="inline-flex items-center gap-2 px-4 py-2 bg-purple-500/20 text-purple-400 rounded-lg hover:bg-purple-500/30 transition-colors"
              >
                <Plus className="w-4 h-4" />
                Add First Question
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
                className="w-full py-3 border-2 border-dashed border-slate-700 rounded-xl text-slate-400 hover:border-purple-500 hover:text-purple-400 transition-colors flex items-center justify-center gap-2"
              >
                <Plus className="w-4 h-4" />
                Add Question
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
};

// ============================================================================
// MAIN COMPONENT
// ============================================================================

export default function AuditTemplateBuilder() {
  const navigate = useNavigate();
  const { templateId } = useParams();

  const [template, setTemplate] = useState<AuditTemplate>({
    id: templateId || generateId(),
    name: '',
    description: '',
    version: '1.0.0',
    status: 'draft',
    category: 'quality',
    isoStandards: [],
    sections: [createNewSection(1)],
    scoringMethod: 'weighted',
    passThreshold: 80,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    createdBy: 'Current User',
    tags: [],
    estimatedDuration: 60,
    isLocked: false,
  });

  const [activeTab, setActiveTab] = useState<'builder' | 'settings' | 'preview'>('builder');
  const [isSaving, setIsSaving] = useState(false);
  const [showAIAssist, setShowAIAssist] = useState(false);

  // Get all questions across all sections
  const allQuestions = template.sections.flatMap(s => s.questions);

  // Section handlers
  const handleAddSection = () => {
    const newSection = createNewSection(template.sections.length + 1);
    setTemplate(prev => ({
      ...prev,
      sections: [...prev.sections, newSection],
    }));
  };

  const handleUpdateSection = (sectionId: string, updates: Partial<Section>) => {
    setTemplate(prev => ({
      ...prev,
      sections: prev.sections.map(s =>
        s.id === sectionId ? { ...s, ...updates } : s
      ),
    }));
  };

  const handleDeleteSection = (sectionId: string) => {
    setTemplate(prev => ({
      ...prev,
      sections: prev.sections.filter(s => s.id !== sectionId),
    }));
  };

  // Question handlers
  const handleAddQuestion = (sectionId: string) => {
    const newQuestion = createNewQuestion();
    setTemplate(prev => ({
      ...prev,
      sections: prev.sections.map(s =>
        s.id === sectionId
          ? { ...s, questions: [...s.questions, newQuestion] }
          : s
      ),
    }));
  };

  const handleUpdateQuestion = (sectionId: string, questionId: string, updates: Partial<Question>) => {
    setTemplate(prev => ({
      ...prev,
      sections: prev.sections.map(s =>
        s.id === sectionId
          ? {
              ...s,
              questions: s.questions.map(q =>
                q.id === questionId ? { ...q, ...updates } : q
              ),
            }
          : s
      ),
    }));
  };

  const handleDeleteQuestion = (sectionId: string, questionId: string) => {
    setTemplate(prev => ({
      ...prev,
      sections: prev.sections.map(s =>
        s.id === sectionId
          ? { ...s, questions: s.questions.filter(q => q.id !== questionId) }
          : s
      ),
    }));
  };

  const handleDuplicateQuestion = (sectionId: string, questionId: string) => {
    setTemplate(prev => ({
      ...prev,
      sections: prev.sections.map(s => {
        if (s.id !== sectionId) return s;
        const questionIndex = s.questions.findIndex(q => q.id === questionId);
        if (questionIndex === -1) return s;
        const originalQuestion = s.questions[questionIndex];
        const duplicatedQuestion = {
          ...originalQuestion,
          id: generateId(),
          text: `${originalQuestion.text} (Copy)`,
        };
        const newQuestions = [...s.questions];
        newQuestions.splice(questionIndex + 1, 0, duplicatedQuestion);
        return { ...s, questions: newQuestions };
      }),
    }));
  };

  // Save handler
  const handleSave = async () => {
    setIsSaving(true);
    try {
      // Simulate API call
      await new Promise(resolve => setTimeout(resolve, 1000));
      console.log('Saving template:', template);
      // In production, call API here
    } catch (error) {
      console.error('Save failed:', error);
    } finally {
      setIsSaving(false);
    }
  };

  // Calculate stats
  const totalQuestions = allQuestions.length;
  const totalWeight = allQuestions.reduce((sum, q) => sum + q.weight, 0);
  const requiredQuestions = allQuestions.filter(q => q.required).length;
  const evidenceQuestions = allQuestions.filter(q => q.evidenceRequired).length;

  return (
    <div className="min-h-screen bg-slate-950">
      {/* Header */}
      <header className="sticky top-0 z-40 bg-slate-900/80 backdrop-blur-xl border-b border-slate-800">
        <div className="max-w-7xl mx-auto px-4 py-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <button
                onClick={() => navigate('/audit-templates')}
                className="p-2 hover:bg-slate-800 rounded-lg transition-colors"
              >
                <ArrowLeft className="w-5 h-5 text-slate-400" />
              </button>
              <div>
                <input
                  type="text"
                  value={template.name}
                  onChange={(e) => setTemplate(prev => ({ ...prev, name: e.target.value }))}
                  placeholder="Untitled Template"
                  className="bg-transparent text-xl font-bold text-white placeholder-slate-500 focus:outline-none"
                />
                <div className="flex items-center gap-2 mt-1">
                  <span className={`px-2 py-0.5 text-xs rounded ${
                    template.status === 'published' ? 'bg-green-500/20 text-green-400' :
                    template.status === 'archived' ? 'bg-gray-500/20 text-gray-400' :
                    'bg-amber-500/20 text-amber-400'
                  }`}>
                    {template.status}
                  </span>
                  <span className="text-xs text-slate-500">v{template.version}</span>
                  <span className="text-xs text-slate-500">•</span>
                  <span className="text-xs text-slate-500">{totalQuestions} questions</span>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-3">
              {/* Tabs */}
              <div className="flex bg-slate-800 rounded-lg p-1">
                {(['builder', 'settings', 'preview'] as const).map((tab) => (
                  <button
                    key={tab}
                    onClick={() => setActiveTab(tab)}
                    className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
                      activeTab === tab
                        ? 'bg-purple-500 text-white'
                        : 'text-slate-400 hover:text-white'
                    }`}
                  >
                    {tab.charAt(0).toUpperCase() + tab.slice(1)}
                  </button>
                ))}
              </div>

              <button
                onClick={() => setShowAIAssist(true)}
                className="flex items-center gap-2 px-3 py-2 bg-gradient-to-r from-purple-500/20 to-pink-500/20 border border-purple-500/30 rounded-lg text-purple-300 hover:bg-purple-500/30 transition-colors"
              >
                <Sparkles className="w-4 h-4" />
                AI Assist
              </button>

              <button
                onClick={handleSave}
                disabled={isSaving}
                className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-purple-500 to-pink-500 text-white font-medium rounded-lg hover:opacity-90 transition-opacity disabled:opacity-50"
              >
                {isSaving ? (
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                ) : (
                  <Save className="w-4 h-4" />
                )}
                Save
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 py-6">
        {activeTab === 'builder' && (
          <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
            {/* Left Sidebar - Stats & Quick Actions */}
            <div className="lg:col-span-1 space-y-4">
              {/* Stats Card */}
              <div className="bg-slate-900/50 border border-slate-800 rounded-2xl p-4">
                <h3 className="text-sm font-semibold text-white mb-4">Template Stats</h3>
                <div className="space-y-3">
                  <div className="flex justify-between">
                    <span className="text-sm text-slate-400">Sections</span>
                    <span className="text-sm font-medium text-white">{template.sections.length}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-sm text-slate-400">Questions</span>
                    <span className="text-sm font-medium text-white">{totalQuestions}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-sm text-slate-400">Required</span>
                    <span className="text-sm font-medium text-white">{requiredQuestions}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-sm text-slate-400">With Evidence</span>
                    <span className="text-sm font-medium text-white">{evidenceQuestions}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-sm text-slate-400">Total Weight</span>
                    <span className="text-sm font-medium text-white">{totalWeight}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-sm text-slate-400">Pass Threshold</span>
                    <span className="text-sm font-medium text-green-400">{template.passThreshold}%</span>
                  </div>
                </div>
              </div>

              {/* Quick Actions */}
              <div className="bg-slate-900/50 border border-slate-800 rounded-2xl p-4">
                <h3 className="text-sm font-semibold text-white mb-4">Quick Actions</h3>
                <div className="space-y-2">
                  <button className="w-full flex items-center gap-2 px-3 py-2 bg-slate-800 hover:bg-slate-700 rounded-lg text-sm text-slate-300 transition-colors">
                    <Upload className="w-4 h-4" />
                    Import from Excel
                  </button>
                  <button className="w-full flex items-center gap-2 px-3 py-2 bg-slate-800 hover:bg-slate-700 rounded-lg text-sm text-slate-300 transition-colors">
                    <Download className="w-4 h-4" />
                    Export Template
                  </button>
                  <button className="w-full flex items-center gap-2 px-3 py-2 bg-slate-800 hover:bg-slate-700 rounded-lg text-sm text-slate-300 transition-colors">
                    <Copy className="w-4 h-4" />
                    Duplicate Template
                  </button>
                  <button className="w-full flex items-center gap-2 px-3 py-2 bg-slate-800 hover:bg-slate-700 rounded-lg text-sm text-slate-300 transition-colors">
                    <History className="w-4 h-4" />
                    Version History
                  </button>
                </div>
              </div>

              {/* ISO Standards */}
              <div className="bg-slate-900/50 border border-slate-800 rounded-2xl p-4">
                <h3 className="text-sm font-semibold text-white mb-4">ISO Standards</h3>
                <div className="space-y-2">
                  {ISO_STANDARDS.map((standard) => (
                    <label
                      key={standard.id}
                      className="flex items-center gap-2 cursor-pointer"
                    >
                      <input
                        type="checkbox"
                        checked={template.isoStandards.includes(standard.id)}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setTemplate(prev => ({
                              ...prev,
                              isoStandards: [...prev.isoStandards, standard.id],
                            }));
                          } else {
                            setTemplate(prev => ({
                              ...prev,
                              isoStandards: prev.isoStandards.filter(s => s !== standard.id),
                            }));
                          }
                        }}
                        className="w-4 h-4 rounded border-slate-600 bg-slate-700 text-purple-500 focus:ring-purple-500"
                      />
                      <div>
                        <p className="text-sm text-white">{standard.label}</p>
                        <p className="text-xs text-slate-500">{standard.description}</p>
                      </div>
                    </label>
                  ))}
                </div>
              </div>
            </div>

            {/* Main Builder Area */}
            <div className="lg:col-span-3 space-y-4">
              {/* Description */}
              <div className="bg-slate-900/50 border border-slate-800 rounded-2xl p-4">
                <label className="block text-sm font-medium text-slate-300 mb-2">
                  Template Description
                </label>
                <textarea
                  value={template.description}
                  onChange={(e) => setTemplate(prev => ({ ...prev, description: e.target.value }))}
                  placeholder="Describe the purpose and scope of this audit template..."
                  rows={2}
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-purple-500 resize-none"
                />
              </div>

              {/* Sections */}
              <div className="space-y-4">
                {template.sections.map((section) => (
                  <SectionEditor
                    key={section.id}
                    section={section}
                    onUpdate={(updates) => handleUpdateSection(section.id, updates)}
                    onDelete={() => handleDeleteSection(section.id)}
                    onAddQuestion={() => handleAddQuestion(section.id)}
                    onUpdateQuestion={(qId, updates) => handleUpdateQuestion(section.id, qId, updates)}
                    onDeleteQuestion={(qId) => handleDeleteQuestion(section.id, qId)}
                    onDuplicateQuestion={(qId) => handleDuplicateQuestion(section.id, qId)}
                  />
                ))}

                {/* Add Section Button */}
                <button
                  type="button"
                  onClick={handleAddSection}
                  className="w-full py-4 border-2 border-dashed border-slate-700 rounded-2xl text-slate-400 hover:border-purple-500 hover:text-purple-400 transition-colors flex items-center justify-center gap-2"
                >
                  <Plus className="w-5 h-5" />
                  Add Section
                </button>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'settings' && (
          <div className="max-w-2xl mx-auto space-y-6">
            <div className="bg-slate-900/50 border border-slate-800 rounded-2xl p-6">
              <h2 className="text-lg font-semibold text-white mb-6">Template Settings</h2>
              
              <div className="space-y-6">
                {/* Category */}
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-2">Category</label>
                  <div className="grid grid-cols-2 gap-2">
                    {CATEGORIES.map((cat) => (
                      <button
                        key={cat.id}
                        type="button"
                        onClick={() => setTemplate(prev => ({ ...prev, category: cat.id }))}
                        className={`flex items-center gap-3 p-3 rounded-xl border-2 transition-all ${
                          template.category === cat.id
                            ? 'border-purple-500 bg-purple-500/10'
                            : 'border-slate-700 hover:border-slate-600'
                        }`}
                      >
                        <cat.icon className={`w-5 h-5 ${
                          template.category === cat.id ? 'text-purple-400' : 'text-slate-400'
                        }`} />
                        <span className="text-sm text-white">{cat.label}</span>
                      </button>
                    ))}
                  </div>
                </div>

                {/* Scoring Method */}
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-2">Scoring Method</label>
                  <div className="grid grid-cols-2 gap-2">
                    {[
                      { id: 'weighted', label: 'Weighted', description: 'Questions have different weights' },
                      { id: 'equal', label: 'Equal Weight', description: 'All questions count equally' },
                      { id: 'pass_fail', label: 'Pass/Fail', description: 'Binary pass or fail result' },
                      { id: 'points', label: 'Points Based', description: 'Accumulate points' },
                    ].map((method) => (
                      <button
                        key={method.id}
                        type="button"
                        onClick={() => setTemplate(prev => ({ ...prev, scoringMethod: method.id as ScoringMethod }))}
                        className={`p-3 rounded-xl border-2 text-left transition-all ${
                          template.scoringMethod === method.id
                            ? 'border-purple-500 bg-purple-500/10'
                            : 'border-slate-700 hover:border-slate-600'
                        }`}
                      >
                        <p className="text-sm font-medium text-white">{method.label}</p>
                        <p className="text-xs text-slate-400 mt-1">{method.description}</p>
                      </button>
                    ))}
                  </div>
                </div>

                {/* Pass Threshold */}
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-2">
                    Pass Threshold: {template.passThreshold}%
                  </label>
                  <input
                    type="range"
                    min="0"
                    max="100"
                    value={template.passThreshold}
                    onChange={(e) => setTemplate(prev => ({ ...prev, passThreshold: parseInt(e.target.value) }))}
                    className="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer"
                  />
                  <div className="flex justify-between text-xs text-slate-500 mt-1">
                    <span>0%</span>
                    <span>100%</span>
                  </div>
                </div>

                {/* Estimated Duration */}
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-2">
                    Estimated Duration (minutes)
                  </label>
                  <input
                    type="number"
                    value={template.estimatedDuration}
                    onChange={(e) => setTemplate(prev => ({ ...prev, estimatedDuration: parseInt(e.target.value) || 0 }))}
                    min="0"
                    className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:border-purple-500"
                  />
                </div>

                {/* Version */}
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-2">Version</label>
                  <input
                    type="text"
                    value={template.version}
                    onChange={(e) => setTemplate(prev => ({ ...prev, version: e.target.value }))}
                    placeholder="1.0.0"
                    className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:border-purple-500"
                  />
                </div>

                {/* Lock Toggle */}
                <div className="flex items-center justify-between p-4 bg-slate-800 rounded-xl">
                  <div className="flex items-center gap-3">
                    {template.isLocked ? (
                      <Lock className="w-5 h-5 text-amber-400" />
                    ) : (
                      <Unlock className="w-5 h-5 text-slate-400" />
                    )}
                    <div>
                      <p className="text-sm font-medium text-white">Lock Template</p>
                      <p className="text-xs text-slate-400">Prevent edits after publishing</p>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => setTemplate(prev => ({ ...prev, isLocked: !prev.isLocked }))}
                    className={`relative w-12 h-6 rounded-full transition-colors ${
                      template.isLocked ? 'bg-amber-500' : 'bg-slate-600'
                    }`}
                  >
                    <span
                      className={`absolute top-1 w-4 h-4 bg-white rounded-full transition-transform ${
                        template.isLocked ? 'translate-x-7' : 'translate-x-1'
                      }`}
                    />
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'preview' && (
          <div className="max-w-2xl mx-auto">
            <div className="bg-slate-900/50 border border-slate-800 rounded-2xl p-6">
              <div className="text-center mb-8">
                <h2 className="text-2xl font-bold text-white mb-2">{template.name || 'Untitled Template'}</h2>
                <p className="text-slate-400">{template.description}</p>
                <div className="flex items-center justify-center gap-4 mt-4">
                  <span className="px-3 py-1 bg-purple-500/20 text-purple-400 rounded-lg text-sm">
                    {totalQuestions} Questions
                  </span>
                  <span className="px-3 py-1 bg-slate-700 text-slate-300 rounded-lg text-sm">
                    ~{template.estimatedDuration} min
                  </span>
                  <span className="px-3 py-1 bg-green-500/20 text-green-400 rounded-lg text-sm">
                    Pass: {template.passThreshold}%
                  </span>
                </div>
              </div>

              {template.sections.map((section, sectionIndex) => (
                <div key={section.id} className="mb-6">
                  <div className={`bg-gradient-to-r ${section.color} p-0.5 rounded-xl`}>
                    <div className="bg-slate-900 p-4 rounded-xl">
                      <h3 className="text-lg font-semibold text-white">
                        {sectionIndex + 1}. {section.title}
                      </h3>
                      {section.description && (
                        <p className="text-sm text-slate-400 mt-1">{section.description}</p>
                      )}
                    </div>
                  </div>
                  <div className="mt-3 space-y-3 pl-4">
                    {section.questions.map((question, qIndex) => (
                      <div key={question.id} className="flex items-start gap-3 p-3 bg-slate-800/50 rounded-lg">
                        <span className="text-sm text-slate-500">{sectionIndex + 1}.{qIndex + 1}</span>
                        <div className="flex-1">
                          <p className="text-sm text-white">
                            {question.text || 'Untitled question'}
                            {question.required && <span className="text-red-400 ml-1">*</span>}
                          </p>
                          <div className="flex items-center gap-2 mt-2">
                            <span className="text-xs text-slate-500 bg-slate-700 px-2 py-0.5 rounded">
                              {QUESTION_TYPES.find(t => t.type === question.type)?.label}
                            </span>
                            {question.evidenceRequired && (
                              <span className="text-xs text-cyan-400 bg-cyan-500/10 px-2 py-0.5 rounded flex items-center gap-1">
                                <Camera className="w-3 h-3" /> Evidence
                              </span>
                            )}
                            {question.riskLevel && (
                              <span className={`text-xs px-2 py-0.5 rounded ${
                                question.riskLevel === 'critical' ? 'text-red-400 bg-red-500/10' :
                                question.riskLevel === 'high' ? 'text-orange-400 bg-orange-500/10' :
                                question.riskLevel === 'medium' ? 'text-amber-400 bg-amber-500/10' :
                                'text-green-400 bg-green-500/10'
                              }`}>
                                {question.riskLevel} risk
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </main>

      {/* AI Template Generator */}
      {showAIAssist && (
        <AITemplateGenerator
          onClose={() => setShowAIAssist(false)}
          onApply={(generatedSections) => {
            // Convert generated sections to template format
            const newSections: Section[] = generatedSections.map((gs, idx) => ({
              id: gs.id,
              title: gs.title,
              description: gs.description,
              questions: gs.questions.map((q) => ({
                id: q.id,
                text: q.text,
                type: q.type as QuestionType,
                required: q.required,
                weight: q.weight,
                riskLevel: (q.riskLevel as 'critical' | 'high' | 'medium' | 'low' | undefined),
                evidenceRequired: q.evidenceRequired,
                isoClause: q.isoClause,
                guidance: q.guidance,
                failureTriggersAction: false,
              })),
              isExpanded: true,
              weight: 1,
              order: template.sections.length + idx,
              color: SECTION_COLORS[(template.sections.length + idx) % SECTION_COLORS.length],
            }));
            
            setTemplate(prev => ({
              ...prev,
              sections: [...prev.sections, ...newSections],
            }));
            setShowAIAssist(false);
          }}
        />
      )}
    </div>
  );
}
