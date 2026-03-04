import { useState, useEffect, useRef } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  ArrowLeft,
  ArrowRight,
  Save,
  Pause,
  Play,
  CheckCircle2,
  XCircle,
  Camera,
  MessageSquare,
  ChevronDown,
  ChevronUp,
  Info,
  X,
  RotateCcw,
  Flag,
  Timer,
  CheckCheck,
  MinusCircle,
  ClipboardCheck,
  Loader2,
} from 'lucide-react';
import { auditsApi, getApiErrorMessage } from '../api/client';

// ============================================================================
// TYPES
// ============================================================================

type ResponseType = 
  | 'yes' 
  | 'no' 
  | 'na' 
  | 'pass' 
  | 'fail' 
  | number 
  | string 
  | string[] 
  | null;

interface QuestionResponse {
  questionId: string;
  response: ResponseType;
  notes?: string;
  photos?: string[];
  signature?: string;
  flagged?: boolean;
  timestamp: string;
  duration?: number; // seconds spent on question
}

interface AuditSection {
  id: string;
  title: string;
  description?: string;
  color: string;
  questions: AuditQuestion[];
  isComplete: boolean;
}

interface AuditQuestion {
  id: string;
  text: string;
  description?: string;
  type: string;
  required: boolean;
  weight: number;
  options?: { id: string; label: string; value: string; score?: number }[];
  evidenceRequired: boolean;
  guidance?: string;
  riskLevel?: string;
  isoClause?: string;
}

interface AuditData {
  id: string;
  templateId: string;
  templateName: string;
  location: string;
  asset: string;
  scheduledDate: string;
  auditor: string;
  sections: AuditSection[];
}

const SECTION_COLORS = [
  'from-blue-500/20 to-blue-600/20',
  'from-green-500/20 to-green-600/20',
  'from-purple-500/20 to-purple-600/20',
  'from-orange-500/20 to-orange-600/20',
  'from-pink-500/20 to-pink-600/20',
  'from-cyan-500/20 to-cyan-600/20',
  'from-yellow-500/20 to-yellow-600/20',
  'from-red-500/20 to-red-600/20',
];

function mapBackendQuestionType(q: { question_type: string; allow_na?: boolean; max_score?: number; max_value?: number }): string {
  switch (q.question_type) {
    case 'yes_no': return q.allow_na ? 'yes_no_na' : 'yes_no';
    case 'pass_fail': return 'pass_fail';
    case 'text': return 'text_short';
    case 'textarea': return 'text_long';
    case 'number': return 'numeric';
    case 'signature': return 'signature';
    case 'rating':
    case 'score':
      return (q.max_score ?? q.max_value ?? 5) > 5 ? 'scale_1_10' : 'scale_1_5';
    default: return 'text_short';
  }
}

function parseResponseValue(value: string | undefined | null, questionType: string): ResponseType {
  if (value == null || value === '') return null;
  if (['yes_no', 'yes_no_na'].includes(questionType)) return value as 'yes' | 'no' | 'na';
  if (questionType === 'pass_fail') return value as 'pass' | 'fail';
  if (['scale_1_5', 'scale_1_10', 'numeric'].includes(questionType)) {
    const num = Number(value);
    return isNaN(num) ? value : num;
  }
  return value;
}

function serializeResponse(response: ResponseType): string | undefined {
  if (response === null || response === undefined) return undefined;
  if (typeof response === 'number') return String(response);
  if (Array.isArray(response)) return JSON.stringify(response);
  return String(response);
}

// ============================================================================
// COMPONENTS
// ============================================================================

