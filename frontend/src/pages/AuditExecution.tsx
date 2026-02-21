import { useState, useEffect, useRef, useCallback } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { auditsApi } from "../api/client";
import { useToast, ToastContainer } from "../components/ui/Toast";
import { CardSkeleton } from "../components/ui/SkeletonLoader";
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
  Loader2,
  Send,
} from "lucide-react";

// ============================================================================
// TYPES
// ============================================================================

type ResponseType =
  | "yes"
  | "no"
  | "na"
  | "pass"
  | "fail"
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
  duration?: number;
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
  allowNa: boolean;
  weight: number;
  options?: {
    value: string;
    label: string;
    score?: number;
    triggers_finding?: boolean;
  }[];
  minValue?: number;
  maxValue?: number;
  maxScore?: number;
  evidenceRequired: boolean;
  guidance?: string;
  riskLevel?: string;
  isoClause?: string;
}

interface AuditData {
  id: string;
  templateName: string;
  location: string;
  asset: string;
  status: string;
  sections: AuditSection[];
}

interface TemplateApiSection {
  id: number | string;
  title?: string;
  description?: string;
  questions?: TemplateApiQuestion[];
}

interface TemplateApiQuestion {
  id: number | string;
  question_text?: string;
  text?: string;
  description?: string;
  question_type?: string;
  type?: string;
  is_required?: boolean;
  is_active?: boolean;
  allow_na?: boolean;
  weight?: number;
  options?: {
    value: string;
    label: string;
    score?: number;
    triggers_finding?: boolean;
  }[];
  options_json?: unknown;
  min_value?: number;
  max_value?: number;
  max_score?: number;
  evidence_required?: boolean;
  help_text?: string;
  risk_category?: string;
  iso_clause?: string;
}

interface TemplateApiData {
  sections?: TemplateApiSection[];
  name?: string;
}

interface RunApiResponse {
  question_id: number | string;
  id: number | string;
  is_na?: boolean;
  response_value?: string;
  score?: number;
  notes?: string;
  flagged?: boolean;
  created_at?: string;
}

interface RunApiData {
  id: number | string;
  location?: string;
  title?: string;
  status?: string;
  responses?: RunApiResponse[];
}

interface ResponsePayload {
  question_id: number;
  response_value: string | undefined;
  score?: number;
  max_score?: number;
  notes?: string;
  is_na: boolean;
}

const SECTION_COLORS = [
  "from-blue-500 to-cyan-500",
  "from-purple-500 to-pink-500",
  "from-orange-500 to-amber-500",
  "from-green-500 to-emerald-500",
  "from-red-500 to-rose-500",
  "from-indigo-500 to-violet-500",
];

// ============================================================================
// COMPONENTS
// ============================================================================

