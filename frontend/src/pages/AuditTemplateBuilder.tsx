import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  ArrowLeft, Save, Plus, Trash2, GripVertical, Settings,
  ChevronDown, ChevronRight, CheckCircle, ToggleLeft,
  Type, Hash, Calendar, Camera, FileSignature, ListChecks, Scale,
  MessageSquare, AlertTriangle, Shield, Leaf, HardHat, Zap, Star,
  History, Download, Upload, Layers, Award, FileText,
  Sparkles, Loader2, Eye,
} from 'lucide-react';
import { Button } from '../components/ui/Button';
import { ToastContainer, useToast } from '../components/ui/Toast';
import { Input } from '../components/ui/Input';
import { Textarea } from '../components/ui/Textarea';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
  DialogDescription, DialogFooter,
} from '../components/ui/Dialog';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../components/ui/Select';
import {
  auditsApi,
  AuditTemplateDetail, AuditSection as ApiSection,
  AuditQuestion as ApiQuestion, AuditTemplateUpdate,
} from '../api/client';
import AITemplateGenerator from '../components/AITemplateGenerator';
import { CardSkeleton } from '../components/ui/SkeletonLoader';

// ============================================================================
// CONSTANTS
// ============================================================================

type QuestionType =
  | 'yes_no' | 'pass_fail' | 'score' | 'rating'
  | 'text' | 'textarea' | 'number'
  | 'date' | 'datetime' | 'photo' | 'signature'
  | 'radio' | 'dropdown' | 'checkbox' | 'file';

const VALID_QUESTION_TYPES = new Set<string>([
  'yes_no', 'pass_fail', 'score', 'rating',
  'text', 'textarea', 'number',
  'date', 'datetime', 'photo', 'signature',
  'radio', 'dropdown', 'checkbox', 'file',
]);

const QUESTION_TYPES: { type: QuestionType; label: string; icon: React.ElementType; description: string }[] = [
  { type: 'yes_no', label: 'Yes / No', icon: ToggleLeft, description: 'Binary choice' },
  { type: 'pass_fail', label: 'Pass / Fail', icon: CheckCircle, description: 'Compliance check' },
  { type: 'score', label: 'Score (1–5)', icon: Star, description: 'Rating scale' },
  { type: 'rating', label: 'Score (1–10)', icon: Scale, description: 'Detailed rating' },
  { type: 'radio', label: 'Multiple Choice', icon: ListChecks, description: 'Select one option' },
  { type: 'checkbox', label: 'Checklist', icon: CheckCircle, description: 'Multiple selections' },
  { type: 'dropdown', label: 'Dropdown', icon: ChevronDown, description: 'Select from list' },
  { type: 'text', label: 'Short Text', icon: Type, description: 'Single line response' },
  { type: 'textarea', label: 'Long Text', icon: MessageSquare, description: 'Multi-line response' },
  { type: 'number', label: 'Numeric', icon: Hash, description: 'Number input' },
  { type: 'date', label: 'Date', icon: Calendar, description: 'Date picker' },
  { type: 'datetime', label: 'Date & Time', icon: Calendar, description: 'Date and time picker' },
  { type: 'photo', label: 'Photo', icon: Camera, description: 'Image capture' },
  { type: 'signature', label: 'Signature', icon: FileSignature, description: 'Digital signature' },
  { type: 'file', label: 'File Upload', icon: Upload, description: 'Document attachment' },
];

const CATEGORIES = [
  { id: 'quality', label: 'Quality Management', icon: Award },
  { id: 'safety', label: 'Health & Safety', icon: HardHat },
  { id: 'environment', label: 'Environmental', icon: Leaf },
  { id: 'security', label: 'Security', icon: Shield },
  { id: 'compliance', label: 'Regulatory Compliance', icon: FileText },
  { id: 'operational', label: 'Operational', icon: Zap },
  { id: 'custom', label: 'Custom', icon: Layers },
];

// ============================================================================
// QUESTION EDITOR
// ============================================================================

interface QuestionEditorProps {
  question: ApiQuestion;
  sectionId: number;
  templateId: number;
  onUpdated: () => void;
  onDeleted: () => void;
}

const OPTION_TYPES = new Set(['radio', 'dropdown', 'checkbox']);
const NUMERIC_TYPES = new Set(['number', 'score', 'rating']);
const SCORE_DEFAULTS: Record<string, { min: number; max: number }> = {
  score: { min: 1, max: 5 },
  rating: { min: 1, max: 10 },
};

interface OptionsEditorProps {
  questionId: number;
  options: { value: string; label: string; score?: number; is_correct?: boolean; triggers_finding?: boolean }[];
  onSaved: () => void;
}