// Response Button Component
const ResponseButton = ({
  selected,
  onClick,
  variant,
  children,
  icon: Icon,
}: {
  selected: boolean;
  onClick: () => void;
  variant: 'success' | 'danger' | 'warning' | 'neutral';
  children: React.ReactNode;
  icon?: React.ElementType;
}) => {
  const variantStyles = {
    success: 'border-success bg-success/20 text-success',
    danger: 'border-destructive bg-destructive/20 text-destructive',
    warning: 'border-warning bg-warning/20 text-warning',
    neutral: 'border-muted-foreground bg-muted-foreground/20 text-muted-foreground',
  };

  const hoverStyles = {
    success: 'hover:bg-success/30 hover:border-success',
    danger: 'hover:bg-destructive/30 hover:border-destructive',
    warning: 'hover:bg-warning/30 hover:border-warning',
    neutral: 'hover:bg-muted-foreground/30 hover:border-muted-foreground',
  };

  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex-1 flex items-center justify-center gap-2 py-4 px-4 rounded-xl border-2 font-semibold transition-all duration-200
        ${selected ? variantStyles[variant] : `border-border bg-secondary text-muted-foreground ${hoverStyles[variant]}`}`}
    >
      {Icon && <Icon className="w-5 h-5" />}
      {children}
    </button>
  );
};

// Scale Input Component
const ScaleInput = ({
  value,
  onChange,
  max = 5,
}: {
  value: number | null;
  onChange: (val: number) => void;
  max?: number;
}) => {
  return (
    <div className="flex items-center gap-2">
      {Array.from({ length: max }, (_, i) => i + 1).map((num) => (
        <button
          key={num}
          type="button"
          onClick={() => onChange(num)}
          className={`w-12 h-12 rounded-xl font-bold text-lg transition-all duration-200 ${
            value === num
              ? 'bg-primary text-primary-foreground shadow-lg shadow-primary/25'
              : 'bg-secondary text-muted-foreground hover:bg-muted hover:text-foreground border border-border'
          }`}
        >
          {num}
        </button>
      ))}
    </div>
  );
};

// Photo Capture Component
const PhotoCapture = ({
  photos,
  onAdd,
  onRemove,
}: {
  photos: string[];
  onAdd: (photo: string) => void;
  onRemove: (index: number) => void;
}) => {
  const inputRef = useRef<HTMLInputElement>(null);

  const handleCapture = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onloadend = () => {
        onAdd(reader.result as string);
      };
      reader.readAsDataURL(file);
    }
  };

  return (
    <div className="space-y-3">
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        capture="environment"
        onChange={handleCapture}
        className="hidden"
      />
      
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        className="w-full py-4 border-2 border-dashed border-border rounded-xl text-muted-foreground hover:border-primary hover:text-primary transition-colors flex items-center justify-center gap-2"
      >
        <Camera className="w-5 h-5" />
        Take Photo / Upload
      </button>

      {photos.length > 0 && (
        <div className="grid grid-cols-3 gap-2">
          {photos.map((photo, idx) => (
            <div key={idx} className="relative group">
              <img
                src={photo}
                alt={`Evidence ${idx + 1}`}
                className="w-full h-24 object-cover rounded-lg"
              />
              <button
                type="button"
                onClick={() => onRemove(idx)}
                aria-label="Remove photo"
                className="absolute top-1 right-1 p-1 bg-destructive rounded-full text-destructive-foreground opacity-0 group-hover:opacity-100 transition-opacity"
              >
                <X className="w-3 h-3" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

// Signature Pad Component
const SignaturePad = ({
  signature,
  onCapture,
  onClear,
}: {
  signature?: string;
  onCapture: (sig: string) => void;
  onClear: () => void;
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [isDrawing, setIsDrawing] = useState(false);

  const startDrawing = (e: React.MouseEvent | React.TouchEvent) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    setIsDrawing(true);
    const rect = canvas.getBoundingClientRect();
    const clientX = 'touches' in e ? e.touches[0].clientX : e.clientX;
    const clientY = 'touches' in e ? e.touches[0].clientY : e.clientY;
    
    ctx.beginPath();
    ctx.moveTo(clientX - rect.left, clientY - rect.top);
  };

  const draw = (e: React.MouseEvent | React.TouchEvent) => {
    if (!isDrawing) return;
    
    const canvas = canvasRef.current;
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const rect = canvas.getBoundingClientRect();
    const clientX = 'touches' in e ? e.touches[0].clientX : e.clientX;
    const clientY = 'touches' in e ? e.touches[0].clientY : e.clientY;

    ctx.lineTo(clientX - rect.left, clientY - rect.top);
    const primaryHsl = getComputedStyle(document.documentElement).getPropertyValue('--primary').trim();
    ctx.strokeStyle = `hsl(${primaryHsl})`;
    ctx.lineWidth = 2;
    ctx.lineCap = 'round';
    ctx.stroke();
  };

  const stopDrawing = () => {
    if (isDrawing && canvasRef.current) {
      setIsDrawing(false);
      onCapture(canvasRef.current.toDataURL());
    }
  };

  const clearCanvas = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    ctx.clearRect(0, 0, canvas.width, canvas.height);
    onClear();
  };

  return (
    <div className="space-y-3">
      <div className="relative">
        <canvas
          ref={canvasRef}
          width={400}
          height={150}
          onMouseDown={startDrawing}
          onMouseMove={draw}
          onMouseUp={stopDrawing}
          onMouseLeave={stopDrawing}
          onTouchStart={startDrawing}
          onTouchMove={draw}
          onTouchEnd={stopDrawing}
          className="w-full h-40 bg-secondary border border-border rounded-xl cursor-crosshair touch-none"
        />
        {!signature && (
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
            <p className="text-muted-foreground">Sign here</p>
          </div>
        )}
      </div>
      <button
        type="button"
        onClick={clearCanvas}
        className="text-sm text-muted-foreground hover:text-foreground flex items-center gap-1"
      >
        <RotateCcw className="w-4 h-4" /> Clear Signature
      </button>
    </div>
  );
};

// ============================================================================
// MAIN COMPONENT
// ============================================================================

export default function AuditExecution() {
  const navigate = useNavigate();
  const { auditId: runId } = useParams<{ auditId: string }>();

  const [audit, setAudit] = useState<AuditData | null>(null);
  const [loading, setLoading] = useState(!!runId);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [responseIdMap, setResponseIdMap] = useState<Record<string, number>>({});
  const [currentSectionIndex, setCurrentSectionIndex] = useState(0);
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
  const [responses, setResponses] = useState<Record<string, QuestionResponse>>({});
  const [isPaused, setIsPaused] = useState(false);
  const [elapsedTime, setElapsedTime] = useState(0);
  const [showGuidance, setShowGuidance] = useState(false);
  const [showSummary, setShowSummary] = useState(false);

  const runIdNum = runId ? Number(runId) : null;

  // Timer
  useEffect(() => {
    if (isPaused || !audit) return;
    
    const timer = setInterval(() => {
      setElapsedTime(prev => prev + 1);
    }, 1000);

    return () => clearInterval(timer);
  }, [isPaused, audit]);

  // Load audit run from API
  useEffect(() => {
    if (!runIdNum || isNaN(runIdNum)) return;

    let cancelled = false;

    const loadRun = async () => {
      try {
        setLoading(true);
        setError(null);

        const runRes = await auditsApi.getRunDetail(runIdNum);
        const runData = runRes.data;

        const templateRes = await auditsApi.getTemplate(runData.template_id);
        const templateData = templateRes.data;

        if (cancelled) return;

        const sections: AuditSection[] = templateData.sections
          .filter(s => s.is_active)
          .sort((a, b) => a.sort_order - b.sort_order)
          .map((s, idx) => ({
            id: String(s.id),
            title: s.title,
            description: s.description || undefined,
            color: SECTION_COLORS[idx % SECTION_COLORS.length],
            questions: s.questions
              .filter(q => q.is_active)
              .sort((a, b) => a.sort_order - b.sort_order)
              .map(q => ({
                id: String(q.id),
                text: q.question_text,
                description: q.description || undefined,
                type: mapBackendQuestionType(q),
                required: q.is_required,
                weight: q.weight,
                options: q.options?.map(o => ({
                  id: o.value,
                  label: o.label,
                  value: o.value,
                  score: o.score ?? undefined,
                })),
                evidenceRequired: false,
                guidance: q.help_text || undefined,
                riskLevel: q.risk_category || undefined,
                isoClause: undefined,
              })),
            isComplete: false,
          }));

        const questionTypeMap: Record<string, string> = {};
        for (const section of sections) {
          for (const q of section.questions) {
            questionTypeMap[q.id] = q.type;
          }
        }

        const existingResponses: Record<string, QuestionResponse> = {};
        const idMap: Record<string, number> = {};

        for (const r of runData.responses || []) {
          const qId = String(r.question_id);
          const qType = questionTypeMap[qId] || 'text_short';
          existingResponses[qId] = {
            questionId: qId,
            response: parseResponseValue(r.response_value, qType),
            notes: r.notes || undefined,
            timestamp: r.created_at,
          };
          idMap[qId] = r.id;
        }

        setAudit({
          id: String(runData.id),
          templateId: String(runData.template_id),
          templateName: runData.template_name || templateData.name,
          location: runData.location || '',
          asset: runData.title || '',
          scheduledDate: runData.scheduled_date || '',
          auditor: '',
          sections,
        });
        setResponses(existingResponses);
        setResponseIdMap(idMap);

        if (runData.status === 'scheduled') {
          await auditsApi.startRun(runIdNum);
        }
      } catch (err) {
        if (!cancelled) {
          setError(getApiErrorMessage(err));
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    loadRun();

    return () => { cancelled = true; };
  }, [runIdNum]);

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const saveAllResponses = async (): Promise<boolean> => {
    if (!runIdNum) return false;

    setSaving(true);
    setError(null);
    try {
      const updatedIdMap = { ...responseIdMap };

      for (const [questionId, resp] of Object.entries(responses)) {
        if (resp.response === null && !resp.notes) continue;

        const payload = {
          response_value: serializeResponse(resp.response),
          notes: resp.notes || undefined,
        };

        const existingId = updatedIdMap[questionId];
        if (existingId) {
          await auditsApi.updateResponse(existingId, payload);
        } else {
          const res = await auditsApi.createResponse(runIdNum, {
            question_id: Number(questionId),
            ...payload,
          });
          updatedIdMap[questionId] = res.data.id;
        }
      }

      setResponseIdMap(updatedIdMap);
      return true;
    } catch (err) {
      setError(getApiErrorMessage(err));
      return false;
    } finally {
      setSaving(false);
    }
  };

  const handleSaveDraft = async () => {
    await saveAllResponses();
  };

  const handleSubmitAudit = async () => {
    if (!runIdNum) return;

    const saved = await saveAllResponses();
    if (!saved) return;

    try {
      setSaving(true);
      await auditsApi.completeRun(runIdNum);
      navigate('/audits');
    } catch (err) {
      setError(getApiErrorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center p-4">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="w-10 h-10 animate-spin text-primary" />
          <p className="text-muted-foreground">Loading audit...</p>
        </div>
      </div>
    );
  }

  if (!audit) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center p-4">
        <div className="max-w-md w-full bg-card border border-border rounded-2xl p-8 text-center">
          <ClipboardCheck className="w-16 h-16 mx-auto text-muted-foreground mb-4" />
          <h2 className="text-2xl font-bold text-foreground mb-2">
            {error ? 'Error Loading Audit' : 'No Audit Loaded'}
          </h2>
          <p className="text-muted-foreground mb-6">
            {error || 'Select an audit from the audit list to begin execution.'}
          </p>
          <button
            onClick={() => navigate('/audits')}
            className="px-6 py-3 bg-primary text-primary-foreground font-semibold rounded-xl hover:opacity-90 transition-opacity"
          >
            Go to Audits
          </button>
        </div>
      </div>
    );
  }

  // Current section and question
  const currentSection = audit.sections[currentSectionIndex];
  const currentQuestion = currentSection.questions[currentQuestionIndex];
  const currentResponse = responses[currentQuestion.id];

  // Calculate progress
  const totalQuestions = audit.sections.reduce((sum, s) => sum + s.questions.length, 0);
  const answeredQuestions = Object.keys(responses).length;
  const progressPercentage = totalQuestions > 0 ? (answeredQuestions / totalQuestions) * 100 : 0;

  // Calculate score
  const calculateScore = () => {
    let totalWeight = 0;
    let achievedWeight = 0;

    audit.sections.forEach(section => {
      section.questions.forEach(question => {
        const response = responses[question.id];
        if (!response) return;

        totalWeight += question.weight;

        if (question.type === 'pass_fail' || question.type === 'yes_no') {
          if (response.response === 'pass' || response.response === 'yes') {
            achievedWeight += question.weight;
          }
        } else if (question.type === 'yes_no_na') {
          if (response.response === 'yes' || response.response === 'na') {
            achievedWeight += question.weight;
          }
        } else if (question.type.startsWith('scale_')) {
          const max = question.type === 'scale_1_5' ? 5 : 10;
          achievedWeight += (Number(response.response) / max) * question.weight;
        } else if (question.weight > 0) {
          achievedWeight += question.weight;
        }
      });
    });

    return totalWeight > 0 ? Math.round((achievedWeight / totalWeight) * 100) : 0;
  };

  // Update response
  const updateResponse = (updates: Partial<Omit<QuestionResponse, 'questionId' | 'timestamp'>>) => {
    setResponses(prev => ({
      ...prev,
      [currentQuestion.id]: {
        ...prev[currentQuestion.id],
        ...updates,
        questionId: currentQuestion.id,
        timestamp: new Date().toISOString(),
      },
    }));
  };

  // Navigation
  const goNext = () => {
    if (currentQuestionIndex < currentSection.questions.length - 1) {
      setCurrentQuestionIndex(prev => prev + 1);
    } else if (currentSectionIndex < audit.sections.length - 1) {
      setCurrentSectionIndex(prev => prev + 1);
      setCurrentQuestionIndex(0);
    } else {
      setShowSummary(true);
    }
  };

  const goPrev = () => {
    if (currentQuestionIndex > 0) {
      setCurrentQuestionIndex(prev => prev - 1);
    } else if (currentSectionIndex > 0) {
      setCurrentSectionIndex(prev => prev - 1);
      setCurrentQuestionIndex(audit.sections[currentSectionIndex - 1].questions.length - 1);
    }
  };

  // Render question input based on type
  const renderQuestionInput = () => {
    switch (currentQuestion.type) {
      case 'pass_fail':
        return (
          <div className="flex gap-4">
            <ResponseButton
              selected={currentResponse?.response === 'pass'}
              onClick={() => updateResponse({ response: 'pass' })}
              variant="success"
              icon={CheckCircle2}
            >
              PASS
            </ResponseButton>
            <ResponseButton
              selected={currentResponse?.response === 'fail'}
              onClick={() => updateResponse({ response: 'fail' })}
              variant="danger"
              icon={XCircle}
            >
              FAIL
            </ResponseButton>
          </div>
        );

      case 'yes_no':
        return (
          <div className="flex gap-4">
            <ResponseButton
              selected={currentResponse?.response === 'yes'}
              onClick={() => updateResponse({ response: 'yes' })}
              variant="success"
              icon={CheckCircle2}
            >
              YES
            </ResponseButton>
            <ResponseButton
              selected={currentResponse?.response === 'no'}
              onClick={() => updateResponse({ response: 'no' })}
              variant="danger"
              icon={XCircle}
            >
              NO
            </ResponseButton>
          </div>
        );

      case 'yes_no_na':
        return (
          <div className="flex gap-3">
            <ResponseButton
              selected={currentResponse?.response === 'yes'}
              onClick={() => updateResponse({ response: 'yes' })}
              variant="success"
              icon={CheckCircle2}
            >
              YES
            </ResponseButton>
            <ResponseButton
              selected={currentResponse?.response === 'no'}
              onClick={() => updateResponse({ response: 'no' })}
              variant="danger"
              icon={XCircle}
            >
              NO
            </ResponseButton>
            <ResponseButton
              selected={currentResponse?.response === 'na'}
              onClick={() => updateResponse({ response: 'na' })}
              variant="neutral"
              icon={MinusCircle}
            >
              N/A
            </ResponseButton>
          </div>
        );

      case 'scale_1_5':
        return (
          <ScaleInput
            value={currentResponse?.response as number | null}
            onChange={(val) => updateResponse({ response: val })}
            max={5}
          />
        );

      case 'scale_1_10':
        return (
          <ScaleInput
            value={currentResponse?.response as number | null}
            onChange={(val) => updateResponse({ response: val })}
            max={10}
          />
        );

      case 'text_short':
        return (
          <input
            type="text"
            value={(currentResponse?.response as string) || ''}
            onChange={(e) => updateResponse({ response: e.target.value })}
            placeholder="Enter your response..."
            className="w-full px-4 py-3 bg-secondary border border-border rounded-xl text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-ring"
          />
        );

      case 'text_long':
        return (
          <textarea
            value={(currentResponse?.response as string) || ''}
            onChange={(e) => updateResponse({ response: e.target.value })}
            placeholder="Enter detailed response..."
            rows={4}
            className="w-full px-4 py-3 bg-secondary border border-border rounded-xl text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-ring resize-none"
          />
        );

      case 'numeric':
        return (
          <input
            type="number"
            value={(currentResponse?.response as string) || ''}
            onChange={(e) => updateResponse({ response: e.target.value })}
            placeholder="Enter number..."
            className="w-full px-4 py-3 bg-secondary border border-border rounded-xl text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-ring"
          />
        );

      case 'signature':
        return (
          <SignaturePad
            signature={currentResponse?.signature}
            onCapture={(sig) => updateResponse({ signature: sig, response: 'signed' })}
            onClear={() => updateResponse({ signature: undefined, response: null })}
          />
        );

      default:
        return null;
    }
  };

  if (showSummary) {
    const score = calculateScore();
    const passed = score >= 80;

    return (
      <div className="min-h-screen bg-background flex items-center justify-center p-4">
        <div className="max-w-lg w-full bg-card border border-border rounded-3xl p-8 text-center animate-fade-in">
          {/* Score Display */}
          <div className={`w-32 h-32 mx-auto rounded-full flex items-center justify-center mb-6 ${
            passed ? 'bg-success' : 'bg-destructive'
          }`}>
            <span className={`text-4xl font-bold ${passed ? 'text-success-foreground' : 'text-destructive-foreground'}`}>{score}%</span>
          </div>

          <h2 className={`text-3xl font-bold mb-2 ${passed ? 'text-success' : 'text-destructive'}`}>
            {passed ? 'AUDIT PASSED' : 'AUDIT FAILED'}
          </h2>
          <p className="text-muted-foreground mb-8">
            {audit.templateName} - {audit.asset}
          </p>

          {/* Stats */}
          <div className="grid grid-cols-3 gap-4 mb-8">
            <div className="bg-secondary rounded-xl p-4">
              <p className="text-2xl font-bold text-foreground">{answeredQuestions}</p>
              <p className="text-xs text-muted-foreground">Questions Answered</p>
            </div>
            <div className="bg-secondary rounded-xl p-4">
              <p className="text-2xl font-bold text-foreground">{formatTime(elapsedTime)}</p>
              <p className="text-xs text-muted-foreground">Duration</p>
            </div>
            <div className="bg-secondary rounded-xl p-4">
              <p className="text-2xl font-bold text-foreground">
                {Object.values(responses).filter(r => r.photos && r.photos.length > 0).length}
              </p>
              <p className="text-xs text-muted-foreground">Photos</p>
            </div>
          </div>

          {/* Findings Summary */}
          <div className="text-left mb-8">
            <h3 className="text-lg font-semibold text-foreground mb-3">Findings</h3>
            <div className="space-y-2">
              {Object.values(responses)
                .filter(r => r.response === 'fail' || r.response === 'no')
                .map((r, idx) => {
                  const question = audit.sections
                    .flatMap(s => s.questions)
                    .find(q => q.id === r.questionId);
                  return (
                    <div key={idx} className="flex items-start gap-2 p-3 bg-destructive/10 border border-destructive/20 rounded-lg">
                      <XCircle className="w-5 h-5 text-destructive mt-0.5" />
                      <p className="text-sm text-destructive">{question?.text}</p>
                    </div>
                  );
                })}
              {Object.values(responses).filter(r => r.response === 'fail' || r.response === 'no').length === 0 && (
                <p className="text-sm text-muted-foreground">No failed items</p>
              )}
            </div>
          </div>

          {/* Actions */}
          <div className="flex gap-3">
            <button
              onClick={() => navigate('/audits')}
              className="flex-1 py-3 bg-secondary text-foreground rounded-xl hover:bg-muted transition-colors"
            >
              Back to Audits
            </button>
            <button
              onClick={handleSubmitAudit}
              disabled={saving}
              className="flex-1 py-3 bg-primary text-primary-foreground font-semibold rounded-xl hover:opacity-90 transition-opacity disabled:opacity-50"
            >
              {saving ? 'Submitting...' : 'Submit Audit'}
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background flex flex-col">
      {/* Header */}
      <header className="sticky top-0 z-40 bg-card/80 backdrop-blur-xl border-b border-border">
        <div className="px-4 py-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <button
                onClick={() => navigate('/audits')}
                aria-label="Go back"
                className="p-2 hover:bg-secondary rounded-lg transition-colors"
              >
                <ArrowLeft className="w-5 h-5 text-muted-foreground" />
              </button>
              <div>
                <h1 className="text-lg font-bold text-foreground">{audit.templateName}</h1>
                <p className="text-xs text-muted-foreground">{audit.asset} • {audit.location}</p>
              </div>
            </div>

            <div className="flex items-center gap-3">
              {/* Timer */}
              <div className="flex items-center gap-2 px-3 py-1.5 bg-secondary rounded-lg">
                <Timer className="w-4 h-4 text-muted-foreground" />
                <span className="text-sm font-mono text-foreground">{formatTime(elapsedTime)}</span>
              </div>

              {/* Pause/Play */}
              <button
                onClick={() => setIsPaused(!isPaused)}
                aria-label={isPaused ? 'Resume' : 'Pause'}
                className={`p-2 rounded-lg transition-colors ${
                  isPaused ? 'bg-warning/20 text-warning' : 'bg-secondary text-muted-foreground hover:text-foreground'
                }`}
              >
                {isPaused ? <Play className="w-5 h-5" /> : <Pause className="w-5 h-5" />}
              </button>

              {/* Save Draft */}
              <button
                onClick={handleSaveDraft}
                disabled={saving}
                className="flex items-center gap-2 px-4 py-2 bg-secondary text-foreground rounded-lg hover:bg-muted disabled:opacity-50"
              >
                {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                Save
              </button>
            </div>
          </div>

          {/* Progress Bar */}
          <div className="mt-3">
            <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
              <span>Progress: {answeredQuestions}/{totalQuestions} questions</span>
              <span>{Math.round(progressPercentage)}%</span>
            </div>
            <div className="h-2 bg-secondary rounded-full overflow-hidden">
              <div
                className="h-full bg-primary transition-all duration-300"
                style={{ width: `${progressPercentage}%` }}
              />
            </div>
          </div>
        </div>
      </header>

      {/* Error Banner */}
      {error && (
        <div className="bg-destructive/10 border-b border-destructive/20 px-4 py-3 flex items-center justify-between">
          <p className="text-sm text-destructive">{error}</p>
          <button onClick={() => setError(null)} className="text-destructive hover:text-destructive/80">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Section Navigation */}
      <div className="bg-card/50 border-b border-border overflow-x-auto">
        <div className="flex px-4 py-2 gap-2">
          {audit.sections.map((section, idx) => {
            const sectionAnswered = section.questions.filter(q => responses[q.id]).length;
            const isComplete = sectionAnswered === section.questions.length;
            const isCurrent = idx === currentSectionIndex;

            return (
              <button
                key={section.id}
                onClick={() => {
                  setCurrentSectionIndex(idx);
                  setCurrentQuestionIndex(0);
                }}
                className={`flex items-center gap-2 px-4 py-2 rounded-xl whitespace-nowrap transition-all ${
                  isCurrent
                    ? `bg-gradient-to-r ${section.color} text-foreground`
                    : isComplete
                    ? 'bg-success/20 text-success border border-success/30'
                    : 'bg-secondary text-muted-foreground hover:bg-muted'
                }`}
              >
                {isComplete ? (
                  <CheckCheck className="w-4 h-4" />
                ) : (
                  <span className="w-5 h-5 rounded-full bg-input text-xs flex items-center justify-center">
                    {idx + 1}
                  </span>
                )}
                <span className="text-sm font-medium">{section.title}</span>
                <span className="text-xs opacity-75">{sectionAnswered}/{section.questions.length}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Main Content */}
      <main className="flex-1 overflow-y-auto">
        <div className="max-w-2xl mx-auto p-4 pb-32">
          {/* Question Card */}
          <div className="bg-card/50 border border-border rounded-3xl overflow-hidden">
            {/* Question Header */}
            <div className={`bg-gradient-to-r ${currentSection.color} p-0.5`}>
              <div className="bg-card p-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-muted-foreground">
                      {currentSection.title} • Question {currentQuestionIndex + 1} of {currentSection.questions.length}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    {currentQuestion.riskLevel && (
                      <span className={`px-2 py-1 text-xs rounded ${
                        currentQuestion.riskLevel === 'critical' ? 'bg-destructive/20 text-destructive' :
                        currentQuestion.riskLevel === 'high' ? 'bg-warning/20 text-warning' :
                        currentQuestion.riskLevel === 'medium' ? 'bg-warning/20 text-warning' :
                        'bg-success/20 text-success'
                      }`}>
                        {currentQuestion.riskLevel} risk
                      </span>
                    )}
                    {currentQuestion.required && (
                      <span className="px-2 py-1 bg-primary/20 text-primary text-xs rounded">
                        Required
                      </span>
                    )}
                  </div>
                </div>
              </div>
            </div>

            {/* Question Content */}
            <div className="p-6 space-y-6">
              {/* Question Text */}
              <div>
                <h2 className="text-xl font-semibold text-foreground mb-2">
                  {currentQuestion.text}
                </h2>
                {currentQuestion.description && (
                  <p className="text-sm text-muted-foreground">{currentQuestion.description}</p>
                )}
              </div>

              {/* Guidance */}
              {currentQuestion.guidance && (
                <div>
                  <button
                    onClick={() => setShowGuidance(!showGuidance)}
                    className="flex items-center gap-2 text-sm text-primary hover:text-primary"
                  >
                    <Info className="w-4 h-4" />
                    Auditor Guidance
                    {showGuidance ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                  </button>
                  {showGuidance && (
                    <div className="mt-2 p-3 bg-primary/10 border border-primary/20 rounded-lg">
                      <p className="text-sm text-primary">{currentQuestion.guidance}</p>
                    </div>
                  )}
                </div>
              )}

              {/* Response Input */}
              <div>
                {renderQuestionInput()}
              </div>

              {/* Evidence Required */}
              {currentQuestion.evidenceRequired && (
                <div className="pt-4 border-t border-border">
                  <div className="flex items-center gap-2 mb-3">
                    <Camera className="w-4 h-4 text-info" />
                    <span className="text-sm font-medium text-foreground">Photo Evidence Required</span>
                  </div>
                  <PhotoCapture
                    photos={currentResponse?.photos || []}
                    onAdd={(photo) => {
                      updateResponse({
                        photos: [...(currentResponse?.photos || []), photo],
                      });
                    }}
                    onRemove={(idx) => {
                      updateResponse({
                        photos: currentResponse?.photos?.filter((_, i) => i !== idx) || [],
                      });
                    }}
                  />
                </div>
              )}

              {/* Notes */}
              <div className="pt-4 border-t border-border">
                <div className="flex items-center gap-2 mb-3">
                  <MessageSquare className="w-4 h-4 text-muted-foreground" />
                  <span className="text-sm font-medium text-foreground">Additional Notes</span>
                </div>
                <textarea
                  value={currentResponse?.notes || ''}
                  onChange={(e) => updateResponse({ notes: e.target.value })}
                  placeholder="Add any additional observations..."
                  rows={2}
                  className="w-full px-4 py-3 bg-secondary border border-border rounded-xl text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-ring resize-none text-sm"
                />
              </div>

              {/* Flag Issue */}
              <button
                onClick={() => updateResponse({ flagged: !currentResponse?.flagged })}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
                  currentResponse?.flagged
                    ? 'bg-destructive/20 text-destructive border border-destructive/30'
                    : 'bg-secondary text-muted-foreground hover:text-foreground'
                }`}
              >
                <Flag className={`w-4 h-4 ${currentResponse?.flagged ? 'fill-current' : ''}`} />
                {currentResponse?.flagged ? 'Issue Flagged' : 'Flag for Follow-up'}
              </button>
            </div>
          </div>
        </div>
      </main>

      {/* Navigation Footer */}
      <footer className="fixed bottom-0 left-0 right-0 bg-card/80 backdrop-blur-xl border-t border-border p-4">
        <div className="max-w-2xl mx-auto flex items-center justify-between">
          <button
            onClick={goPrev}
            disabled={currentSectionIndex === 0 && currentQuestionIndex === 0}
            className="flex items-center gap-2 px-6 py-3 bg-secondary text-foreground rounded-xl hover:bg-muted disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
            Previous
          </button>

          {/* Quick Jump */}
          <div className="flex items-center gap-1">
            {currentSection.questions.map((_, idx) => (
              <button
                key={idx}
                onClick={() => setCurrentQuestionIndex(idx)}
                className={`w-3 h-3 rounded-full transition-all ${
                  idx === currentQuestionIndex
                    ? 'bg-primary w-6'
                    : responses[currentSection.questions[idx].id]
                    ? 'bg-success'
                    : 'bg-input hover:bg-muted'
                }`}
              />
            ))}
          </div>

          <button
            onClick={goNext}
            className="flex items-center gap-2 px-6 py-3 bg-primary text-primary-foreground font-semibold rounded-xl hover:opacity-90 transition-opacity"
          >
            {currentSectionIndex === audit.sections.length - 1 && 
             currentQuestionIndex === currentSection.questions.length - 1
              ? 'Finish'
              : 'Next'
            }
            <ArrowRight className="w-5 h-5" />
          </button>
        </div>
      </footer>
    </div>
  );
}
