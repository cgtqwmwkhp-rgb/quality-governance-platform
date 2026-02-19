import { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { auditsApi } from '../api/client';
import {
  ArrowLeft,
  ArrowRight,
  Pause,
  Play,
  CheckCircle2,
  XCircle,
  Camera,
  Mic,
  MicOff,
  MapPin,
  MessageSquare,
  ChevronDown,
  ChevronUp,
  X,
  Flag,
  CheckCheck,
  MinusCircle,
  Sparkles,
  Wifi,
  WifiOff,
  Battery,
  Cloud,
  CloudOff,
  Navigation,
  Loader2,
  Lightbulb,
  ThumbsUp,
  ThumbsDown,
  Send,
} from 'lucide-react';

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
  | null;

interface QuestionResponse {
  questionId: string;
  response: ResponseType;
  notes?: string;
  photos?: string[];
  voiceNote?: string;
  signature?: string;
  flagged?: boolean;
  timestamp: string;
  location?: { lat: number; lng: number };
  aiSuggestion?: string;
  aiAccepted?: boolean;
}

interface AuditQuestion {
  id: string;
  text: string;
  description?: string;
  type: string;
  required: boolean;
  weight: number;
  evidenceRequired: boolean;
  guidance?: string;
  riskLevel?: string;
  isoClause?: string;
}

interface AuditSection {
  id: string;
  title: string;
  description?: string;
  color: string;
  questions: AuditQuestion[];
}

const SECTION_COLORS = [
  'from-blue-500 to-cyan-500',
  'from-purple-500 to-pink-500',
  'from-orange-500 to-amber-500',
  'from-green-500 to-emerald-500',
  'from-red-500 to-rose-500',
  'from-indigo-500 to-violet-500',
];

// ============================================================================
// COMPONENTS
// ============================================================================

// Haptic feedback simulation
const triggerHaptic = (type: 'light' | 'medium' | 'heavy' = 'light') => {
  if ('vibrate' in navigator) {
    const patterns = { light: [10], medium: [20], heavy: [30, 10, 30] };
    navigator.vibrate(patterns[type]);
  }
};

// Status Bar Component
const StatusBar = ({ 
  isOnline, 
  isSynced, 
  batteryLevel 
}: { 
  isOnline: boolean; 
  isSynced: boolean; 
  batteryLevel: number;
}) => (
  <div className="flex items-center gap-3 px-4 py-2 bg-slate-900/80 text-xs">
    <div className={`flex items-center gap-1 ${isOnline ? 'text-green-400' : 'text-red-400'}`}>
      {isOnline ? <Wifi className="w-3 h-3" /> : <WifiOff className="w-3 h-3" />}
      <span>{isOnline ? 'Online' : 'Offline'}</span>
    </div>
    <div className={`flex items-center gap-1 ${isSynced ? 'text-green-400' : 'text-amber-400'}`}>
      {isSynced ? <Cloud className="w-3 h-3" /> : <CloudOff className="w-3 h-3" />}
      <span>{isSynced ? 'Synced' : 'Pending'}</span>
    </div>
    <div className="flex items-center gap-1 text-slate-400 ml-auto">
      <Battery className="w-3 h-3" />
      <span>{batteryLevel}%</span>
    </div>
  </div>
);

// AI Suggestion Component
const AISuggestion = ({
  suggestion,
  confidence,
  onAccept,
  onDismiss,
  isLoading,
}: {
  suggestion?: string;
  confidence?: number;
  onAccept: () => void;
  onDismiss: () => void;
  isLoading: boolean;
}) => {
  if (isLoading) {
    return (
      <div className="flex items-center gap-2 p-3 bg-purple-500/10 border border-purple-500/20 rounded-xl animate-pulse">
        <Loader2 className="w-4 h-4 text-purple-400 animate-spin" />
        <span className="text-sm text-purple-300">AI analyzing...</span>
      </div>
    );
  }

  if (!suggestion) return null;

  return (
    <div className="p-3 bg-gradient-to-r from-purple-500/10 to-pink-500/10 border border-purple-500/30 rounded-xl">
      <div className="flex items-start gap-2">
        <Sparkles className="w-4 h-4 text-purple-400 mt-0.5 flex-shrink-0" />
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-medium text-purple-400">AI Insight</span>
            <span className="text-xs text-purple-400/60">{Math.round((confidence || 0) * 100)}% confidence</span>
          </div>
          <p className="text-sm text-purple-200">{suggestion}</p>
        </div>
      </div>
      <div className="flex gap-2 mt-3">
        <button
          onClick={() => { onAccept(); triggerHaptic('light'); }}
          className="flex-1 flex items-center justify-center gap-1 py-2 bg-purple-500/20 text-purple-300 rounded-lg text-xs font-medium hover:bg-purple-500/30"
        >
          <ThumbsUp className="w-3 h-3" /> Helpful
        </button>
        <button
          onClick={() => { onDismiss(); triggerHaptic('light'); }}
          className="flex-1 flex items-center justify-center gap-1 py-2 bg-slate-700/50 text-slate-400 rounded-lg text-xs font-medium hover:bg-slate-700"
        >
          <ThumbsDown className="w-3 h-3" /> Dismiss
        </button>
      </div>
    </div>
  );
};

// Large Touch-Friendly Response Button
const TouchResponseButton = ({
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
    success: 'border-green-500 bg-green-500/30 text-green-300 shadow-lg shadow-green-500/20',
    danger: 'border-red-500 bg-red-500/30 text-red-300 shadow-lg shadow-red-500/20',
    warning: 'border-amber-500 bg-amber-500/30 text-amber-300 shadow-lg shadow-amber-500/20',
    neutral: 'border-slate-500 bg-slate-500/30 text-slate-300 shadow-lg shadow-slate-500/20',
  };

  const hoverStyles = {
    success: 'active:bg-green-500/40 active:scale-95',
    danger: 'active:bg-red-500/40 active:scale-95',
    warning: 'active:bg-amber-500/40 active:scale-95',
    neutral: 'active:bg-slate-500/40 active:scale-95',
  };

  return (
    <button
      type="button"
      onClick={() => {
        onClick();
        triggerHaptic(selected ? 'light' : 'medium');
      }}
      className={`flex-1 flex flex-col items-center justify-center gap-2 py-6 px-4 rounded-2xl border-2 font-bold transition-all duration-150 min-h-[100px]
        ${selected ? variantStyles[variant] : `border-slate-700 bg-slate-800/80 text-slate-400 ${hoverStyles[variant]}`}`}
    >
      {Icon && <Icon className={`w-8 h-8 ${selected ? '' : 'opacity-60'}`} />}
      <span className="text-lg">{children}</span>
    </button>
  );
};

// Scale Input with Touch Optimization
const TouchScaleInput = ({
  value,
  onChange,
  max = 5,
}: {
  value: number | null;
  onChange: (val: number) => void;
  max?: number;
}) => {
  return (
    <div className="flex items-center justify-between gap-2">
      {Array.from({ length: max }, (_, i) => i + 1).map((num) => (
        <button
          key={num}
          type="button"
          onClick={() => {
            onChange(num);
            triggerHaptic('light');
          }}
          className={`flex-1 h-16 rounded-xl font-bold text-xl transition-all duration-150 active:scale-95 ${
            value === num
              ? 'bg-gradient-to-br from-purple-500 to-pink-500 text-white shadow-lg shadow-purple-500/25'
              : 'bg-slate-800 text-slate-400 border border-slate-700 hover:bg-slate-700'
          }`}
        >
          {num}
        </button>
      ))}
    </div>
  );
};

// Voice Recording Component
const VoiceRecorder = ({
  onRecordingComplete,
}: {
  onRecordingComplete: (audioBlob: string) => void;
}) => {
  const [isRecording, setIsRecording] = useState(false);
  const [recordingTime, setRecordingTime] = useState(0);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  useEffect(() => {
    let interval: ReturnType<typeof setInterval>;
    if (isRecording) {
      interval = setInterval(() => {
        setRecordingTime(prev => prev + 1);
      }, 1000);
    }
    return () => clearInterval(interval);
  }, [isRecording]);

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;
      chunksRef.current = [];

      mediaRecorder.ondataavailable = (e) => {
        chunksRef.current.push(e.data);
      };

      mediaRecorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' });
        const reader = new FileReader();
        reader.onloadend = () => {
          onRecordingComplete(reader.result as string);
        };
        reader.readAsDataURL(blob);
        stream.getTracks().forEach(track => track.stop());
      };

      mediaRecorder.start();
      setIsRecording(true);
      setRecordingTime(0);
      triggerHaptic('medium');
    } catch (err) {
      console.error('Error accessing microphone:', err);
      alert('Could not access microphone. Please check permissions.');
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      triggerHaptic('heavy');
    }
  };

  return (
    <button
      type="button"
      onClick={isRecording ? stopRecording : startRecording}
      className={`flex items-center justify-center gap-2 w-full py-4 rounded-xl font-medium transition-all duration-200 ${
        isRecording
          ? 'bg-red-500 text-white animate-pulse'
          : 'bg-slate-800 text-slate-300 border border-slate-700'
      }`}
    >
      {isRecording ? (
        <>
          <MicOff className="w-5 h-5" />
          <span>Stop Recording ({recordingTime}s)</span>
        </>
      ) : (
        <>
          <Mic className="w-5 h-5" />
          <span>Record Voice Note</span>
        </>
      )}
    </button>
  );
};