function OptionsEditor({ questionId, options: initial, onSaved }: OptionsEditorProps) {
  const [opts, setOpts] = useState(initial.length > 0 ? initial : [{ value: 'option_1', label: 'Option 1', score: 0 }]);
  const [saving, setSaving] = useState(false);

  const addOption = () => {
    const idx = opts.length + 1;
    setOpts([...opts, { value: `option_${idx}`, label: `Option ${idx}`, score: 0 }]);
  };

  const removeOption = (index: number) => {
    if (opts.length <= 1) return;
    setOpts(opts.filter((_, i) => i !== index));
  };

  const updateOption = (index: number, field: string, value: string | number | boolean) => {
    const updated = [...opts];
    updated[index] = { ...updated[index], [field]: value };
    if (field === 'label') {
      updated[index].value = String(value).toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '') || `option_${index + 1}`;
    }
    setOpts(updated);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await auditsApi.updateQuestion(questionId, { options: opts });
      onSaved();
    } catch (err) {
      console.error('Failed to save options:', err);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card className="bg-surface border-primary/20">
      <CardContent className="p-4 space-y-3">
        <div className="flex items-center justify-between">
          <h4 className="text-sm font-semibold text-foreground">Answer Options</h4>
          <Button variant="outline" size="sm" onClick={addOption}>
            <Plus className="w-3 h-3" /> Add Option
          </Button>
        </div>

        <div className="space-y-2">
          {opts.map((opt, idx) => (
            <div key={idx} className="flex items-center gap-2">
              <span className="text-xs text-muted-foreground font-mono w-6 text-right">{idx + 1}.</span>
              <Input
                value={opt.label}
                onChange={(e) => updateOption(idx, 'label', e.target.value)}
                placeholder="Option label..."
                className="flex-1"
              />
              <Input
                type="number"
                value={opt.score ?? 0}
                onChange={(e) => updateOption(idx, 'score', parseFloat(e.target.value) || 0)}
                className="w-20 text-center"
                placeholder="Score"
                title="Score value"
              />
              <label className="flex items-center gap-1 text-xs text-muted-foreground cursor-pointer whitespace-nowrap" title="Triggers audit finding">
                <input
                  type="checkbox"
                  checked={opt.triggers_finding || false}
                  onChange={(e) => updateOption(idx, 'triggers_finding', e.target.checked)}
                  className="w-3 h-3"
                />
                Finding
              </label>
              <Button
                variant="ghost" size="icon-sm"
                onClick={() => removeOption(idx)}
                disabled={opts.length <= 1}
                aria-label="Remove option"
              >
                <Trash2 className="w-3 h-3" />
              </Button>
            </div>
          ))}
        </div>

        <Button size="sm" onClick={handleSave} disabled={saving} className="w-full">
          {saving ? <Loader2 className="w-3 h-3 animate-spin" /> : <Save className="w-3 h-3" />}
          Save Options
        </Button>
      </CardContent>
    </Card>
  );
}

interface NumericConfigProps {
  questionId: number;
  questionType: string;
  minValue?: number | null;
  maxValue?: number | null;
  maxScore?: number | null;
  onSaved: () => void;
}

function NumericConfig({ questionId, questionType, minValue, maxValue, maxScore, onSaved }: NumericConfigProps) {
  const defaults = SCORE_DEFAULTS[questionType];
  const [min, setMin] = useState(minValue ?? defaults?.min ?? 0);
  const [max, setMax] = useState(maxValue ?? defaults?.max ?? 100);
  const [score, setScore] = useState(maxScore ?? defaults?.max ?? 10);
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    setSaving(true);
    try {
      await auditsApi.updateQuestion(questionId, {
        min_value: min,
        max_value: max,
        max_score: score,
      });
      onSaved();
    } catch (err) {
      console.error('Failed to save numeric config:', err);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card className="bg-surface border-primary/20">
      <CardContent className="p-4 space-y-3">
        <h4 className="text-sm font-semibold text-foreground">
          {questionType === 'score' ? 'Score Range (1–5)' : questionType === 'rating' ? 'Rating Range (1–10)' : 'Numeric Constraints'}
        </h4>
        <div className="grid grid-cols-3 gap-3">
          <div>
            <label className="block text-xs text-muted-foreground mb-1">Min Value</label>
            <Input type="number" value={min} onChange={(e) => setMin(parseFloat(e.target.value) || 0)} />
          </div>
          <div>
            <label className="block text-xs text-muted-foreground mb-1">Max Value</label>
            <Input type="number" value={max} onChange={(e) => setMax(parseFloat(e.target.value) || 0)} />
          </div>
          <div>
            <label className="block text-xs text-muted-foreground mb-1">Max Score</label>
            <Input type="number" value={score} onChange={(e) => setScore(parseFloat(e.target.value) || 0)} />
          </div>
        </div>
        <Button size="sm" onClick={handleSave} disabled={saving} className="w-full">
          {saving ? <Loader2 className="w-3 h-3 animate-spin" /> : <Save className="w-3 h-3" />}
          Save Configuration
        </Button>
      </CardContent>
    </Card>
  );
}

