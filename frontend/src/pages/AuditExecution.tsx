import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
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

// Mock audit data
const MOCK_AUDIT = {
  id: 'audit-001',
  templateId: 'template-001',
  templateName: 'Vehicle Pre-Departure Inspection',
  location: 'Depot A - Main Yard',
  asset: 'LD24VLP',
  scheduledDate: '2026-01-19',
  auditor: 'John Smith',
  sections: [
    {
      id: 'sec-1',
      title: 'Exterior Checks',
      description: 'Visual inspection of vehicle exterior',
      color: 'from-blue-500 to-cyan-500',
      isComplete: false,
      questions: [
        {
          id: 'q-1-1',
          text: 'Are all lights working correctly? (headlights, indicators, brake lights, hazards)',
          description: 'Check all external lighting',
          type: 'pass_fail',
          required: true,
          weight: 2,
          evidenceRequired: true,
          guidance: 'Turn on ignition and test each light function. Walk around vehicle to verify.',
          riskLevel: 'high',
        },
        {
          id: 'q-1-2',
          text: 'Are tyres in good condition with adequate tread depth?',
          description: 'Minimum 1.6mm tread depth required',
          type: 'pass_fail',
          required: true,
          weight: 3,
          evidenceRequired: true,
          guidance: 'Use tread depth gauge. Check for damage, bulges, or embedded objects.',
          riskLevel: 'critical',
        },
        {
          id: 'q-1-3',
          text: 'Is the windscreen free from cracks or chips in driver vision area?',
          type: 'pass_fail',
          required: true,
          weight: 2,
          evidenceRequired: false,
          riskLevel: 'high',
        },
        {
          id: 'q-1-4',
          text: 'Are mirrors clean, secure, and correctly adjusted?',
          type: 'yes_no',
          required: true,
          weight: 1,
          evidenceRequired: false,
          riskLevel: 'medium',
        },
        {
          id: 'q-1-5',
          text: 'Rate the overall exterior cleanliness',
          type: 'scale_1_5',
          required: false,
          weight: 0.5,
          evidenceRequired: false,
          riskLevel: 'low',
        },
      ],
    },
    {
      id: 'sec-2',
      title: 'Interior Checks',
      description: 'Safety equipment and interior condition',
      color: 'from-purple-500 to-pink-500',
      isComplete: false,
      questions: [
        {
          id: 'q-2-1',
          text: 'Is the first aid kit present and fully stocked?',
          type: 'pass_fail',
          required: true,
          weight: 2,
          evidenceRequired: true,
          guidance: 'Check expiry dates on all items. Verify complete contents against checklist.',
          riskLevel: 'high',
        },
        {
          id: 'q-2-2',
          text: 'Is the fire extinguisher present, in date, and accessible?',
          type: 'pass_fail',
          required: true,
          weight: 2,
          evidenceRequired: true,
          riskLevel: 'critical',
        },
        {
          id: 'q-2-3',
          text: 'Is the high-visibility vest present?',
          type: 'yes_no',
          required: true,
          weight: 1,
          evidenceRequired: false,
          riskLevel: 'medium',
        },
        {
          id: 'q-2-4',
          text: 'Is the warning triangle present?',
          type: 'yes_no',
          required: true,
          weight: 1,
          evidenceRequired: false,
          riskLevel: 'medium',
        },
        {
          id: 'q-2-5',
          text: 'Are seatbelts in good condition and functioning?',
          type: 'pass_fail',
          required: true,
          weight: 3,
          evidenceRequired: false,
          riskLevel: 'critical',
        },
        {
          id: 'q-2-6',
          text: 'Note any interior damage or cleanliness issues',
          type: 'text_long',
          required: false,
          weight: 0,
          evidenceRequired: false,
          riskLevel: 'low',
        },
      ],
    },
    {
      id: 'sec-3',
      title: 'Mechanical Checks',
      description: 'Engine and fluid levels',
      color: 'from-orange-500 to-amber-500',
      isComplete: false,
      questions: [
        {
          id: 'q-3-1',
          text: 'Is the engine oil level within acceptable range?',
          type: 'pass_fail',
          required: true,
          weight: 2,
          evidenceRequired: true,
          guidance: 'Check with engine cold. Oil should be between min and max marks.',
          riskLevel: 'high',
        },
        {
          id: 'q-3-2',
          text: 'Is the coolant level adequate?',
          type: 'pass_fail',
          required: true,
          weight: 2,
          evidenceRequired: false,
          riskLevel: 'high',
        },
        {
          id: 'q-3-3',
          text: 'Is the screenwash fluid topped up?',
          type: 'yes_no',
          required: true,
          weight: 1,
          evidenceRequired: false,
          riskLevel: 'low',
        },
        {
          id: 'q-3-4',
          text: 'Are there any warning lights on the dashboard?',
          type: 'yes_no_na',
          required: true,
          weight: 3,
          evidenceRequired: true,
          guidance: 'If yes, photograph the warning light and do not use vehicle.',
          riskLevel: 'critical',
        },
        {
          id: 'q-3-5',
          text: 'Current odometer reading',
          type: 'numeric',
          required: true,
          weight: 0,
          evidenceRequired: false,
          riskLevel: 'low',
        },
      ],
    },
  ] as AuditSection[],
};

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
    success: 'border-green-500 bg-green-500/20 text-green-400',
    danger: 'border-red-500 bg-red-500/20 text-red-400',
    warning: 'border-amber-500 bg-amber-500/20 text-amber-400',
    neutral: 'border-slate-500 bg-slate-500/20 text-slate-400',
  };

  const hoverStyles = {
    success: 'hover:bg-green-500/30 hover:border-green-400',
    danger: 'hover:bg-red-500/30 hover:border-red-400',
    warning: 'hover:bg-amber-500/30 hover:border-amber-400',
    neutral: 'hover:bg-slate-500/30 hover:border-slate-400',
  };

  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex-1 flex items-center justify-center gap-2 py-4 px-4 rounded-xl border-2 font-semibold transition-all duration-200
        ${selected ? variantStyles[variant] : `border-slate-700 bg-slate-800 text-slate-400 ${hoverStyles[variant]}`}`}
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
              ? 'bg-purple-500 text-white shadow-lg shadow-purple-500/25'
              : 'bg-slate-800 text-slate-400 hover:bg-slate-700 hover:text-white border border-slate-700'
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
        className="w-full py-4 border-2 border-dashed border-slate-700 rounded-xl text-slate-400 hover:border-purple-500 hover:text-purple-400 transition-colors flex items-center justify-center gap-2"
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
    ctx.strokeStyle = '#a855f7';
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
          className="w-full h-40 bg-slate-800 border border-slate-700 rounded-xl cursor-crosshair touch-none"
        />
        {!signature && (
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
            <p className="text-slate-500">Sign here</p>
          </div>
        )}
      </div>
      <button
        type="button"
        onClick={clearCanvas}
        className="text-sm text-slate-400 hover:text-white flex items-center gap-1"
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
  
  const [audit] = useState(MOCK_AUDIT);
  const [currentSectionIndex, setCurrentSectionIndex] = useState(0);
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
  const [responses, setResponses] = useState<Record<string, QuestionResponse>>({});
  const [isPaused, setIsPaused] = useState(false);
  const [elapsedTime, setElapsedTime] = useState(0);
  const [showGuidance, setShowGuidance] = useState(false);
  const [showSummary, setShowSummary] = useState(false);

  // Timer
  useEffect(() => {
    if (isPaused) return;
    
    const timer = setInterval(() => {
      setElapsedTime(prev => prev + 1);
    }, 1000);

    return () => clearInterval(timer);
  }, [isPaused]);

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  // Current section and question
  const currentSection = audit.sections[currentSectionIndex];
  const currentQuestion = currentSection.questions[currentQuestionIndex];
  const currentResponse = responses[currentQuestion.id];

  // Calculate progress
  const totalQuestions = audit.sections.reduce((sum, s) => sum + s.questions.length, 0);
  const answeredQuestions = Object.keys(responses).length;
  const progressPercentage = (answeredQuestions / totalQuestions) * 100;

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
            className="w-full px-4 py-3 bg-slate-800 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-purple-500"
          />
        );

      case 'text_long':
        return (
          <textarea
            value={(currentResponse?.response as string) || ''}
            onChange={(e) => updateResponse({ response: e.target.value })}
            placeholder="Enter detailed response..."
            rows={4}
            className="w-full px-4 py-3 bg-slate-800 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-purple-500 resize-none"
          />
        );

      case 'numeric':
        return (
          <input
            type="number"
            value={(currentResponse?.response as string) || ''}
            onChange={(e) => updateResponse({ response: e.target.value })}
            placeholder="Enter number..."
            className="w-full px-4 py-3 bg-slate-800 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-purple-500"
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
      <div className="min-h-screen bg-slate-950 flex items-center justify-center p-4">
        <div className="max-w-lg w-full bg-slate-900 border border-slate-800 rounded-3xl p-8 text-center animate-fade-in">
          {/* Score Display */}
          <div className={`w-32 h-32 mx-auto rounded-full flex items-center justify-center mb-6 ${
            passed ? 'bg-gradient-to-br from-green-500 to-emerald-500' : 'bg-gradient-to-br from-red-500 to-rose-500'
          }`}>
            <span className="text-4xl font-bold text-white">{score}%</span>
          </div>

          <h2 className={`text-3xl font-bold mb-2 ${passed ? 'text-green-400' : 'text-red-400'}`}>
            {passed ? 'AUDIT PASSED' : 'AUDIT FAILED'}
          </h2>
          <p className="text-slate-400 mb-8">
            {audit.templateName} - {audit.asset}
          </p>

          {/* Stats */}
          <div className="grid grid-cols-3 gap-4 mb-8">
            <div className="bg-slate-800 rounded-xl p-4">
              <p className="text-2xl font-bold text-white">{answeredQuestions}</p>
              <p className="text-xs text-slate-400">Questions Answered</p>
            </div>
            <div className="bg-slate-800 rounded-xl p-4">
              <p className="text-2xl font-bold text-white">{formatTime(elapsedTime)}</p>
              <p className="text-xs text-slate-400">Duration</p>
            </div>
            <div className="bg-slate-800 rounded-xl p-4">
              <p className="text-2xl font-bold text-white">
                {Object.values(responses).filter(r => r.photos && r.photos.length > 0).length}
              </p>
              <p className="text-xs text-slate-400">Photos</p>
            </div>
          </div>

          {/* Findings Summary */}
          <div className="text-left mb-8">
            <h3 className="text-lg font-semibold text-white mb-3">Findings</h3>
            <div className="space-y-2">
              {Object.values(responses)
                .filter(r => r.response === 'fail' || r.response === 'no')
                .map((r, idx) => {
                  const question = audit.sections
                    .flatMap(s => s.questions)
                    .find(q => q.id === r.questionId);
                  return (
                    <div key={idx} className="flex items-start gap-2 p-3 bg-red-500/10 border border-red-500/20 rounded-lg">
                      <XCircle className="w-5 h-5 text-red-400 mt-0.5" />
                      <p className="text-sm text-red-300">{question?.text}</p>
                    </div>
                  );
                })}
              {Object.values(responses).filter(r => r.response === 'fail' || r.response === 'no').length === 0 && (
                <p className="text-sm text-slate-400">No failed items</p>
              )}
            </div>
          </div>

          {/* Actions */}
          <div className="flex gap-3">
            <button
              onClick={() => navigate('/audits')}
              className="flex-1 py-3 bg-slate-800 text-slate-300 rounded-xl hover:bg-slate-700 transition-colors"
            >
              Back to Audits
            </button>
            <button
              onClick={() => {/* Submit audit */}}
              className="flex-1 py-3 bg-gradient-to-r from-purple-500 to-pink-500 text-white font-semibold rounded-xl hover:opacity-90 transition-opacity"
            >
              Submit Audit
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col">
      {/* Header */}
      <header className="sticky top-0 z-40 bg-slate-900/80 backdrop-blur-xl border-b border-slate-800">
        <div className="px-4 py-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <button
                onClick={() => navigate('/audits')}
                className="p-2 hover:bg-slate-800 rounded-lg transition-colors"
              >
                <ArrowLeft className="w-5 h-5 text-slate-400" />
              </button>
              <div>
                <h1 className="text-lg font-bold text-white">{audit.templateName}</h1>
                <p className="text-xs text-slate-400">{audit.asset} • {audit.location}</p>
              </div>
            </div>

            <div className="flex items-center gap-3">
              {/* Timer */}
              <div className="flex items-center gap-2 px-3 py-1.5 bg-slate-800 rounded-lg">
                <Timer className="w-4 h-4 text-slate-400" />
                <span className="text-sm font-mono text-white">{formatTime(elapsedTime)}</span>
              </div>

              {/* Pause/Play */}
              <button
                onClick={() => setIsPaused(!isPaused)}
                className={`p-2 rounded-lg transition-colors ${
                  isPaused ? 'bg-amber-500/20 text-amber-400' : 'bg-slate-800 text-slate-400 hover:text-white'
                }`}
              >
                {isPaused ? <Play className="w-5 h-5" /> : <Pause className="w-5 h-5" />}
              </button>

              {/* Save Draft */}
              <button className="flex items-center gap-2 px-4 py-2 bg-slate-800 text-slate-300 rounded-lg hover:bg-slate-700">
                <Save className="w-4 h-4" />
                Save
              </button>
            </div>
          </div>

          {/* Progress Bar */}
          <div className="mt-3">
            <div className="flex items-center justify-between text-xs text-slate-400 mb-1">
              <span>Progress: {answeredQuestions}/{totalQuestions} questions</span>
              <span>{Math.round(progressPercentage)}%</span>
            </div>
            <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-purple-500 to-pink-500 transition-all duration-300"
                style={{ width: `${progressPercentage}%` }}
              />
            </div>
          </div>
        </div>
      </header>

      {/* Section Navigation */}
      <div className="bg-slate-900/50 border-b border-slate-800 overflow-x-auto">
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
                    ? `bg-gradient-to-r ${section.color} text-white`
                    : isComplete
                    ? 'bg-green-500/20 text-green-400 border border-green-500/30'
                    : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
                }`}
              >
                {isComplete ? (
                  <CheckCheck className="w-4 h-4" />
                ) : (
                  <span className="w-5 h-5 rounded-full bg-slate-700 text-xs flex items-center justify-center">
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
          <div className="bg-slate-900/50 border border-slate-800 rounded-3xl overflow-hidden">
            {/* Question Header */}
            <div className={`bg-gradient-to-r ${currentSection.color} p-0.5`}>
              <div className="bg-slate-900 p-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-slate-400">
                      {currentSection.title} • Question {currentQuestionIndex + 1} of {currentSection.questions.length}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    {currentQuestion.riskLevel && (
                      <span className={`px-2 py-1 text-xs rounded ${
                        currentQuestion.riskLevel === 'critical' ? 'bg-red-500/20 text-red-400' :
                        currentQuestion.riskLevel === 'high' ? 'bg-orange-500/20 text-orange-400' :
                        currentQuestion.riskLevel === 'medium' ? 'bg-amber-500/20 text-amber-400' :
                        'bg-green-500/20 text-green-400'
                      }`}>
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
              {/* Question Text */}
              <div>
                <h2 className="text-xl font-semibold text-white mb-2">
                  {currentQuestion.text}
                </h2>
                {currentQuestion.description && (
                  <p className="text-sm text-slate-400">{currentQuestion.description}</p>
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
                    {showGuidance ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                  </button>
                  {showGuidance && (
                    <div className="mt-2 p-3 bg-purple-500/10 border border-purple-500/20 rounded-lg">
                      <p className="text-sm text-purple-300">{currentQuestion.guidance}</p>
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
                <div className="pt-4 border-t border-slate-800">
                  <div className="flex items-center gap-2 mb-3">
                    <Camera className="w-4 h-4 text-cyan-400" />
                    <span className="text-sm font-medium text-white">Photo Evidence Required</span>
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
              <div className="pt-4 border-t border-slate-800">
                <div className="flex items-center gap-2 mb-3">
                  <MessageSquare className="w-4 h-4 text-slate-400" />
                  <span className="text-sm font-medium text-white">Additional Notes</span>
                </div>
                <textarea
                  value={currentResponse?.notes || ''}
                  onChange={(e) => updateResponse({ notes: e.target.value })}
                  placeholder="Add any additional observations..."
                  rows={2}
                  className="w-full px-4 py-3 bg-slate-800 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-purple-500 resize-none text-sm"
                />
              </div>

              {/* Flag Issue */}
              <button
                onClick={() => updateResponse({ flagged: !currentResponse?.flagged })}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
                  currentResponse?.flagged
                    ? 'bg-red-500/20 text-red-400 border border-red-500/30'
                    : 'bg-slate-800 text-slate-400 hover:text-white'
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
      <footer className="fixed bottom-0 left-0 right-0 bg-slate-900/80 backdrop-blur-xl border-t border-slate-800 p-4">
        <div className="max-w-2xl mx-auto flex items-center justify-between">
          <button
            onClick={goPrev}
            disabled={currentSectionIndex === 0 && currentQuestionIndex === 0}
            className="flex items-center gap-2 px-6 py-3 bg-slate-800 text-slate-300 rounded-xl hover:bg-slate-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
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
                    ? 'bg-purple-500 w-6'
                    : responses[currentSection.questions[idx].id]
                    ? 'bg-green-500'
                    : 'bg-slate-700 hover:bg-slate-600'
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