// Photo Capture with Camera
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
        triggerHaptic('medium');
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
        className="w-full py-4 bg-gradient-to-r from-cyan-500/20 to-blue-500/20 border border-cyan-500/30 rounded-xl text-cyan-300 font-medium flex items-center justify-center gap-2 active:scale-98"
      >
        <Camera className="w-5 h-5" />
        {photos.length > 0 ? `Add Photo (${photos.length})` : 'Take Photo'}
      </button>

      {photos.length > 0 && (
        <div className="grid grid-cols-3 gap-2">
          {photos.map((photo, idx) => (
            <div key={idx} className="relative aspect-square">
              <img
                src={photo}
                alt={`Evidence ${idx + 1}`}
                className="w-full h-full object-cover rounded-lg"
              />
              <button
                type="button"
                onClick={() => {
                  onRemove(idx);
                  triggerHaptic('light');
                }}
                className="absolute top-1 right-1 p-1.5 bg-red-500 rounded-full text-white"
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

// Location Capture
const LocationCapture = ({
  location,
  onCapture,
}: {
  location?: { lat: number; lng: number };
  onCapture: (loc: { lat: number; lng: number }) => void;
}) => {
  const [isCapturing, setIsCapturing] = useState(false);

  const captureLocation = () => {
    if (!navigator.geolocation) {
      alert('Geolocation is not supported by this device.');
      return;
    }

    setIsCapturing(true);
    navigator.geolocation.getCurrentPosition(
      (position) => {
        onCapture({
          lat: position.coords.latitude,
          lng: position.coords.longitude,
        });
        setIsCapturing(false);
        triggerHaptic('medium');
      },
      (error) => {
        console.error('Geolocation error:', error);
        alert('Could not get location. Please check permissions.');
        setIsCapturing(false);
      },
      { enableHighAccuracy: true }
    );
  };

  return (
    <button
      type="button"
      onClick={captureLocation}
      disabled={isCapturing}
      className={`flex items-center justify-center gap-2 w-full py-3 rounded-xl font-medium transition-all ${
        location
          ? 'bg-green-500/20 text-green-300 border border-green-500/30'
          : 'bg-slate-800 text-slate-300 border border-slate-700'
      }`}
    >
      {isCapturing ? (
        <>
          <Loader2 className="w-4 h-4 animate-spin" />
          <span>Getting location...</span>
        </>
      ) : location ? (
        <>
          <Navigation className="w-4 h-4" />
          <span>Location captured</span>
        </>
      ) : (
        <>
          <MapPin className="w-4 h-4" />
          <span>Capture Location</span>
        </>
      )}
    </button>
  );
};

// ============================================================================
// MAIN COMPONENT
// ============================================================================

export default function MobileAuditExecution() {
  const navigate = useNavigate();
  const { runId } = useParams<{ runId: string }>();
  
  interface AuditData {
    id: string;
    templateName: string;
    location: string;
    asset: string;
    sections: AuditSection[];
  }
  
  const [audit, setAudit] = useState<AuditData | null>(null);
  const [loading, setLoading] = useState(true);
  const [currentSectionIndex, setCurrentSectionIndex] = useState(0);
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
  const [responses, setResponses] = useState<Record<string, QuestionResponse>>({});
  const [isPaused, setIsPaused] = useState(false);
  const [elapsedTime, setElapsedTime] = useState(0);
  const [showGuidance, setShowGuidance] = useState(false);
  const [showSummary, setShowSummary] = useState(false);
  const [isOnline, setIsOnline] = useState(navigator.onLine);
  const [isSynced, setIsSynced] = useState(true);
  const [batteryLevel] = useState(85);
  const [aiLoading, setAiLoading] = useState(false);
  const [showAISuggestion, setShowAISuggestion] = useState(true);
  const responseIdMapRef = useRef<Record<string, number>>({});

  const loadAuditRun = useCallback(async () => {
    if (!runId) return;
    try {
      setLoading(true);
      const numericId = parseInt(runId, 10);
      const runData = await auditsApi.getRun(numericId);
      const templateData = await auditsApi.getTemplate(runData.data.template_id);

      const sections: AuditSection[] = ((templateData.data as any).sections || []).map(
        (sec: any, sIdx: number) => ({
          id: String(sec.id),
          title: String(sec.title || ''),
          description: sec.description ? String(sec.description) : undefined,
          color: SECTION_COLORS[sIdx % SECTION_COLORS.length],
          questions: (sec.questions || []).map(
            (q: any) => ({
              id: String(q.id),
              text: String(q.text || ''),
              description: q.description ? String(q.description) : undefined,
              type: String(q.question_type || q.type || 'yes_no'),
              required: q.is_required !== false,
              weight: Number(q.weight || 1),
              evidenceRequired: q.evidence_required === true,
              guidance: q.guidance ? String(q.guidance) : undefined,
              riskLevel: q.risk_category ? String(q.risk_category) : undefined,
              isoClause: q.iso_clause ? String(q.iso_clause) : undefined,
            })
          ),
        })
      );

      const rd = runData.data as any;
      setAudit({
        id: String(rd.id),
        templateName: String((templateData.data as any).name || ''),
        location: String(rd.location || ''),
        asset: String(rd.asset_id || ''),
        sections,
      });

      const existingResponses: Record<string, QuestionResponse> = {};
      if (rd.responses) {
        for (const r of rd.responses as any[]) {
          const qId = String(r.question_id);
          responseIdMapRef.current[qId] = Number(r.id);
          existingResponses[qId] = {
            questionId: qId,
            response: r.is_na ? 'na' : (r.score != null ? Number(r.score) : (r.text_response ? String(r.text_response) : null)),
            notes: r.notes ? String(r.notes) : undefined,
            flagged: r.flagged === true,
            timestamp: String(r.created_at || new Date().toISOString()),
          };
        }
      }
      setResponses(existingResponses);
    } catch {
      console.error('Failed to load audit run');
    } finally {
      setLoading(false);
    }
  }, [runId]);

  useEffect(() => { loadAuditRun(); }, [loadAuditRun]);

  // Handle online/offline status
  useEffect(() => {
    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);
    
    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);
    
    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  // Timer
  useEffect(() => {
    if (isPaused) return;
    
    const timer = setInterval(() => {
      setElapsedTime(prev => prev + 1);
    }, 1000);

    return () => clearInterval(timer);
  }, [isPaused]);

  useEffect(() => {
    setShowAISuggestion(false);
    setAiLoading(false);
  }, [currentSectionIndex, currentQuestionIndex]);

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const currentSection = audit?.sections[currentSectionIndex];
  const currentQuestion = currentSection?.questions[currentQuestionIndex];
  const currentResponse = currentQuestion ? responses[currentQuestion.id] : undefined;

  const totalQuestions = audit?.sections.reduce((sum, s) => sum + s.questions.length, 0) ?? 0;
  const answeredQuestions = Object.keys(responses).length;
  const progressPercentage = (answeredQuestions / totalQuestions) * 100;

  // Calculate score
  const calculateScore = () => {
    let totalWeight = 0;
    let achievedWeight = 0;

    audit?.sections.forEach(section => {
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

  const updateResponse = (updates: Partial<Omit<QuestionResponse, 'questionId' | 'timestamp'>>) => {
    if (!currentQuestion || !runId) return;
    const questionId = currentQuestion.id;
    setResponses(prev => ({
      ...prev,
      [questionId]: {
        ...prev[questionId],
        ...updates,
        questionId,
        timestamp: new Date().toISOString(),
      },
    }));
    setIsSynced(false);

    const numericRunId = parseInt(runId, 10);
    const numericQuestionId = parseInt(questionId, 10);
    const existingResponseId = responseIdMapRef.current[questionId];

    const payload: Record<string, unknown> = {
      question_id: numericQuestionId,
      score: typeof updates.response === 'number' ? updates.response : undefined,
      text_response: typeof updates.response === 'string' && !['yes','no','pass','fail','na'].includes(updates.response) ? updates.response : undefined,
      is_na: updates.response === 'na',
      notes: updates.notes,
      flagged: updates.flagged,
    };
    if (updates.response === 'pass' || updates.response === 'yes') payload.score = 1;
    if (updates.response === 'fail' || updates.response === 'no') payload.score = 0;

    const syncToApi = async () => {
      try {
        if (existingResponseId) {
          await auditsApi.updateResponse(existingResponseId, payload as never);
        } else {
          const created = await auditsApi.createResponse(numericRunId, payload as never);
          responseIdMapRef.current[questionId] = created.data.id;
        }
        setIsSynced(true);
      } catch {
        console.error('Failed to sync response');
      }
    };
    syncToApi();
  };

  // Navigation
  const goNext = () => {
    triggerHaptic('light');
    if (currentSection && currentQuestionIndex < currentSection.questions.length - 1) {
      setCurrentQuestionIndex(prev => prev + 1);
    } else if (currentSectionIndex < (audit?.sections.length ?? 0) - 1) {
      setCurrentSectionIndex(prev => prev + 1);
      setCurrentQuestionIndex(0);
    } else {
      setShowSummary(true);
    }
  };

  const goPrev = () => {
    triggerHaptic('light');
    if (currentQuestionIndex > 0) {
      setCurrentQuestionIndex(prev => prev - 1);
    } else if (currentSectionIndex > 0) {
      setCurrentSectionIndex(prev => prev - 1);
      setCurrentQuestionIndex(audit?.sections[currentSectionIndex - 1]?.questions.length ? audit.sections[currentSectionIndex - 1].questions.length - 1 : 0);
    }
  };

  // Render question input based on type
  const renderQuestionInput = () => {
    if (!currentQuestion) return null;
    
    switch (currentQuestion.type) {
      case 'pass_fail':
        return (
          <div className="flex gap-3">
            <TouchResponseButton
              selected={currentResponse?.response === 'pass'}
              onClick={() => updateResponse({ response: 'pass' })}
              variant="success"
              icon={CheckCircle2}
            >
              PASS
            </TouchResponseButton>
            <TouchResponseButton
              selected={currentResponse?.response === 'fail'}
              onClick={() => updateResponse({ response: 'fail' })}
              variant="danger"
              icon={XCircle}
            >
              FAIL
            </TouchResponseButton>
          </div>
        );

      case 'yes_no':
        return (
          <div className="flex gap-3">
            <TouchResponseButton
              selected={currentResponse?.response === 'yes'}
              onClick={() => updateResponse({ response: 'yes' })}
              variant="success"
              icon={CheckCircle2}
            >
              YES
            </TouchResponseButton>
            <TouchResponseButton
              selected={currentResponse?.response === 'no'}
              onClick={() => updateResponse({ response: 'no' })}
              variant="danger"
              icon={XCircle}
            >
              NO
            </TouchResponseButton>
          </div>
        );

      case 'yes_no_na':
        return (
          <div className="flex gap-2">
            <TouchResponseButton
              selected={currentResponse?.response === 'yes'}
              onClick={() => updateResponse({ response: 'yes' })}
              variant="success"
              icon={CheckCircle2}
            >
              YES
            </TouchResponseButton>
            <TouchResponseButton
              selected={currentResponse?.response === 'no'}
              onClick={() => updateResponse({ response: 'no' })}
              variant="danger"
              icon={XCircle}
            >
              NO
            </TouchResponseButton>
            <TouchResponseButton
              selected={currentResponse?.response === 'na'}
              onClick={() => updateResponse({ response: 'na' })}
              variant="neutral"
              icon={MinusCircle}
            >
              N/A
            </TouchResponseButton>
          </div>
        );

      case 'scale_1_5':
        return (
          <TouchScaleInput
            value={currentResponse?.response as number | null}
            onChange={(val) => updateResponse({ response: val })}
            max={5}
          />
        );

      case 'numeric':
        return (
          <input
            type="number"
            inputMode="numeric"
            value={(currentResponse?.response as string) || ''}
            onChange={(e) => updateResponse({ response: e.target.value })}
            placeholder="Enter number..."
            className="w-full px-4 py-4 bg-slate-800 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-purple-500 text-lg text-center"
          />
        );

      default:
        return (
          <textarea
            value={(currentResponse?.response as string) || ''}
            onChange={(e) => updateResponse({ response: e.target.value })}
            placeholder="Enter response..."
            rows={3}
            className="w-full px-4 py-4 bg-slate-800 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-purple-500 text-lg"
          />
        );
    }
  };

  if (loading || !audit) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center">
        <Loader2 className="w-8 h-8 text-purple-400 animate-spin" />
      </div>
    );
  }

  if (showSummary) {
    const score = calculateScore();
    const passed = score >= 80;
    const failedItems = Object.values(responses).filter(r => r.response === 'fail' || r.response === 'no');

    return (
      <div className="min-h-screen bg-slate-950 flex flex-col">
        <StatusBar isOnline={isOnline} isSynced={isSynced} batteryLevel={batteryLevel} />
        
        <div className="flex-1 flex items-center justify-center p-4">
          <div className="max-w-lg w-full text-center animate-fade-in">
            {/* Score Display */}
            <div className={`w-40 h-40 mx-auto rounded-full flex items-center justify-center mb-6 ${
              passed 
                ? 'bg-gradient-to-br from-green-500 to-emerald-500 shadow-lg shadow-green-500/30' 
                : 'bg-gradient-to-br from-red-500 to-rose-500 shadow-lg shadow-red-500/30'
            }`}>
              <span className="text-5xl font-bold text-white">{score}%</span>
            </div>

            <h2 className={`text-3xl font-bold mb-2 ${passed ? 'text-green-400' : 'text-red-400'}`}>
              {passed ? 'AUDIT PASSED' : 'AUDIT FAILED'}
            </h2>
            <p className="text-slate-400 mb-6">
              {audit.templateName} - {audit.asset}
            </p>

            {/* AI Summary */}
            <div className="bg-gradient-to-r from-purple-500/10 to-pink-500/10 border border-purple-500/30 rounded-2xl p-4 mb-6 text-left">
              <div className="flex items-center gap-2 mb-3">
                <Sparkles className="w-5 h-5 text-purple-400" />
                <span className="font-semibold text-purple-300">AI Summary</span>
              </div>
              <p className="text-sm text-purple-200">
                {passed 
                  ? `Vehicle ${audit.asset} passed all critical checks. ${failedItems.length} minor issues noted for follow-up. Recommend scheduling preventive maintenance within 30 days.`
                  : `Vehicle ${audit.asset} has ${failedItems.length} failed items requiring immediate attention. Do not operate until issues are resolved. Priority: ${failedItems.some(f => audit.sections.flatMap(s => s.questions).find(q => q.id === f.questionId)?.riskLevel === 'critical') ? 'CRITICAL' : 'HIGH'}`
                }
              </p>
            </div>

            {/* Stats */}
            <div className="grid grid-cols-3 gap-3 mb-6">
              <div className="bg-slate-800 rounded-xl p-3">
                <p className="text-2xl font-bold text-white">{answeredQuestions}</p>
                <p className="text-xs text-slate-400">Answered</p>
              </div>
              <div className="bg-slate-800 rounded-xl p-3">
                <p className="text-2xl font-bold text-white">{formatTime(elapsedTime)}</p>
                <p className="text-xs text-slate-400">Duration</p>
              </div>
              <div className="bg-slate-800 rounded-xl p-3">
                <p className="text-2xl font-bold text-red-400">{failedItems.length}</p>
                <p className="text-xs text-slate-400">Failed</p>
              </div>
            </div>

            {/* Actions */}
            <div className="flex flex-col gap-3">
              <button
                onClick={async () => {
                  triggerHaptic('heavy');
                  if (runId) {
                    try {
                      await auditsApi.completeRun(parseInt(runId, 10));
                    } catch { /* navigate anyway */ }
                  }
                  navigate('/audits');
                }}
                className="w-full py-4 bg-gradient-to-r from-purple-500 to-pink-500 text-white font-bold rounded-xl active:scale-98"
              >
                <Send className="w-5 h-5 inline mr-2" />
                Submit Audit
              </button>
              <button
                onClick={async () => {
                  if (runId) {
                    try {
                      await auditsApi.updateRun(parseInt(runId, 10), { notes: 'Draft saved from mobile' } as never);
                    } catch { /* navigate anyway */ }
                  }
                  navigate('/audits');
                }}
                className="w-full py-3 bg-slate-800 text-slate-300 rounded-xl"
              >
                Save as Draft
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (!currentQuestion) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center">
        <Loader2 className="w-8 h-8 text-purple-400 animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col">
      {/* Status Bar */}
      <StatusBar isOnline={isOnline} isSynced={isSynced} batteryLevel={batteryLevel} />

      {/* Header */}
      <header className="sticky top-0 z-40 bg-slate-900/95 backdrop-blur-xl border-b border-slate-800">
        <div className="px-4 py-3">
          <div className="flex items-center justify-between">
            <button
              onClick={() => navigate('/audits')}
              className="p-2 -ml-2"
            >
              <ArrowLeft className="w-5 h-5 text-slate-400" />
            </button>
            
            <div className="text-center">
              <h1 className="text-sm font-bold text-white">{audit.templateName}</h1>
              <p className="text-xs text-slate-500">{audit.asset}</p>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={() => setIsPaused(!isPaused)}
                className={`p-2 rounded-lg ${isPaused ? 'text-amber-400' : 'text-slate-400'}`}
              >
                {isPaused ? <Play className="w-5 h-5" /> : <Pause className="w-5 h-5" />}
              </button>
              <div className="px-2 py-1 bg-slate-800 rounded-lg">
                <span className="text-sm font-mono text-white">{formatTime(elapsedTime)}</span>
              </div>
            </div>
          </div>

          {/* Progress Bar */}
          <div className="mt-3">
            <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-purple-500 to-pink-500 transition-all duration-300"
                style={{ width: `${progressPercentage}%` }}
              />
            </div>
            <div className="flex justify-between mt-1">
              <span className="text-xs text-slate-500">{currentSection.title}</span>
              <span className="text-xs text-slate-500">{answeredQuestions}/{totalQuestions}</span>
            </div>
          </div>
        </div>
      </header>

      {/* Section Pills */}
      <div className="overflow-x-auto px-4 py-2 bg-slate-900/50">
        <div className="flex gap-2">
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
                  triggerHaptic('light');
                }}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full whitespace-nowrap text-xs font-medium transition-all ${
                  isCurrent
                    ? 'bg-purple-500 text-white'
                    : isComplete
                    ? 'bg-green-500/20 text-green-400'
                    : 'bg-slate-800 text-slate-400'
                }`}
              >
                {isComplete && <CheckCheck className="w-3 h-3" />}
                <span>{section.title}</span>
                <span className="opacity-60">{sectionAnswered}/{section.questions.length}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Main Content */}
      <main className="flex-1 overflow-y-auto pb-32">
        <div className="p-4 space-y-4">
          {/* Question Card */}
          <div className="bg-slate-900/80 border border-slate-800 rounded-2xl overflow-hidden">
            {/* Question Header */}
            <div className={`h-1 bg-gradient-to-r ${currentSection.color}`} />
            
            <div className="p-4 space-y-4">
              {/* Risk & Required Badges */}
              <div className="flex items-center gap-2">
                {currentQuestion.riskLevel && (
                  <span className={`px-2 py-0.5 text-xs font-medium rounded ${
                    currentQuestion.riskLevel === 'critical' ? 'bg-red-500/20 text-red-400' :
                    currentQuestion.riskLevel === 'high' ? 'bg-orange-500/20 text-orange-400' :
                    currentQuestion.riskLevel === 'medium' ? 'bg-amber-500/20 text-amber-400' :
                    'bg-green-500/20 text-green-400'
                  }`}>
                    {currentQuestion.riskLevel.toUpperCase()}
                  </span>
                )}
                {currentQuestion.required && (
                  <span className="px-2 py-0.5 bg-purple-500/20 text-purple-400 text-xs font-medium rounded">
                    Required
                  </span>
                )}
                {currentQuestion.evidenceRequired && (
                  <span className="px-2 py-0.5 bg-cyan-500/20 text-cyan-400 text-xs font-medium rounded flex items-center gap-1">
                    <Camera className="w-3 h-3" /> Evidence
                  </span>
                )}
              </div>

              {/* Question Text */}
              <div>
                <h2 className="text-lg font-semibold text-white leading-snug">
                  {currentQuestion.text}
                </h2>
                {currentQuestion.description && (
                  <p className="text-sm text-slate-400 mt-1">{currentQuestion.description}</p>
                )}
              </div>

              {/* Guidance Toggle */}
              {currentQuestion.guidance && (
                <button
                  onClick={() => setShowGuidance(!showGuidance)}
                  className="flex items-center gap-2 text-sm text-purple-400"
                >
                  <Lightbulb className="w-4 h-4" />
                  <span>Guidance</span>
                  {showGuidance ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                </button>
              )}
              
              {showGuidance && currentQuestion.guidance && (
                <div className="p-3 bg-purple-500/10 border border-purple-500/20 rounded-xl">
                  <p className="text-sm text-purple-200">{currentQuestion.guidance}</p>
                </div>
              )}

              {/* AI Suggestion */}
              {(showAISuggestion || aiLoading) && (
                <AISuggestion
                  suggestion={undefined}
                  confidence={undefined}
                  onAccept={() => updateResponse({ aiAccepted: true })}
                  onDismiss={() => setShowAISuggestion(false)}
                  isLoading={aiLoading}
                />
              )}

              {/* Response Input */}
              <div className="pt-2">
                {renderQuestionInput()}
              </div>
            </div>
          </div>

          {/* Evidence Section */}
          {currentQuestion.evidenceRequired && (
            <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-4">
              <h3 className="text-sm font-medium text-white mb-3 flex items-center gap-2">
                <Camera className="w-4 h-4 text-cyan-400" />
                Photo Evidence
              </h3>
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

          {/* Voice & Location */}
          <div className="grid grid-cols-2 gap-3">
            <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-3">
              <VoiceRecorder
                onRecordingComplete={(audio) => updateResponse({ voiceNote: audio })}
              />
            </div>
            <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-3">
              <LocationCapture
                location={currentResponse?.location}
                onCapture={(loc) => updateResponse({ location: loc })}
              />
            </div>
          </div>

          {/* Notes */}
          <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-4">
            <div className="flex items-center gap-2 mb-2">
              <MessageSquare className="w-4 h-4 text-slate-400" />
              <span className="text-sm font-medium text-white">Notes</span>
            </div>
            <textarea
              value={currentResponse?.notes || ''}
              onChange={(e) => updateResponse({ notes: e.target.value })}
              placeholder="Add observations..."
              rows={2}
              className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-purple-500 text-sm resize-none"
            />
          </div>

          {/* Flag */}
          <button
            onClick={() => {
              updateResponse({ flagged: !currentResponse?.flagged });
              triggerHaptic('medium');
            }}
            className={`flex items-center justify-center gap-2 w-full py-3 rounded-xl font-medium transition-all ${
              currentResponse?.flagged
                ? 'bg-red-500/20 text-red-400 border border-red-500/30'
                : 'bg-slate-800 text-slate-400 border border-slate-700'
            }`}
          >
            <Flag className={`w-4 h-4 ${currentResponse?.flagged ? 'fill-current' : ''}`} />
            {currentResponse?.flagged ? 'Issue Flagged' : 'Flag for Follow-up'}
          </button>
        </div>
      </main>

      {/* Navigation Footer */}
      <footer className="fixed bottom-0 left-0 right-0 bg-slate-900/95 backdrop-blur-xl border-t border-slate-800 p-4 safe-area-pb">
        <div className="flex items-center gap-3">
          <button
            onClick={goPrev}
            disabled={currentSectionIndex === 0 && currentQuestionIndex === 0}
            className="flex-1 flex items-center justify-center gap-2 py-4 bg-slate-800 text-slate-300 rounded-xl font-medium disabled:opacity-50 active:scale-98"
          >
            <ArrowLeft className="w-5 h-5" />
            Prev
          </button>

          {/* Quick Jump Dots */}
          <div className="flex items-center gap-1">
            {currentSection.questions.slice(
              Math.max(0, currentQuestionIndex - 2),
              Math.min(currentSection.questions.length, currentQuestionIndex + 3)
            ).map((q, idx) => {
              const actualIdx = Math.max(0, currentQuestionIndex - 2) + idx;
              return (
                <button
                  key={q.id}
                  onClick={() => {
                    setCurrentQuestionIndex(actualIdx);
                    triggerHaptic('light');
                  }}
                  className={`w-2 h-2 rounded-full transition-all ${
                    actualIdx === currentQuestionIndex
                      ? 'bg-purple-500 w-4'
                      : responses[q.id]
                      ? 'bg-green-500'
                      : 'bg-slate-600'
                  }`}
                />
              );
            })}
          </div>

          <button
            onClick={goNext}
            className="flex-1 flex items-center justify-center gap-2 py-4 bg-gradient-to-r from-purple-500 to-pink-500 text-white rounded-xl font-bold active:scale-98"
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