const QuestionEditor = React.memo(function QuestionEditor({
  question, onUpdated, onDeleted,
}: QuestionEditorProps) {
  const [text, setText] = useState(question.question_text);
  const [description, setDescription] = useState(question.description || '');
  const [weight, setWeight] = useState(question.weight);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [saving, setSaving] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();

  const needsOptions = OPTION_TYPES.has(question.question_type);
  const needsNumericConfig = NUMERIC_TYPES.has(question.question_type);

  useEffect(() => {
    setText(question.question_text);
    setDescription(question.description || '');
    setWeight(question.weight);
  }, [question.question_text, question.description, question.weight]);

  const debouncedSave = useCallback((field: string, value: unknown) => {
    if (field === 'question_text' && (typeof value !== 'string' || value.trim() === '')) return;
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      try {
        await auditsApi.updateQuestion(question.id, { [field]: value });
        onUpdated();
      } catch (err) {
        console.error('Failed to save question:', err);
      }
    }, 600);
  }, [question.id, onUpdated]);

  useEffect(() => () => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
  }, []);

  const handleTypeChange = useCallback(async (newType: string) => {
    setSaving(true);
    try {
      const update: Record<string, unknown> = { question_type: newType };
      const defaults = SCORE_DEFAULTS[newType];
      if (defaults) {
        update.min_value = defaults.min;
        update.max_value = defaults.max;
        update.max_score = defaults.max;
      }
      if (newType === 'yes_no' || newType === 'pass_fail') {
        update.max_score = 1;
        update.options = [
          { value: newType === 'yes_no' ? 'yes' : 'pass', label: newType === 'yes_no' ? 'Yes' : 'Pass', score: 1, triggers_finding: false },
          { value: newType === 'yes_no' ? 'no' : 'fail', label: newType === 'yes_no' ? 'No' : 'Fail', score: 0, triggers_finding: true },
        ];
      }
      await auditsApi.updateQuestion(question.id, update);
      onUpdated();
    } catch (err) {
      console.error('Failed to update question type:', err);
    } finally {
      setSaving(false);
    }
  }, [question.id, onUpdated]);

  const handleToggle = useCallback(async (field: string, value: boolean) => {
    try {
      await auditsApi.updateQuestion(question.id, { [field]: value });
      onUpdated();
    } catch (err) {
      console.error('Failed to toggle:', err);
    }
  }, [question.id, onUpdated]);

  const handleDelete = useCallback(async () => {
    try {
      await auditsApi.deleteQuestion(question.id);
      onDeleted();
      setShowDeleteConfirm(false);
    } catch (err) {
      console.error('Failed to delete question:', err);
    }
  }, [question.id, onDeleted]);

  return (
    <>
      <Card className="group">
        <CardContent className="p-4">
          <div className="flex items-start gap-3">
            <div
              className="p-2 rounded-lg bg-surface text-muted-foreground mt-1"
              aria-hidden="true"
            >
              <GripVertical className="w-4 h-4" />
            </div>

            <div className="flex-1 space-y-3">
              <div>
                <label htmlFor={`q-text-${question.id}`} className="sr-only">Question text</label>
                <Input
                  id={`q-text-${question.id}`}
                  value={text}
                  onChange={(e) => {
                    setText(e.target.value);
                    debouncedSave('question_text', e.target.value);
                  }}
                  placeholder="Enter question text..."
                  aria-required="true"
                />
              </div>

              <div>
                <label htmlFor={`q-desc-${question.id}`} className="sr-only">Question description</label>
                <Input
                  id={`q-desc-${question.id}`}
                  value={description}
                  onChange={(e) => {
                    setDescription(e.target.value);
                    debouncedSave('description', e.target.value);
                  }}
                  placeholder="Optional description or guidance..."
                  className="text-sm"
                />
              </div>

              <div className="flex flex-wrap items-center gap-3">
                <div>
                  <label htmlFor={`q-type-${question.id}`} className="sr-only">Question type</label>
                  <Select
                    value={question.question_type}
                    onValueChange={handleTypeChange}
                  >
                    <SelectTrigger className="w-[180px]" id={`q-type-${question.id}`}>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {QUESTION_TYPES.map((type) => (
                        <SelectItem key={type.type} value={type.type}>
                          <span className="flex items-center gap-2">
                            <type.icon className="w-4 h-4" />
                            {type.label}
                          </span>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <label className="flex items-center gap-2 text-sm text-foreground cursor-pointer min-h-[44px] px-2">
                  <input
                    type="checkbox"
                    checked={question.is_required}
                    onChange={(e) => handleToggle('is_required', e.target.checked)}
                    className="w-4 h-4 rounded border-input bg-background text-primary focus:ring-primary"
                  />
                  Required
                </label>

                <label className="flex items-center gap-2 text-sm text-foreground cursor-pointer min-h-[44px] px-2">
                  <input
                    type="checkbox"
                    checked={question.allow_na}
                    onChange={(e) => handleToggle('allow_na', e.target.checked)}
                    className="w-4 h-4 rounded border-input bg-background text-primary focus:ring-primary"
                  />
                  Allow N/A
                </label>

                <div className="flex items-center gap-2">
                  <label htmlFor={`q-weight-${question.id}`} className="text-sm text-muted-foreground">Weight:</label>
                  <Input
                    id={`q-weight-${question.id}`}
                    type="number"
                    value={weight}
                    onChange={(e) => { const v = parseFloat(e.target.value) || 1; setWeight(v); debouncedSave('weight', v); }}
                    min={0} max={10} step={0.5}
                    className="w-20 text-center"
                  />
                </div>
              </div>

              {needsOptions && (
                <OptionsEditor
                  questionId={question.id}
                  options={question.options || []}
                  onSaved={onUpdated}
                />
              )}

              {needsNumericConfig && (
                <NumericConfig
                  questionId={question.id}
                  questionType={question.question_type}
                  minValue={question.min_value}
                  maxValue={question.max_value}
                  maxScore={question.max_score}
                  onSaved={onUpdated}
                />
              )}

              <button
                type="button"
                onClick={() => setShowAdvanced(!showAdvanced)}
                className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors min-h-[44px]"
                aria-expanded={showAdvanced}
              >
                <Settings className="w-4 h-4" />
                Advanced Settings
                <ChevronRight className={`w-4 h-4 transition-transform ${showAdvanced ? 'rotate-90' : ''}`} />
              </button>

              {showAdvanced && (
                <Card className="bg-surface">
                  <CardContent className="p-4 grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label htmlFor={`q-risk-${question.id}`} className="block text-sm font-medium text-foreground mb-1">Risk Category</label>
                      <Select
                        value={question.risk_category || 'none'}
                        onValueChange={(v) => debouncedSave('risk_category', v === 'none' ? null : v)}
                      >
                        <SelectTrigger id={`q-risk-${question.id}`}>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="none">None</SelectItem>
                          <SelectItem value="low">Low</SelectItem>
                          <SelectItem value="medium">Medium</SelectItem>
                          <SelectItem value="high">High</SelectItem>
                          <SelectItem value="critical">Critical</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div>
                      <label htmlFor={`q-help-${question.id}`} className="block text-sm font-medium text-foreground mb-1">Help Text</label>
                      <Input
                        id={`q-help-${question.id}`}
                        value={question.help_text || ''}
                        onChange={(e) => debouncedSave('help_text', e.target.value)}
                        placeholder="Guidance for auditors..."
                      />
                    </div>
                    <div>
                      <label htmlFor={`q-maxscore-${question.id}`} className="block text-sm font-medium text-foreground mb-1">Max Score</label>
                      <Input
                        id={`q-maxscore-${question.id}`}
                        type="number"
                        value={question.max_score ?? ''}
                        onChange={(e) => debouncedSave('max_score', parseFloat(e.target.value) || null)}
                        placeholder="Maximum score"
                      />
                    </div>
                  </CardContent>
                </Card>
              )}
            </div>

            <div className="flex items-center gap-1">
              {saving && <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />}
              <Button
                variant="ghost" size="icon-sm"
                onClick={() => setShowDeleteConfirm(true)}
                aria-label="Delete question"
              >
                <Trash2 className="w-4 h-4" />
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      <Dialog open={showDeleteConfirm} onOpenChange={setShowDeleteConfirm}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Question</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete this question? This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowDeleteConfirm(false)}>Cancel</Button>
            <Button variant="destructive" onClick={handleDelete}>Delete</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
});

// ============================================================================
// SECTION EDITOR
// ============================================================================

interface SectionEditorProps {
  section: ApiSection;
  templateId: number;
  onUpdated: () => void;
  onDeleted: () => void;
}

const SectionEditor = React.memo(function SectionEditor({
  section, templateId, onUpdated, onDeleted,
}: SectionEditorProps) {
  const [isExpanded, setIsExpanded] = useState(true);
  const [title, setTitle] = useState(section.title);
  const [description, setDescription] = useState(section.description || '');
  const [sectionWeight, setSectionWeight] = useState(section.weight);
  const [addingQuestion, setAddingQuestion] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();

  useEffect(() => {
    setTitle(section.title);
    setDescription(section.description || '');
    setSectionWeight(section.weight);
  }, [section.title, section.description, section.weight]);

  const debouncedSave = useCallback((field: string, value: string | number) => {
    if (field === 'title' && (typeof value !== 'string' || value.trim() === '')) return;
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      try {
        await auditsApi.updateSection(section.id, { [field]: value });
        onUpdated();
      } catch (err) {
        console.error('Failed to save section:', err);
      }
    }, 600);
  }, [section.id, onUpdated]);

  useEffect(() => () => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
  }, []);

  const handleAddQuestion = useCallback(async () => {
    setAddingQuestion(true);
    try {
      await auditsApi.createQuestion(templateId, {
        section_id: section.id,
        question_text: 'New Question',
        question_type: 'yes_no',
        is_required: true,
        weight: 1,
        sort_order: (section.questions?.length || 0),
      });
      onUpdated();
    } catch (err) {
      console.error('Failed to add question:', err);
    } finally {
      setAddingQuestion(false);
    }
  }, [templateId, section.id, section.questions?.length, onUpdated]);

  const handleDelete = useCallback(async () => {
    try {
      await auditsApi.deleteSection(section.id);
      onDeleted();
      setShowDeleteConfirm(false);
    } catch (err) {
      console.error('Failed to delete section:', err);
    }
  }, [section.id, onDeleted]);

  const activeQuestions = useMemo(
    () => (section.questions || []).filter(q => q.is_active),
    [section.questions]
  );

  return (
    <>
      <Card>
        <CardHeader className="pb-0">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-surface text-muted-foreground" aria-hidden="true">
              <GripVertical className="w-5 h-5" />
            </div>

            <Button
              variant="ghost" size="icon-sm"
              onClick={() => setIsExpanded(!isExpanded)}
              aria-expanded={isExpanded}
              aria-label={isExpanded ? 'Collapse section' : 'Expand section'}
            >
              {isExpanded ? <ChevronDown className="w-5 h-5" /> : <ChevronRight className="w-5 h-5" />}
            </Button>

            <div className="flex-1 space-y-1">
              <label htmlFor={`sec-title-${section.id}`} className="sr-only">Section title</label>
              <Input
                id={`sec-title-${section.id}`}
                value={title}
                onChange={(e) => {
                  setTitle(e.target.value);
                  debouncedSave('title', e.target.value);
                }}
                placeholder="Section title..."
                className="text-lg font-semibold border-none bg-transparent px-0 focus-visible:ring-0 h-auto"
              />
              <label htmlFor={`sec-desc-${section.id}`} className="sr-only">Section description</label>
              <Input
                id={`sec-desc-${section.id}`}
                value={description}
                onChange={(e) => {
                  setDescription(e.target.value);
                  debouncedSave('description', e.target.value);
                }}
                placeholder="Section description..."
                className="text-sm border-none bg-transparent px-0 focus-visible:ring-0 h-auto text-muted-foreground"
              />
            </div>

            <Badge variant="secondary">{activeQuestions.length} questions</Badge>

            <div className="flex items-center gap-2">
              <label htmlFor={`sec-weight-${section.id}`} className="text-sm text-muted-foreground">Weight:</label>
              <Input
                id={`sec-weight-${section.id}`}
                type="number" value={sectionWeight}
                onChange={(e) => { const v = parseFloat(e.target.value) || 1; setSectionWeight(v); debouncedSave('weight', v); }}
                min={0} max={10} step={0.5}
                className="w-20 text-center"
              />
            </div>

            <Button
              variant="ghost" size="icon-sm"
              onClick={() => setShowDeleteConfirm(true)}
              aria-label="Delete section"
            >
              <Trash2 className="w-4 h-4" />
            </Button>
          </div>
        </CardHeader>

        {isExpanded && (
          <CardContent className="pt-4 space-y-3">
            {activeQuestions.length === 0 ? (
              <div className="text-center py-8 border-2 border-dashed border-border rounded-xl">
                <ListChecks className="w-10 h-10 mx-auto text-muted-foreground mb-3" />
                <p className="text-muted-foreground mb-4">No questions in this section</p>
                <Button onClick={handleAddQuestion} disabled={addingQuestion}>
                  {addingQuestion ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
                  Add First Question
                </Button>
              </div>
            ) : (
              <>
                {activeQuestions.map((question) => (
                  <QuestionEditor
                    key={question.id}
                    question={question}
                    sectionId={section.id}
                    templateId={templateId}
                    onUpdated={onUpdated}
                    onDeleted={onUpdated}
                  />
                ))}
                <Button
                  variant="outline" className="w-full"
                  onClick={handleAddQuestion}
                  disabled={addingQuestion}
                >
                  {addingQuestion ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
                  Add Question
                </Button>
              </>
            )}
          </CardContent>
        )}
      </Card>

      <Dialog open={showDeleteConfirm} onOpenChange={setShowDeleteConfirm}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Section</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete &quot;{section.title}&quot; and all {activeQuestions.length} questions in it? This cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowDeleteConfirm(false)}>Cancel</Button>
            <Button variant="destructive" onClick={handleDelete}>Delete Section</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
});