const ResponseButton = ({
  selected,
  onClick,
  variant,
  children,
  icon: Icon,
}: {
  selected: boolean;
  onClick: () => void;
  variant: "success" | "danger" | "warning" | "neutral";
  children: React.ReactNode;
  icon?: React.ElementType;
}) => {
  const variantStyles = {
    success: "border-green-500 bg-green-500/20 text-green-400",
    danger: "border-red-500 bg-red-500/20 text-red-400",
    warning: "border-amber-500 bg-amber-500/20 text-amber-400",
    neutral: "border-slate-500 bg-slate-500/20 text-slate-400",
  };

  const hoverStyles = {
    success: "hover:bg-green-500/30 hover:border-green-400",
    danger: "hover:bg-red-500/30 hover:border-red-400",
    warning: "hover:bg-amber-500/30 hover:border-amber-400",
    neutral: "hover:bg-slate-500/30 hover:border-slate-400",
  };

  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex-1 flex items-center justify-center gap-2 py-4 px-4 rounded-xl border-2 font-semibold transition-all duration-200
        ${selected ? variantStyles[variant] : `border-border bg-card text-muted-foreground ${hoverStyles[variant]}`}`}
    >
      {Icon && <Icon className="w-5 h-5" />}
      {children}
    </button>
  );
};

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
              ? "bg-purple-500 text-white shadow-lg shadow-purple-500/25"
              : "bg-card text-muted-foreground hover:bg-surface hover:text-foreground border border-border"
          }`}
        >
          {num}
        </button>
      ))}
    </div>
  );
};

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
        className="w-full py-4 border-2 border-dashed border-border rounded-xl text-muted-foreground hover:border-purple-500 hover:text-purple-400 transition-colors flex items-center justify-center gap-2"
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
                className="absolute top-1 right-1 p-1 bg-red-500 rounded-full text-white opacity-0 group-hover:opacity-100 transition-opacity"
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

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    setIsDrawing(true);
    const rect = canvas.getBoundingClientRect();
    const clientX = "touches" in e ? e.touches[0]!.clientX : e.clientX;
    const clientY = "touches" in e ? e.touches[0]!.clientY : e.clientY;

    ctx.beginPath();
    ctx.moveTo(clientX - rect.left, clientY - rect.top);
  };

  const draw = (e: React.MouseEvent | React.TouchEvent) => {
    if (!isDrawing) return;

    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const rect = canvas.getBoundingClientRect();
    const clientX = "touches" in e ? e.touches[0]!.clientX : e.clientX;
    const clientY = "touches" in e ? e.touches[0]!.clientY : e.clientY;

    ctx.lineTo(clientX - rect.left, clientY - rect.top);
    ctx.strokeStyle = "#a855f7";
    ctx.lineWidth = 2;
    ctx.lineCap = "round";
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

    const ctx = canvas.getContext("2d");
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
          className="w-full h-40 bg-card border border-border rounded-xl cursor-crosshair touch-none"
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
  const { auditId } = useParams<{ auditId: string }>();
  const { toasts, show: showToast, dismiss: dismissToast } = useToast();

  const [audit, setAudit] = useState<AuditData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentSectionIndex, setCurrentSectionIndex] = useState(0);
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
  const [responses, setResponses] = useState<Record<string, QuestionResponse>>(
    {},
  );
  const [isPaused, setIsPaused] = useState(false);
  const [elapsedTime, setElapsedTime] = useState(0);
  const [showGuidance, setShowGuidance] = useState(false);
  const [showSummary, setShowSummary] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [saveStatus, setSaveStatus] = useState<
    "idle" | "saving" | "saved" | "error"
  >("idle");

  const responseIdMapRef = useRef<Record<string, number>>({});

  // Load audit run from API
  const loadAuditRun = useCallback(async () => {
    if (!auditId) return;
    try {
      setLoading(true);
      setError(null);
      const numericId = parseInt(auditId, 10);
      const runData = await auditsApi.getRun(numericId);
      const templateData = await auditsApi.getTemplate(
        runData.data.template_id,
      );

      const tplData = templateData.data as TemplateApiData;
      const sections: AuditSection[] = (tplData.sections || []).map(
        (sec: TemplateApiSection, sIdx: number) => ({
          id: String(sec.id),
          title: String(sec.title || ""),
          description: sec.description ? String(sec.description) : undefined,
          color: SECTION_COLORS[sIdx % SECTION_COLORS.length]!,
          isComplete: false,
          questions: (sec.questions || [])
            .filter((q: TemplateApiQuestion) => q.is_active !== false)
            .map((q: TemplateApiQuestion) => ({
              id: String(q.id),
              text: String(q.question_text || q.text || ""),
              description: q.description ? String(q.description) : undefined,
              type: String(q.question_type || q.type || "yes_no"),
              required: q.is_required !== false,
              allowNa: q.allow_na === true,
              weight: Number(q.weight || 1),
              options:
                q.options || (q.options_json as typeof q.options) || undefined,
              minValue: q.min_value != null ? Number(q.min_value) : undefined,
              maxValue: q.max_value != null ? Number(q.max_value) : undefined,
              maxScore: q.max_score != null ? Number(q.max_score) : undefined,
              evidenceRequired: q.evidence_required === true,
              guidance: q.help_text ? String(q.help_text) : undefined,
              riskLevel: q.risk_category ? String(q.risk_category) : undefined,
              isoClause: q.iso_clause ? String(q.iso_clause) : undefined,
            })),
        }),
      );

      const rd = runData.data as RunApiData;
      setAudit({
        id: String(rd.id),
        templateName: String(tplData.name || ""),
        location: String(rd.location || ""),
        asset: String(rd.title || ""),
        status: String(rd.status || "scheduled"),
        sections,
      });

      // Restore previously saved responses
      const existingResponses: Record<string, QuestionResponse> = {};
      if (rd.responses) {
        for (const r of rd.responses as RunApiResponse[]) {
          const qId = String(r.question_id);
          responseIdMapRef.current[qId] = Number(r.id);
          existingResponses[qId] = {
            questionId: qId,
            response: r.is_na
              ? "na"
              : r.response_value
                ? String(r.response_value)
                : r.score != null
                  ? Number(r.score)
                  : null,
            notes: r.notes ? String(r.notes) : undefined,
            flagged: r.flagged === true,
            timestamp: String(r.created_at || new Date().toISOString()),
          };
        }
      }
      setResponses(existingResponses);
    } catch (err) {
      console.error("Failed to load audit run:", err);
      setError("Failed to load audit. Please try again.");
    } finally {
      setLoading(false);
    }
  }, [auditId]);

  useEffect(() => {
    loadAuditRun();
  }, [loadAuditRun]);

  // Timer
  useEffect(() => {
    if (isPaused || loading || showSummary) return;

    const timer = setInterval(() => {
      setElapsedTime((prev) => prev + 1);
    }, 1000);

    return () => clearInterval(timer);
  }, [isPaused, loading, showSummary]);

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  };

  const currentSection = audit?.sections[currentSectionIndex];
  const currentQuestion = currentSection?.questions[currentQuestionIndex];
  const currentResponse = currentQuestion
    ? responses[currentQuestion.id]
    : undefined;

  const totalQuestions =
    audit?.sections.reduce((sum, s) => sum + s.questions.length, 0) ?? 0;
  const answeredQuestions = Object.keys(responses).length;
  const progressPercentage =
    totalQuestions > 0 ? (answeredQuestions / totalQuestions) * 100 : 0;

  // Calculate score
  const calculateScore = () => {
    let totalWeight = 0;
    let achievedWeight = 0;

    audit?.sections.forEach((section) => {
      section.questions.forEach((question) => {
        const response = responses[question.id];
        if (!response) return;

        totalWeight += question.weight;

        if (response.response === "na") {
          totalWeight -= question.weight;
        } else if (
          question.type === "pass_fail" ||
          question.type === "yes_no"
        ) {
          if (response.response === "pass" || response.response === "yes") {
            achievedWeight += question.weight;
          }
        } else if (question.type === "score" || question.type === "scale_1_5") {
          const max = question.maxValue ?? 5;
          achievedWeight += (Number(response.response) / max) * question.weight;
        } else if (
          question.type === "rating" ||
          question.type === "scale_1_10"
        ) {
          const max = question.maxValue ?? 10;
          achievedWeight += (Number(response.response) / max) * question.weight;
        } else if (question.weight > 0) {
          achievedWeight += question.weight;
        }
      });
    });

    return totalWeight > 0
      ? Math.round((achievedWeight / totalWeight) * 100)
      : 0;
  };

  // Sync a single response to the API
  const syncResponseToApi = useCallback(
    async (questionId: string, updates: Partial<QuestionResponse>) => {
      if (!auditId) return;

      const numericRunId = parseInt(auditId, 10);
      const numericQuestionId = parseInt(questionId, 10);
      const existingResponseId = responseIdMapRef.current[questionId];

      const responseValue =
        updates.response != null ? String(updates.response) : undefined;
      const isNa = updates.response === "na";
      let score: number | undefined;
      let maxScore: number | undefined;

      if (updates.response === "pass" || updates.response === "yes") {
        score = 1;
        maxScore = 1;
      } else if (updates.response === "fail" || updates.response === "no") {
        score = 0;
        maxScore = 1;
      } else if (typeof updates.response === "number") {
        score = updates.response;
        maxScore = 5;
      }

      const payload: ResponsePayload = {
        question_id: numericQuestionId,
        response_value: responseValue,
        score,
        max_score: maxScore,
        notes: updates.notes,
        is_na: isNa,
      };

      try {
        setSaveStatus("saving");
        if (existingResponseId) {
          await auditsApi.updateResponse(existingResponseId, payload);
        } else {
          const created = await auditsApi.createResponse(numericRunId, payload);
          responseIdMapRef.current[questionId] = created.data.id;
        }
        setSaveStatus("saved");
        setTimeout(() => setSaveStatus("idle"), 2000);
      } catch (err) {
        console.error("Failed to sync response:", err);
        showToast("Failed to save response", "error");
        setSaveStatus("error");
      }
    },
    [auditId, showToast],
  );

  // Update local state + sync to API
  const updateResponse = (
    updates: Partial<Omit<QuestionResponse, "questionId" | "timestamp">>,
  ) => {
    if (!currentQuestion) return;
    const questionId = currentQuestion.id;

    setResponses((prev) => {
      const existing = prev[questionId];
      const updated: QuestionResponse = {
        ...(existing ??
          ({
            questionId,
            timestamp: new Date().toISOString(),
          } as QuestionResponse)),
        ...updates,
        questionId,
        timestamp: new Date().toISOString(),
      };
      return { ...prev, [questionId]: updated };
    });

    syncResponseToApi(questionId, updates);
  };

  // Navigation
  const goNext = () => {
    if (!currentSection || !audit) return;
    if (currentQuestionIndex < currentSection.questions.length - 1) {
      setCurrentQuestionIndex((prev) => prev + 1);
    } else if (currentSectionIndex < audit.sections.length - 1) {
      setCurrentSectionIndex((prev) => prev + 1);
      setCurrentQuestionIndex(0);
    } else {
      setShowSummary(true);
    }
    setShowGuidance(false);
  };

  const goPrev = () => {
    if (!audit) return;
    if (currentQuestionIndex > 0) {
      setCurrentQuestionIndex((prev) => prev - 1);
    } else if (currentSectionIndex > 0) {
      setCurrentSectionIndex((prev) => prev - 1);
      setCurrentQuestionIndex(
        audit.sections[currentSectionIndex - 1]!.questions.length - 1,
      );
    }
    setShowGuidance(false);
  };

  // Submit (complete) the audit
  const handleSubmitAudit = async () => {
    if (!auditId) return;
    setIsSubmitting(true);
    try {
      await auditsApi.completeRun(parseInt(auditId, 10));
      navigate("/audits");
    } catch (err) {
      console.error("Failed to complete audit:", err);
      showToast("Failed to submit audit", "error");
      setIsSubmitting(false);
    }
  };

  // Save draft
  const handleSaveDraft = async () => {
    if (!auditId) return;
    setIsSaving(true);
    try {
      await auditsApi.updateRun(parseInt(auditId, 10), {
        status: "in_progress",
      });
      navigate("/audits");
    } catch (err) {
      console.error("Failed to save draft:", err);
      showToast("Failed to save draft", "error");
    } finally {
      setIsSaving(false);
    }
  };

  // Render question input based on type
  const renderQuestionInput = () => {
    if (!currentQuestion) return null;
    const qType = currentQuestion.type;
    const opts = currentQuestion.options || [];
    const allowNa = currentQuestion.allowNa;

    const naButton = allowNa ? (
      <ResponseButton
        selected={currentResponse?.response === "na"}
        onClick={() => updateResponse({ response: "na" })}
        variant="neutral"
        icon={MinusCircle}
      >
        N/A
      </ResponseButton>
    ) : null;

    switch (qType) {
      case "pass_fail":
        return (
          <div className="flex gap-3">
            <ResponseButton
              selected={currentResponse?.response === "pass"}
              onClick={() => updateResponse({ response: "pass" })}
              variant="success"
              icon={CheckCircle2}
            >
              PASS
            </ResponseButton>
            <ResponseButton
              selected={currentResponse?.response === "fail"}
              onClick={() => updateResponse({ response: "fail" })}
              variant="danger"
              icon={XCircle}
            >
              FAIL
            </ResponseButton>
            {naButton}
          </div>
        );

      case "yes_no":
        return (
          <div className="flex gap-3">
            <ResponseButton
              selected={currentResponse?.response === "yes"}
              onClick={() => updateResponse({ response: "yes" })}
              variant="success"
              icon={CheckCircle2}
            >
              YES
            </ResponseButton>
            <ResponseButton
              selected={currentResponse?.response === "no"}
              onClick={() => updateResponse({ response: "no" })}
              variant="danger"
              icon={XCircle}
            >
              NO
            </ResponseButton>
            {naButton}
          </div>
        );

      case "score":
      case "scale_1_5":
        return (
          <ScaleInput
            value={currentResponse?.response as number | null}
            onChange={(val) => updateResponse({ response: val })}
            max={currentQuestion.maxValue ?? 5}
          />
        );

      case "rating":
      case "scale_1_10":
        return (
          <ScaleInput
            value={currentResponse?.response as number | null}
            onChange={(val) => updateResponse({ response: val })}
            max={currentQuestion.maxValue ?? 10}
          />
        );

      case "radio":
        return (
          <div className="space-y-2">
            {opts.map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => updateResponse({ response: opt.value })}
                className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl border-2 transition-all text-left ${
                  currentResponse?.response === opt.value
                    ? "border-primary bg-primary/10 text-foreground"
                    : "border-border bg-card text-muted-foreground hover:border-primary/50 hover:bg-surface"
                }`}
              >
                <div
                  className={`w-5 h-5 rounded-full border-2 flex items-center justify-center flex-shrink-0 ${
                    currentResponse?.response === opt.value
                      ? "border-primary"
                      : "border-muted-foreground"
                  }`}
                >
                  {currentResponse?.response === opt.value && (
                    <div className="w-2.5 h-2.5 rounded-full bg-primary" />
                  )}
                </div>
                <span className="font-medium">{opt.label}</span>
              </button>
            ))}
            {opts.length === 0 && (
              <p className="text-sm text-muted-foreground italic">
                No options configured for this question.
              </p>
            )}
          </div>
        );

      case "dropdown":
        return (
          <div className="space-y-2">
            <select
              value={(currentResponse?.response as string) || ""}
              onChange={(e) =>
                updateResponse({ response: e.target.value || null })
              }
              className="w-full px-4 py-3 bg-card border border-border rounded-xl text-foreground focus:outline-none focus:border-primary appearance-none cursor-pointer"
            >
              <option value="">Select an option...</option>
              {opts.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
            {opts.length === 0 && (
              <p className="text-sm text-muted-foreground italic">
                No options configured for this question.
              </p>
            )}
          </div>
        );

      case "checkbox":
        const selected = currentResponse?.response
          ? typeof currentResponse.response === "string"
            ? currentResponse.response.split(",").filter(Boolean)
            : Array.isArray(currentResponse.response)
              ? currentResponse.response
              : []
          : [];
        return (
          <div className="space-y-2">
            {opts.map((opt) => {
              const isChecked = selected.includes(opt.value);
              return (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => {
                    const newSelected = isChecked
                      ? selected.filter((v) => v !== opt.value)
                      : [...selected, opt.value];
                    updateResponse({ response: newSelected.join(",") });
                  }}
                  className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl border-2 transition-all text-left ${
                    isChecked
                      ? "border-primary bg-primary/10 text-foreground"
                      : "border-border bg-card text-muted-foreground hover:border-primary/50 hover:bg-surface"
                  }`}
                >
                  <div
                    className={`w-5 h-5 rounded border-2 flex items-center justify-center flex-shrink-0 ${
                      isChecked
                        ? "border-primary bg-primary"
                        : "border-muted-foreground"
                    }`}
                  >
                    {isChecked && (
                      <CheckCircle2 className="w-3 h-3 text-primary-foreground" />
                    )}
                  </div>
                  <span className="font-medium">{opt.label}</span>
                </button>
              );
            })}
            {opts.length === 0 && (
              <p className="text-sm text-muted-foreground italic">
                No options configured for this question.
              </p>
            )}
          </div>
        );

      case "text":
      case "text_short":
        return (
          <input
            type="text"
            value={(currentResponse?.response as string) || ""}
            onChange={(e) => updateResponse({ response: e.target.value })}
            placeholder="Enter your response..."
            className="w-full px-4 py-3 bg-card border border-border rounded-xl text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary"
          />
        );

      case "textarea":
      case "text_long":
        return (
          <textarea
            value={(currentResponse?.response as string) || ""}
            onChange={(e) => updateResponse({ response: e.target.value })}
            placeholder="Enter detailed response..."
            rows={4}
            className="w-full px-4 py-3 bg-card border border-border rounded-xl text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary resize-none"
          />
        );

      case "number":
      case "numeric":
        return (
          <input
            type="number"
            value={(currentResponse?.response as string) || ""}
            onChange={(e) => updateResponse({ response: e.target.value })}
            placeholder="Enter number..."
            min={currentQuestion.minValue}
            max={currentQuestion.maxValue}
            className="w-full px-4 py-3 bg-card border border-border rounded-xl text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary"
          />
        );

      case "date":
        return (
          <input
            type="date"
            value={(currentResponse?.response as string) || ""}
            onChange={(e) => updateResponse({ response: e.target.value })}
            className="w-full px-4 py-3 bg-card border border-border rounded-xl text-foreground focus:outline-none focus:border-primary"
          />
        );

      case "datetime":
        return (
          <input
            type="datetime-local"
            value={(currentResponse?.response as string) || ""}
            onChange={(e) => updateResponse({ response: e.target.value })}
            className="w-full px-4 py-3 bg-card border border-border rounded-xl text-foreground focus:outline-none focus:border-primary"
          />
        );

      case "photo":
        return (
          <PhotoCapture
            photos={currentResponse?.photos || []}
            onAdd={(photo) => {
              const newPhotos = [...(currentResponse?.photos || []), photo];
              updateResponse({
                photos: newPhotos,
                response: `${newPhotos.length} photo(s)`,
              });
            }}
            onRemove={(idx) => {
              const newPhotos = (currentResponse?.photos || []).filter(
                (_, i) => i !== idx,
              );
              updateResponse({
                photos: newPhotos,
                response:
                  newPhotos.length > 0 ? `${newPhotos.length} photo(s)` : null,
              });
            }}
          />
        );

      case "file":
        return (
          <div className="space-y-3">
            <input
              type="file"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) updateResponse({ response: file.name });
              }}
              className="w-full px-4 py-3 bg-card border border-border rounded-xl text-foreground file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:bg-primary file:text-primary-foreground file:font-medium file:cursor-pointer"
            />
            {currentResponse?.response && (
              <p className="text-sm text-muted-foreground">
                Selected: {currentResponse.response as string}
              </p>
            )}
          </div>
        );

      case "signature":
        return (
          <SignaturePad
            signature={currentResponse?.signature}
            onCapture={(sig) =>
              updateResponse({ signature: sig, response: "signed" })
            }
            onClear={() =>
              updateResponse({ signature: undefined, response: null })
            }
          />
        );

      default:
        return (
          <textarea
            value={(currentResponse?.response as string) || ""}
            onChange={(e) => updateResponse({ response: e.target.value })}
            placeholder="Enter response..."
            rows={3}
            className="w-full px-4 py-3 bg-card border border-border rounded-xl text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary resize-none"
          />
        );
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-background p-6">
        <CardSkeleton count={2} />
      </div>
    );
  }

  // Error state
  if (error || !audit) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-center max-w-md">
          <XCircle className="w-12 h-12 text-destructive mx-auto mb-4" />
          <h2 className="text-xl font-bold text-foreground mb-2">
            Failed to Load Audit
          </h2>
          <p className="text-muted-foreground mb-6">
            {error || "Audit not found."}
          </p>
          <div className="flex gap-3 justify-center">
            <button
              onClick={() => navigate("/audits")}
              className="px-6 py-2 bg-card border border-border text-foreground rounded-xl hover:bg-surface transition-colors"
            >
              Back to Audits
            </button>
            <button
              onClick={loadAuditRun}
              className="px-6 py-2 bg-primary text-primary-foreground rounded-xl hover:opacity-90 transition-opacity"
            >
              Retry
            </button>
          </div>
        </div>
      </div>
    );
  }

  // No sections/questions
  if (
    audit.sections.length === 0 ||
    audit.sections.every((s) => s.questions.length === 0)
  ) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-center max-w-md">
          <Info className="w-12 h-12 text-warning mx-auto mb-4" />
          <h2 className="text-xl font-bold text-foreground mb-2">
            No Questions Found
          </h2>
          <p className="text-muted-foreground mb-6">
            This audit template has no sections or questions configured. Please
            add questions in the Audit Builder first.
          </p>
          <button
            onClick={() => navigate("/audits")}
            className="px-6 py-2 bg-primary text-primary-foreground rounded-xl hover:opacity-90 transition-opacity"
          >
            Back to Audits
          </button>
        </div>
      </div>
    );
  }

  // Summary view
  if (showSummary) {
    const score = calculateScore();
    const passed = score >= 80;

    return (
      <div className="min-h-screen bg-background flex items-center justify-center p-4">
        <div className="max-w-lg w-full bg-card border border-border rounded-3xl p-8 text-center animate-fade-in">
          <div
            className={`w-32 h-32 mx-auto rounded-full flex items-center justify-center mb-6 ${
              passed
                ? "bg-gradient-to-br from-green-500 to-emerald-500"
                : "bg-gradient-to-br from-red-500 to-rose-500"
            }`}
          >
            <span className="text-4xl font-bold text-white">{score}%</span>
          </div>

          <h2
            className={`text-3xl font-bold mb-2 ${passed ? "text-success" : "text-destructive"}`}
          >
            {passed ? "AUDIT PASSED" : "AUDIT FAILED"}
          </h2>
          <p className="text-muted-foreground mb-8">
            {audit.templateName} {audit.location ? `- ${audit.location}` : ""}
          </p>

          <div className="grid grid-cols-3 gap-4 mb-8">
            <div className="bg-surface rounded-xl p-4 border border-border">
              <p className="text-2xl font-bold text-foreground">
                {answeredQuestions}
              </p>
              <p className="text-xs text-muted-foreground">Answered</p>
            </div>
            <div className="bg-surface rounded-xl p-4 border border-border">
              <p className="text-2xl font-bold text-foreground">
                {formatTime(elapsedTime)}
              </p>
              <p className="text-xs text-muted-foreground">Duration</p>
            </div>
            <div className="bg-surface rounded-xl p-4 border border-border">
              <p className="text-2xl font-bold text-foreground">
                {
                  Object.values(responses).filter(
                    (r) => r.photos && r.photos.length > 0,
                  ).length
                }
              </p>
              <p className="text-xs text-muted-foreground">Photos</p>
            </div>
          </div>

          {/* Findings Summary */}
          <div className="text-left mb-8">
            <h3 className="text-lg font-semibold text-foreground mb-3">
              Findings
            </h3>
            <div className="space-y-2">
              {Object.values(responses)
                .filter((r) => r.response === "fail" || r.response === "no")
                .map((r, idx) => {
                  const question = audit.sections
                    .flatMap((s) => s.questions)
                    .find((q) => q.id === r.questionId);
                  return (
                    <div
                      key={idx}
                      className="flex items-start gap-2 p-3 bg-red-500/10 border border-red-500/20 rounded-lg"
                    >
                      <XCircle className="w-5 h-5 text-destructive mt-0.5 flex-shrink-0" />
                      <p className="text-sm text-destructive">
                        {question?.text}
                      </p>
                    </div>
                  );
                })}
              {Object.values(responses).filter(
                (r) => r.response === "fail" || r.response === "no",
              ).length === 0 && (
                <p className="text-sm text-muted-foreground">No failed items</p>
              )}
            </div>
          </div>

          <div className="flex gap-3">
            <button
              onClick={() => setShowSummary(false)}
              className="flex-1 py-3 bg-card border border-border text-foreground rounded-xl hover:bg-surface transition-colors"
            >
              Review Answers
            </button>
            <button
              onClick={handleSubmitAudit}
              disabled={isSubmitting}
              className="flex-1 py-3 bg-gradient-to-r from-purple-500 to-pink-500 text-white font-semibold rounded-xl hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {isSubmitting ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <Send className="w-5 h-5" />
              )}
              {isSubmitting ? "Submitting..." : "Submit Audit"}
            </button>
          </div>
        </div>
        <ToastContainer toasts={toasts} onDismiss={dismissToast} />
      </div>
    );
  }

  if (!currentSection || !currentQuestion) return null;

  return (
    <div className="min-h-screen bg-background flex flex-col">
      {/* Header */}
      <header className="sticky top-0 z-40 bg-card/80 backdrop-blur-xl border-b border-border">
        <div className="px-4 py-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <button
                onClick={() => navigate("/audits")}
                className="p-2 hover:bg-surface rounded-lg transition-colors"
              >
                <ArrowLeft className="w-5 h-5 text-muted-foreground" />
              </button>
              <div>
                <h1 className="text-lg font-bold text-foreground">
                  {audit.templateName}
                </h1>
                <p className="text-xs text-muted-foreground">
                  {audit.asset} {audit.location ? `• ${audit.location}` : ""}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-3">
              {/* Save Status */}
              {saveStatus === "saving" && (
                <span className="text-xs text-muted-foreground flex items-center gap-1">
                  <Loader2 className="w-3 h-3 animate-spin" /> Saving...
                </span>
              )}
              {saveStatus === "saved" && (
                <span className="text-xs text-success flex items-center gap-1">
                  <CheckCircle2 className="w-3 h-3" /> Saved
                </span>
              )}
              {saveStatus === "error" && (
                <span className="text-xs text-destructive flex items-center gap-1">
                  <XCircle className="w-3 h-3" /> Error
                </span>
              )}

              {/* Timer */}
              <div className="flex items-center gap-2 px-3 py-1.5 bg-surface rounded-lg border border-border">
                <Timer className="w-4 h-4 text-muted-foreground" />
                <span className="text-sm font-mono text-foreground">
                  {formatTime(elapsedTime)}
                </span>
              </div>

              {/* Pause/Play */}
              <button
                onClick={() => setIsPaused(!isPaused)}
                className={`p-2 rounded-lg transition-colors ${
                  isPaused
                    ? "bg-amber-500/20 text-amber-400"
                    : "bg-surface text-muted-foreground hover:text-foreground"
                }`}
              >
                {isPaused ? (
                  <Play className="w-5 h-5" />
                ) : (
                  <Pause className="w-5 h-5" />
                )}
              </button>

              {/* Save Draft */}
              <button
                onClick={handleSaveDraft}
                disabled={isSaving}
                className="flex items-center gap-2 px-4 py-2 bg-surface text-foreground rounded-lg hover:bg-card border border-border"
              >
                {isSaving ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Save className="w-4 h-4" />
                )}
                Save
              </button>
            </div>
          </div>

          {/* Progress Bar */}
          <div className="mt-3">
            <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
              <span>
                Progress: {answeredQuestions}/{totalQuestions} questions
              </span>
              <span>{Math.round(progressPercentage)}%</span>
            </div>
            <div className="h-2 bg-surface rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-purple-500 to-pink-500 transition-all duration-300"
                style={{ width: `${progressPercentage}%` }}
              />
            </div>
          </div>
        </div>
      </header>

      {/* Section Navigation */}
      <div className="bg-card/50 border-b border-border overflow-x-auto">
        <div className="flex px-4 py-2 gap-2">
          {audit.sections.map((section, idx) => {
            const sectionAnswered = section.questions.filter(
              (q) => responses[q.id],
            ).length;
            const isComplete = sectionAnswered === section.questions.length;
            const isCurrent = idx === currentSectionIndex;

            return (
              <button
                key={section.id}
                onClick={() => {
                  setCurrentSectionIndex(idx);
                  setCurrentQuestionIndex(0);
                  setShowGuidance(false);
                }}
                className={`flex items-center gap-2 px-4 py-2 rounded-xl whitespace-nowrap transition-all ${
                  isCurrent
                    ? `bg-gradient-to-r ${section.color} text-white`
                    : isComplete
                      ? "bg-green-500/20 text-green-400 border border-green-500/30"
                      : "bg-surface text-muted-foreground hover:bg-card border border-border"
                }`}
              >
                {isComplete ? (
                  <CheckCheck className="w-4 h-4" />
                ) : (
                  <span className="w-5 h-5 rounded-full bg-surface text-xs flex items-center justify-center border border-border">
                    {idx + 1}
                  </span>
                )}
                <span className="text-sm font-medium">{section.title}</span>
                <span className="text-xs opacity-75">
                  {sectionAnswered}/{section.questions.length}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Main Content */}
      <main className="flex-1 overflow-y-auto">
        <div className="max-w-2xl mx-auto p-4 pb-32">
          {/* Question Card */}
          <div className="bg-card border border-border rounded-3xl overflow-hidden">
            {/* Question Header */}
            <div className={`bg-gradient-to-r ${currentSection.color} p-0.5`}>
              <div className="bg-card p-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-muted-foreground">
                      {currentSection.title} • Question{" "}
                      {currentQuestionIndex + 1} of{" "}
                      {currentSection.questions.length}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    {currentQuestion.riskLevel && (
                      <span
                        className={`px-2 py-1 text-xs rounded ${
                          currentQuestion.riskLevel === "critical"
                            ? "bg-red-500/20 text-red-400"
                            : currentQuestion.riskLevel === "high"
                              ? "bg-orange-500/20 text-orange-400"
                              : currentQuestion.riskLevel === "medium"
                                ? "bg-amber-500/20 text-amber-400"
                                : "bg-green-500/20 text-green-400"
                        }`}
                      >
                        {currentQuestion.riskLevel} risk
                      </span>
                    )}
                    {currentQuestion.required && (
                      <span className="px-2 py-1 bg-purple-500/20 text-purple-400 text-xs rounded">
                        Required
                      </span>
                    )}
                  </div>
                </div>
              </div>
            </div>

            {/* Question Content */}
            <div className="p-6 space-y-6">
              <div>
                <h2 className="text-xl font-semibold text-foreground mb-2">
                  {currentQuestion.text}
                </h2>
                {currentQuestion.description && (
                  <p className="text-sm text-muted-foreground">
                    {currentQuestion.description}
                  </p>
                )}
              </div>

              {/* Guidance */}
              {currentQuestion.guidance && (
                <div>
                  <button
                    onClick={() => setShowGuidance(!showGuidance)}
                    className="flex items-center gap-2 text-sm text-purple-400 hover:text-purple-300"
                  >
                    <Info className="w-4 h-4" />
                    Auditor Guidance
                    {showGuidance ? (
                      <ChevronUp className="w-4 h-4" />
                    ) : (
                      <ChevronDown className="w-4 h-4" />
                    )}
                  </button>
                  {showGuidance && (
                    <div className="mt-2 p-3 bg-purple-500/10 border border-purple-500/20 rounded-lg">
                      <p className="text-sm text-purple-300">
                        {currentQuestion.guidance}
                      </p>
                    </div>
                  )}
                </div>
              )}

              {/* Response Input */}
              <div>{renderQuestionInput()}</div>

              {/* Evidence Required */}
              {currentQuestion.evidenceRequired && (
                <div className="pt-4 border-t border-border">
                  <div className="flex items-center gap-2 mb-3">
                    <Camera className="w-4 h-4 text-cyan-400" />
                    <span className="text-sm font-medium text-foreground">
                      Photo Evidence Required
                    </span>
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
                        photos:
                          currentResponse?.photos?.filter(
                            (_, i) => i !== idx,
                          ) || [],
                      });
                    }}
                  />
                </div>
              )}

              {/* Notes */}
              <div className="pt-4 border-t border-border">
                <div className="flex items-center gap-2 mb-3">
                  <MessageSquare className="w-4 h-4 text-muted-foreground" />
                  <span className="text-sm font-medium text-foreground">
                    Additional Notes
                  </span>
                </div>
                <textarea
                  value={currentResponse?.notes || ""}
                  onChange={(e) => updateResponse({ notes: e.target.value })}
                  placeholder="Add any additional observations..."
                  rows={2}
                  className="w-full px-4 py-3 bg-card border border-border rounded-xl text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary resize-none text-sm"
                />
              </div>

              {/* Flag Issue */}
              <button
                onClick={() =>
                  updateResponse({ flagged: !currentResponse?.flagged })
                }
                className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
                  currentResponse?.flagged
                    ? "bg-red-500/20 text-red-400 border border-red-500/30"
                    : "bg-surface text-muted-foreground hover:text-foreground border border-border"
                }`}
              >
                <Flag
                  className={`w-4 h-4 ${currentResponse?.flagged ? "fill-current" : ""}`}
                />
                {currentResponse?.flagged
                  ? "Issue Flagged"
                  : "Flag for Follow-up"}
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
            className="flex items-center gap-2 px-6 py-3 bg-surface text-foreground rounded-xl hover:bg-card disabled:opacity-50 disabled:cursor-not-allowed transition-colors border border-border"
          >
            <ArrowLeft className="w-5 h-5" />
            Previous
          </button>

          {/* Quick Jump */}
          <div className="flex items-center gap-1">
            {currentSection.questions.map((_, idx) => (
              <button
                key={idx}
                onClick={() => {
                  setCurrentQuestionIndex(idx);
                  setShowGuidance(false);
                }}
                className={`w-3 h-3 rounded-full transition-all ${
                  idx === currentQuestionIndex
                    ? "bg-purple-500 w-6"
                    : responses[currentSection.questions[idx]!.id]
                      ? "bg-green-500"
                      : "bg-surface border border-border hover:bg-card"
                }`}
              />
            ))}
          </div>

          <button
            onClick={goNext}
            className="flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-purple-500 to-pink-500 text-white font-semibold rounded-xl hover:opacity-90 transition-opacity"
          >
            {currentSectionIndex === audit.sections.length - 1 &&
            currentQuestionIndex === currentSection.questions.length - 1
              ? "Finish"
              : "Next"}
            <ArrowRight className="w-5 h-5" />
          </button>
        </div>
      </footer>
      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}