// ============================================================================
// TEMPLATE SETTINGS PANEL
// ============================================================================

interface SettingsPanelProps {
  template: AuditTemplateDetail;
  onSave: (data: AuditTemplateUpdate) => Promise<void>;
}

function SettingsPanel({ template, onSave }: SettingsPanelProps) {
  const [category, setCategory] = useState(template.category || '');
  const [scoringMethod, setScoringMethod] = useState(template.scoring_method || 'percentage');
  const [passingScore, setPassingScore] = useState(template.passing_score ?? 80);
  const [auditType, setAuditType] = useState(template.audit_type || 'inspection');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setCategory(template.category || '');
    setScoringMethod(template.scoring_method || 'percentage');
    setPassingScore(template.passing_score ?? 80);
    setAuditType(template.audit_type || 'inspection');
  }, [template.category, template.scoring_method, template.passing_score, template.audit_type]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await onSave({
        category,
        scoring_method: scoringMethod,
        passing_score: passingScore,
        audit_type: auditType,
      });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Template Settings</CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          <div>
            <label className="block text-sm font-medium text-foreground mb-2">Category</label>
            <div className="grid grid-cols-2 gap-2">
              {CATEGORIES.map((cat) => (
                <button
                  key={cat.id}
                  type="button"
                  onClick={() => setCategory(cat.id)}
                  className={`flex items-center gap-3 p-3 rounded-xl border-2 transition-all ${
                    category === cat.id
                      ? 'border-primary bg-primary/5'
                      : 'border-border hover:border-border-strong'
                  }`}
                  aria-pressed={category === cat.id}
                >
                  <cat.icon className={`w-5 h-5 ${category === cat.id ? 'text-primary' : 'text-muted-foreground'}`} />
                  <span className="text-sm text-foreground">{cat.label}</span>
                </button>
              ))}
            </div>
          </div>

          <div>
            <label htmlFor="audit-type" className="block text-sm font-medium text-foreground mb-2">Audit Type</label>
            <Select value={auditType} onValueChange={setAuditType}>
              <SelectTrigger id="audit-type">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="inspection">Inspection</SelectItem>
                <SelectItem value="audit">Audit</SelectItem>
                <SelectItem value="assessment">Assessment</SelectItem>
                <SelectItem value="checklist">Checklist</SelectItem>
                <SelectItem value="survey">Survey</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div>
            <label htmlFor="scoring-method" className="block text-sm font-medium text-foreground mb-2">Scoring Method</label>
            <Select value={scoringMethod} onValueChange={setScoringMethod}>
              <SelectTrigger id="scoring-method">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="percentage">Percentage</SelectItem>
                <SelectItem value="points">Points Based</SelectItem>
                <SelectItem value="weighted">Weighted</SelectItem>
                <SelectItem value="pass_fail">Pass / Fail</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div>
            <label htmlFor="passing-score" className="block text-sm font-medium text-foreground mb-2">
              Pass Threshold: {passingScore}%
            </label>
            <input
              id="passing-score"
              type="range" min={0} max={100} value={passingScore}
              onChange={(e) => setPassingScore(parseInt(e.target.value))}
              className="w-full h-2 bg-surface rounded-lg appearance-none cursor-pointer accent-primary"
            />
            <div className="flex justify-between text-xs text-muted-foreground mt-1">
              <span>0%</span>
              <span>100%</span>
            </div>
          </div>

          <Button onClick={handleSave} disabled={saving} className="w-full">
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
            Save Settings
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}

// ============================================================================
// TEMPLATE PREVIEW
// ============================================================================

interface PreviewPanelProps {
  template: AuditTemplateDetail;
}

function PreviewPanel({ template }: PreviewPanelProps) {
  const activeSections = useMemo(
    () => template.sections.filter(s => s.is_active),
    [template.sections]
  );

  return (
    <div className="max-w-2xl mx-auto">
      <Card>
        <CardContent className="p-6">
          <div className="text-center mb-8">
            <h2 className="text-2xl font-bold text-foreground mb-2">{template.name || 'Untitled Template'}</h2>
            <p className="text-muted-foreground">{template.description}</p>
            <div className="flex items-center justify-center gap-3 mt-4 flex-wrap">
              <Badge>{template.question_count} Questions</Badge>
              <Badge variant="secondary">v{template.version}</Badge>
              <Badge variant={template.is_published ? 'success' : 'warning'}>
                {template.is_published ? 'Published' : 'Draft'}
              </Badge>
              {template.passing_score != null && (
                <Badge variant="success">Pass: {template.passing_score}%</Badge>
              )}
            </div>
          </div>

          {activeSections.map((section, sectionIndex) => (
            <div key={section.id} className="mb-6" role="region" aria-label={`Section ${sectionIndex + 1}: ${section.title}`}>
              <Card className="bg-surface mb-3">
                <CardContent className="p-4">
                  <h3 className="text-lg font-semibold text-foreground">
                    {sectionIndex + 1}. {section.title}
                  </h3>
                  {section.description && (
                    <p className="text-sm text-muted-foreground mt-1">{section.description}</p>
                  )}
                </CardContent>
              </Card>
              <div className="space-y-2 pl-4">
                {(section.questions || []).filter(q => q.is_active).map((question, qIndex) => {
                  const qType = QUESTION_TYPES.find(t => t.type === question.question_type);
                  return (
                    <div key={question.id} className="flex items-start gap-3 p-3 rounded-lg border border-border bg-card">
                      <span className="text-sm text-muted-foreground font-mono">{sectionIndex + 1}.{qIndex + 1}</span>
                      <div className="flex-1">
                        <p className="text-sm text-foreground">
                          {question.question_text || 'Untitled question'}
                          {question.is_required && <span className="text-destructive ml-1">*</span>}
                        </p>
                        <div className="flex items-center gap-2 mt-2 flex-wrap">
                          <Badge variant="secondary">{qType?.label || question.question_type}</Badge>
                          {question.risk_category && (
                            <Badge variant={
                              question.risk_category === 'critical' ? 'critical' :
                              question.risk_category === 'high' ? 'high' :
                              question.risk_category === 'medium' ? 'medium' : 'low'
                            }>
                              {question.risk_category} risk
                            </Badge>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}

          {activeSections.length === 0 && (
            <div className="text-center py-12">
              <Eye className="w-12 h-12 mx-auto text-muted-foreground mb-3" />
              <p className="text-muted-foreground">Add sections and questions to see a preview</p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

// ============================================================================
// MAIN COMPONENT
// ============================================================================

export default function AuditTemplateBuilder() {
  const navigate = useNavigate();
  const { templateId } = useParams();
  const isEditing = Boolean(templateId);

  const [template, setTemplate] = useState<AuditTemplateDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'builder' | 'settings' | 'preview'>('builder');
  const [showAIAssist, setShowAIAssist] = useState(false);
  const [addingSection, setAddingSection] = useState(false);
  const [applyingAI, setApplyingAI] = useState(false);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  const [showLeaveConfirm, setShowLeaveConfirm] = useState(false);
  const [pendingNavigation, setPendingNavigation] = useState<string | null>(null);

  const { toasts, show: showToast, dismiss: dismissToast } = useToast();

  // Template name/description local state
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const nameDebounceRef = useRef<ReturnType<typeof setTimeout>>();

  // Load template
  useEffect(() => {
    const load = async () => {
      if (!isEditing) {
        try {
          const response = await auditsApi.createTemplate({
            name: 'Untitled Template',
            audit_type: 'inspection',
            scoring_method: 'percentage',
            passing_score: 80,
          });
          const detail = await auditsApi.getTemplate(response.data.id);
          setTemplate(detail.data);
          setName(detail.data.name);
          setDescription(detail.data.description || '');
          window.history.replaceState(null, '', `/audit-templates/${response.data.id}/edit`);
        } catch (err) {
          setError('Failed to create template. Please try again.');
          console.error(err);
        } finally {
          setLoading(false);
        }
        return;
      }

      try {
        const response = await auditsApi.getTemplate(Number(templateId));
        setTemplate(response.data);
        setName(response.data.name);
        setDescription(response.data.description || '');
      } catch (err) {
        setError('Failed to load template. It may not exist or you may not have access.');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [templateId, isEditing]);

  // Unsaved changes warning
  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (hasUnsavedChanges) {
        e.preventDefault();
      }
    };
    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, [hasUnsavedChanges]);

  // Cleanup debounce timers on unmount
  useEffect(() => () => {
    if (nameDebounceRef.current) clearTimeout(nameDebounceRef.current);
  }, []);

  const refreshTemplate = useCallback(async () => {
    if (!template) return;
    try {
      const response = await auditsApi.getTemplate(template.id);
      setTemplate(response.data);
    } catch (err) {
      console.error('Failed to refresh template:', err);
    }
  }, [template?.id]);

  const handleSave = useCallback(async () => {
    if (!template) return;
    setSaving(true);
    try {
      await auditsApi.updateTemplate(template.id, { name, description });
      await refreshTemplate();
      setHasUnsavedChanges(false);
      showToast('Template saved successfully', 'success');
    } catch (err) {
      showToast('Failed to save template. Please try again.', 'error');
      console.error(err);
    } finally {
      setSaving(false);
    }
  }, [template, name, description, refreshTemplate, showToast]);

  // Keyboard shortcuts — must be after handleSave is defined
  const handleSaveRef = useRef(handleSave);
  handleSaveRef.current = handleSave;

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 's') {
        e.preventDefault();
        handleSaveRef.current();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const handleSaveSettings = useCallback(async (data: AuditTemplateUpdate) => {
    if (!template) return;
    try {
      await auditsApi.updateTemplate(template.id, data);
      await refreshTemplate();
      showToast('Settings saved successfully', 'success');
    } catch (err) {
      showToast('Failed to save settings.', 'error');
      console.error(err);
    }
  }, [template, refreshTemplate, showToast]);

  const handlePublish = useCallback(async () => {
    if (!template) return;
    setSaving(true);
    try {
      await auditsApi.updateTemplate(template.id, { name, description });
      await auditsApi.publishTemplate(template.id);
      await refreshTemplate();
      showToast('Template published successfully', 'success');
    } catch (err: unknown) {
      const message = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to publish. Ensure at least one question exists.';
      showToast(message, 'error');
    } finally {
      setSaving(false);
    }
  }, [template, name, description, refreshTemplate, showToast]);

  const handleAddSection = useCallback(async () => {
    if (!template) return;
    setAddingSection(true);
    try {
      await auditsApi.createSection(template.id, {
        title: `Section ${(template.sections?.length || 0) + 1}`,
        sort_order: template.sections?.length || 0,
        weight: 1,
      });
      await refreshTemplate();
      showToast('Section added', 'success');
    } catch (err) {
      showToast('Failed to add section.', 'error');
      console.error(err);
    } finally {
      setAddingSection(false);
    }
  }, [template, refreshTemplate, showToast]);

  const handleNameChange = useCallback((value: string) => {
    setName(value);
    setHasUnsavedChanges(true);
    if (nameDebounceRef.current) clearTimeout(nameDebounceRef.current);
    if (!value.trim()) return;
    nameDebounceRef.current = setTimeout(async () => {
      if (template) {
        try {
          await auditsApi.updateTemplate(template.id, { name: value });
        } catch { /* will be saved on explicit save */ }
      }
    }, 1000);
  }, [template]);

  const handleDescriptionChange = useCallback((value: string) => {
    setDescription(value);
    setHasUnsavedChanges(true);
  }, []);

  const handleNavigateAway = useCallback((path: string) => {
    if (hasUnsavedChanges) {
      setPendingNavigation(path);
      setShowLeaveConfirm(true);
    } else {
      navigate(path);
    }
  }, [hasUnsavedChanges, navigate]);

  // Computed stats
  const stats = useMemo(() => {
    if (!template) return { sections: 0, questions: 0, required: 0 };
    const activeSections = template.sections.filter(s => s.is_active);
    const allQuestions = activeSections.flatMap(s => (s.questions || []).filter(q => q.is_active));
    return {
      sections: activeSections.length,
      questions: allQuestions.length,
      required: allQuestions.filter(q => q.is_required).length,
    };
  }, [template]);

  const activeSections = useMemo(
    () => (template?.sections || []).filter(s => s.is_active),
    [template?.sections]
  );

  if (loading) {
    return (
      <div className="p-6">
        <CardSkeleton count={2} />
      </div>
    );
  }

  // Error state
  if (error || !template) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Card className="max-w-md w-full">
          <CardContent className="p-6 text-center">
            <AlertTriangle className="w-12 h-12 text-destructive mx-auto mb-4" />
            <h2 className="text-lg font-semibold text-foreground mb-2">Unable to Load Template</h2>
            <p className="text-muted-foreground mb-6">{error || 'Template not found.'}</p>
            <Button onClick={() => navigate('/audit-templates')}>
              <ArrowLeft className="w-4 h-4" />
              Back to Library
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <ToastContainer toasts={toasts} onDismiss={dismissToast} />

      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div className="flex items-center gap-4">
          <Button
            variant="ghost" size="icon"
            onClick={() => handleNavigateAway('/audit-templates')}
            aria-label="Back to template library"
          >
            <ArrowLeft className="w-5 h-5" />
          </Button>
          <div className="flex-1">
            <label htmlFor="template-name" className="sr-only">Template name</label>
            <Input
              id="template-name"
              value={name}
              onChange={(e) => handleNameChange(e.target.value)}
              placeholder="Untitled Template"
              className="text-xl font-bold border-none bg-transparent px-0 focus-visible:ring-0 h-auto"
              aria-required="true"
            />
            <div className="flex items-center gap-2 mt-1">
              <Badge variant={template.is_published ? 'success' : 'warning'}>
                {template.is_published ? 'Published' : 'Draft'}
              </Badge>
              <span className="text-sm text-muted-foreground">v{template.version}</span>
              <span className="text-sm text-muted-foreground">•</span>
              <span className="text-sm text-muted-foreground">{stats.questions} questions</span>
              {hasUnsavedChanges && (
                <Badge variant="warning">Unsaved changes</Badge>
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          {/* Tabs */}
          <div className="flex bg-secondary rounded-lg p-1" role="tablist" aria-label="Builder views">
            {(['builder', 'settings', 'preview'] as const).map((tab) => (
              <button
                key={tab}
                id={`tab-${tab}`}
                onClick={() => setActiveTab(tab)}
                className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors min-h-[36px] ${
                  activeTab === tab
                    ? 'bg-primary text-primary-foreground'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
                role="tab"
                aria-selected={activeTab === tab}
                aria-controls={`panel-${tab}`}
              >
                {tab.charAt(0).toUpperCase() + tab.slice(1)}
              </button>
            ))}
          </div>

          <Button variant="outline" onClick={() => setShowAIAssist(true)}>
            <Sparkles className="w-4 h-4" />
            AI Assist
          </Button>

          {!template.is_published && (
            <Button variant="success" onClick={handlePublish} disabled={saving || stats.questions === 0}>
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle className="w-4 h-4" />}
              Publish
            </Button>
          )}

          <Button onClick={handleSave} disabled={saving}>
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
            Save
          </Button>
        </div>
      </div>

      {/* Main Content */}
      <div id="panel-builder" role="tabpanel" aria-labelledby="tab-builder" hidden={activeTab !== 'builder'}>
        {activeTab === 'builder' && (
          <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
            {/* Sidebar */}
            <div className="lg:col-span-1 space-y-4">
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm">Template Stats</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  {[
                    { label: 'Sections', value: stats.sections },
                    { label: 'Questions', value: stats.questions },
                    { label: 'Required', value: stats.required },
                    { label: 'Pass Threshold', value: `${template.passing_score ?? 0}%` },
                  ].map((stat) => (
                    <div key={stat.label} className="flex justify-between text-sm">
                      <span className="text-muted-foreground">{stat.label}</span>
                      <span className="font-medium text-foreground">{stat.value}</span>
                    </div>
                  ))}
                </CardContent>
              </Card>

              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm">Quick Actions</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  <Button variant="outline" className="w-full justify-start" size="sm" disabled>
                    <Upload className="w-4 h-4" /> Import from Excel
                  </Button>
                  <Button variant="outline" className="w-full justify-start" size="sm" disabled>
                    <Download className="w-4 h-4" /> Export Template
                  </Button>
                  <Button variant="outline" className="w-full justify-start" size="sm" disabled>
                    <History className="w-4 h-4" /> Version History
                  </Button>
                </CardContent>
              </Card>
            </div>

            {/* Builder Area */}
            <div className="lg:col-span-3 space-y-4">
              <Card>
                <CardContent className="p-4">
                  <label htmlFor="template-description" className="block text-sm font-medium text-foreground mb-2">
                    Template Description
                  </label>
                  <Textarea
                    id="template-description"
                    value={description}
                    onChange={(e) => handleDescriptionChange(e.target.value)}
                    placeholder="Describe the purpose and scope of this audit template..."
                    className="min-h-[60px]"
                  />
                </CardContent>
              </Card>

              {activeSections.map((section) => (
                <SectionEditor
                  key={section.id}
                  section={section}
                  templateId={template.id}
                  onUpdated={refreshTemplate}
                  onDeleted={refreshTemplate}
                />
              ))}

              <Button
                variant="outline" className="w-full py-6 border-dashed border-2"
                onClick={handleAddSection}
                disabled={addingSection}
              >
                {addingSection ? <Loader2 className="w-5 h-5 animate-spin" /> : <Plus className="w-5 h-5" />}
                Add Section
              </Button>
            </div>
          </div>
        )}
      </div>

      <div id="panel-settings" role="tabpanel" aria-labelledby="tab-settings" hidden={activeTab !== 'settings'}>
        {activeTab === 'settings' && (
          <SettingsPanel template={template} onSave={handleSaveSettings} />
        )}
      </div>

      <div id="panel-preview" role="tabpanel" aria-labelledby="tab-preview" hidden={activeTab !== 'preview'}>
        {activeTab === 'preview' && (
          <PreviewPanel template={template} />
        )}
      </div>

      {/* AI Template Generator */}
      {showAIAssist && (
        <AITemplateGenerator
          onClose={() => setShowAIAssist(false)}
          applying={applyingAI}
          onApply={async (generatedSections) => {
            if (applyingAI) return;
            setApplyingAI(true);
            const baseOrder = template.sections?.length || 0;
            let successes = 0;
            let failures = 0;
            try {
              for (let i = 0; i < generatedSections.length; i++) {
                const gs = generatedSections[i];
                try {
                  const sectionRes = await auditsApi.createSection(template.id, {
                    title: gs.title,
                    description: gs.description,
                    sort_order: baseOrder + i,
                  });
                  for (let qi = 0; qi < gs.questions.length; qi++) {
                    const q = gs.questions[qi];
                    const sanitizedType = VALID_QUESTION_TYPES.has(q.type) ? q.type : 'yes_no';
                    await auditsApi.createQuestion(template.id, {
                      section_id: sectionRes.data.id,
                      question_text: q.text || 'New Question',
                      question_type: sanitizedType,
                      is_required: q.required ?? true,
                      weight: q.weight ?? 1,
                      sort_order: qi,
                      risk_category: q.riskLevel || undefined,
                      help_text: q.guidance || undefined,
                    });
                  }
                  successes++;
                } catch (err) {
                  failures++;
                  console.error('Failed to create AI section:', err);
                }
              }
              await refreshTemplate();
              setShowAIAssist(false);
              if (failures === 0) {
                showToast(`${successes} AI-generated sections added`, 'success');
              } else if (successes > 0) {
                showToast(`${successes} sections added, ${failures} failed`, 'error');
              } else {
                showToast('Failed to add AI-generated sections', 'error');
              }
            } finally {
              setApplyingAI(false);
            }
          }}
        />
      )}

      {/* Leave Confirmation Dialog */}
      <Dialog open={showLeaveConfirm} onOpenChange={setShowLeaveConfirm}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Unsaved Changes</DialogTitle>
            <DialogDescription>
              You have unsaved changes. Are you sure you want to leave? Your changes will be lost.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowLeaveConfirm(false)}>Stay</Button>
            <Button
              variant="destructive"
              onClick={() => {
                setShowLeaveConfirm(false);
                setHasUnsavedChanges(false);
                if (pendingNavigation) navigate(pendingNavigation);
              }}
            >
              Leave
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
