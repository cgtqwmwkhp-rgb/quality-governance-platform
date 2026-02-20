import { useState, useEffect, useRef } from 'react';
import {
  Sparkles,
  Wand2,
  Loader2,
  CheckCircle2,
  Plus,
  Leaf,
  HardHat,
  Award,
  Building2,
  Truck,
  ClipboardCheck,
  AlertTriangle,
  X,
} from 'lucide-react';
import { aiApi } from '../api/client';

// ============================================================================
// TYPES
// ============================================================================

interface GeneratedQuestion {
  id: string;
  text: string;
  type: string;
  required: boolean;
  weight: number;
  riskLevel?: string;
  evidenceRequired: boolean;
  isoClause?: string;
  guidance?: string;
}

interface GeneratedSection {
  id: string;
  title: string;
  description: string;
  questions: GeneratedQuestion[];
}

interface AITemplateGeneratorProps {
  onApply: (sections: GeneratedSection[]) => void;
  onClose: () => void;
  applying?: boolean;
}

// ============================================================================
// PRESET PROMPTS
// ============================================================================

const PRESET_PROMPTS = [
  {
    id: 'iso9001',
    label: 'ISO 9001 Quality',
    icon: Award,
    description: 'Generate ISO 9001:2015 compliance questions',
    prompt: 'Generate a comprehensive ISO 9001:2015 Quality Management System audit checklist covering context, leadership, planning, support, operation, performance evaluation, and improvement clauses.',
  },
  {
    id: 'iso14001',
    label: 'ISO 14001 Environmental',
    icon: Leaf,
    description: 'Environmental management audit',
    prompt: 'Generate an ISO 14001:2015 Environmental Management System audit checklist covering environmental aspects, legal requirements, objectives, operational controls, emergency preparedness, and performance monitoring.',
  },
  {
    id: 'iso45001',
    label: 'ISO 45001 H&S',
    icon: HardHat,
    description: 'Health & safety management audit',
    prompt: 'Generate an ISO 45001:2018 Occupational Health and Safety audit checklist covering hazard identification, risk assessment, legal compliance, worker participation, competence, emergency response, and incident investigation.',
  },
  {
    id: 'vehicle',
    label: 'Vehicle Inspection',
    icon: Truck,
    description: 'Pre-departure vehicle check',
    prompt: 'Generate a comprehensive vehicle pre-departure safety inspection checklist covering exterior, interior, mechanical, safety equipment, and documentation checks.',
  },
  {
    id: '5s',
    label: '5S Workplace',
    icon: ClipboardCheck,
    description: 'Sort, Set, Shine, Standardize, Sustain',
    prompt: 'Generate a 5S workplace organization audit checklist with sections for Sort (Seiri), Set in Order (Seiton), Shine (Seiso), Standardize (Seiketsu), and Sustain (Shitsuke).',
  },
  {
    id: 'supplier',
    label: 'Supplier Assessment',
    icon: Building2,
    description: 'Vendor qualification audit',
    prompt: 'Generate a supplier qualification assessment checklist covering quality systems, capacity, financial stability, delivery performance, sustainability practices, and compliance certifications.',
  },
];

// ============================================================================
// AI GENERATION (tries backend API, falls back to built-in templates)
// ============================================================================

const STANDARD_MAP: Record<string, string> = {
  'iso 9001': 'ISO 9001',
  'iso 14001': 'ISO 14001',
  'iso 45001': 'ISO 45001',
  'quality': 'ISO 9001',
  'environmental': 'ISO 14001',
  'health': 'ISO 45001',
  'safety': 'ISO 45001',
};

function detectStandard(prompt: string): string | null {
  const lower = prompt.toLowerCase();
  for (const [key, standard] of Object.entries(STANDARD_MAP)) {
    if (lower.includes(key)) return standard;
  }
  return null;
}

const generateTemplateWithAI = async (prompt: string): Promise<GeneratedSection[]> => {
  const standard = detectStandard(prompt);
  if (standard) {
    try {
      const res = await aiApi.generateAuditChecklist(standard);
      const data = res.data as any[];
      if (Array.isArray(data) && data.length > 0) {
        return data.map((section: any, sIdx: number) => ({
          id: section.id || `sec-${sIdx}`,
          title: section.title || section.clause || `Section ${sIdx + 1}`,
          description: section.description || '',
          questions: (section.questions || []).map((q: any, qIdx: number) => ({
            id: q.id || `q-${sIdx}-${qIdx}`,
            text: q.text || q.question_text || '',
            type: q.type || q.question_type || 'yes_no',
            required: q.required !== false,
            weight: q.weight ?? 1,
            riskLevel: q.risk_level || q.riskLevel || 'medium',
            evidenceRequired: q.evidence_required || q.evidenceRequired || false,
            isoClause: q.iso_clause || q.isoClause,
            guidance: q.guidance,
          })),
        }));
      }
    } catch {
      // fall through to built-in templates
    }
  }

  const lowerPrompt = prompt.toLowerCase();
  
  if (lowerPrompt.includes('vehicle') || lowerPrompt.includes('car') || lowerPrompt.includes('fleet')) {
    return [
      {
        id: 'sec-ext',
        title: 'Exterior Inspection',
        description: 'Visual inspection of vehicle exterior components',
        questions: [
          { id: 'q-1', text: 'Are all external lights functioning correctly? (headlights, brake lights, indicators, hazards)', type: 'pass_fail', required: true, weight: 3, riskLevel: 'critical', evidenceRequired: true, guidance: 'Test all lights with engine running. Check for dim or flickering bulbs.' },
          { id: 'q-2', text: 'Are all tyres in good condition with minimum 1.6mm tread depth?', type: 'pass_fail', required: true, weight: 3, riskLevel: 'critical', evidenceRequired: true, guidance: 'Use tread depth gauge. Check for bulges, cuts, or embedded objects.' },
          { id: 'q-3', text: 'Is the windscreen free from chips or cracks in the driver vision area?', type: 'pass_fail', required: true, weight: 2, riskLevel: 'high', evidenceRequired: true },
          { id: 'q-4', text: 'Are all mirrors present, clean, and correctly adjusted?', type: 'yes_no', required: true, weight: 2, riskLevel: 'high', evidenceRequired: false },
          { id: 'q-5', text: 'Is the vehicle bodywork free from significant damage?', type: 'yes_no', required: true, weight: 1, riskLevel: 'medium', evidenceRequired: false },
          { id: 'q-6', text: 'Are number plates clean, visible, and correctly displayed?', type: 'yes_no', required: true, weight: 1, riskLevel: 'medium', evidenceRequired: false },
        ],
      },
      {
        id: 'sec-int',
        title: 'Interior & Safety Equipment',
        description: 'Interior condition and safety equipment checks',
        questions: [
          { id: 'q-7', text: 'Is the first aid kit present, sealed, and within expiry date?', type: 'pass_fail', required: true, weight: 2, riskLevel: 'high', evidenceRequired: true, guidance: 'Verify seal is intact. Check expiry sticker.' },
          { id: 'q-8', text: 'Is the fire extinguisher present, in date, and gauge in green zone?', type: 'pass_fail', required: true, weight: 2, riskLevel: 'critical', evidenceRequired: true },
          { id: 'q-9', text: 'Is the high-visibility vest present and in good condition?', type: 'yes_no', required: true, weight: 1, riskLevel: 'medium', evidenceRequired: false },
          { id: 'q-10', text: 'Is the warning triangle present?', type: 'yes_no', required: true, weight: 1, riskLevel: 'medium', evidenceRequired: false },
          { id: 'q-11', text: 'Are all seatbelts functioning correctly?', type: 'pass_fail', required: true, weight: 3, riskLevel: 'critical', evidenceRequired: false, guidance: 'Test each seatbelt locks and retracts properly.' },
          { id: 'q-12', text: 'Is the vehicle interior clean and free from loose items?', type: 'yes_no', required: false, weight: 0.5, riskLevel: 'low', evidenceRequired: false },
        ],
      },
      {
        id: 'sec-mech',
        title: 'Mechanical Checks',
        description: 'Engine, fluids, and mechanical systems',
        questions: [
          { id: 'q-13', text: 'Is the engine oil level within acceptable range?', type: 'pass_fail', required: true, weight: 2, riskLevel: 'high', evidenceRequired: true, guidance: 'Check with engine cold. Oil between min and max marks.' },
          { id: 'q-14', text: 'Is the coolant level adequate?', type: 'pass_fail', required: true, weight: 2, riskLevel: 'high', evidenceRequired: false },
          { id: 'q-15', text: 'Is the brake fluid level adequate?', type: 'pass_fail', required: true, weight: 2, riskLevel: 'critical', evidenceRequired: false },
          { id: 'q-16', text: 'Is the screenwash fluid topped up?', type: 'yes_no', required: true, weight: 0.5, riskLevel: 'low', evidenceRequired: false },
          { id: 'q-17', text: 'Are there any dashboard warning lights illuminated?', type: 'yes_no', required: true, weight: 3, riskLevel: 'critical', evidenceRequired: true, guidance: 'If any warning lights are on, photograph and report immediately.' },
          { id: 'q-18', text: 'Current odometer reading (miles)', type: 'number', required: true, weight: 0, riskLevel: 'low', evidenceRequired: false },
        ],
      },
      {
        id: 'sec-doc',
        title: 'Documentation',
        description: 'Required vehicle documents',
        questions: [
          { id: 'q-19', text: 'Is the MOT valid and certificate available?', type: 'pass_fail', required: true, weight: 3, riskLevel: 'critical', evidenceRequired: true },
          { id: 'q-20', text: 'Is the vehicle insurance valid and certificate available?', type: 'pass_fail', required: true, weight: 3, riskLevel: 'critical', evidenceRequired: true },
          { id: 'q-21', text: 'Is the vehicle tax valid?', type: 'pass_fail', required: true, weight: 3, riskLevel: 'critical', evidenceRequired: false },
          { id: 'q-22', text: 'Is the driver licence checked and valid for this vehicle category?', type: 'pass_fail', required: true, weight: 3, riskLevel: 'critical', evidenceRequired: false },
        ],
      },
    ];
  }
  
  if (lowerPrompt.includes('5s') || lowerPrompt.includes('workplace')) {
    return [
      {
        id: 'sec-sort',
        title: 'Sort (Seiri)',
        description: 'Remove unnecessary items from the workplace',
        questions: [
          { id: 'q-1', text: 'Are all items in the work area necessary for current operations?', type: 'pass_fail', required: true, weight: 2, riskLevel: 'medium', evidenceRequired: true },
          { id: 'q-2', text: 'Is there a clear system for disposing of unnecessary items?', type: 'yes_no', required: true, weight: 1, riskLevel: 'low', evidenceRequired: false },
          { id: 'q-3', text: 'Are red tag procedures being followed for unneeded items?', type: 'yes_no', required: false, weight: 1, riskLevel: 'low', evidenceRequired: false },
        ],
      },
      {
        id: 'sec-set',
        title: 'Set in Order (Seiton)',
        description: 'Organize items for easy access',
        questions: [
          { id: 'q-4', text: 'Do all items have a designated storage location?', type: 'pass_fail', required: true, weight: 2, riskLevel: 'medium', evidenceRequired: true },
          { id: 'q-5', text: 'Are storage locations clearly labeled?', type: 'yes_no', required: true, weight: 1, riskLevel: 'low', evidenceRequired: true },
          { id: 'q-6', text: 'Are frequently used items stored at point of use?', type: 'yes_no', required: true, weight: 1, riskLevel: 'low', evidenceRequired: false },
        ],
      },
      {
        id: 'sec-shine',
        title: 'Shine (Seiso)',
        description: 'Clean the workplace and equipment',
        questions: [
          { id: 'q-7', text: 'Is the work area clean and free from debris?', type: 'pass_fail', required: true, weight: 2, riskLevel: 'medium', evidenceRequired: true },
          { id: 'q-8', text: 'Is equipment cleaned regularly and properly maintained?', type: 'yes_no', required: true, weight: 2, riskLevel: 'medium', evidenceRequired: false },
          { id: 'q-9', text: 'Are cleaning schedules posted and followed?', type: 'yes_no', required: false, weight: 1, riskLevel: 'low', evidenceRequired: true },
        ],
      },
      {
        id: 'sec-std',
        title: 'Standardize (Seiketsu)',
        description: 'Create consistent procedures',
        questions: [
          { id: 'q-10', text: 'Are standard work procedures documented and visible?', type: 'pass_fail', required: true, weight: 2, riskLevel: 'medium', evidenceRequired: true },
          { id: 'q-11', text: 'Do visual controls indicate correct vs. incorrect states?', type: 'yes_no', required: true, weight: 1, riskLevel: 'low', evidenceRequired: true },
        ],
      },
      {
        id: 'sec-sus',
        title: 'Sustain (Shitsuke)',
        description: 'Maintain and improve standards',
        questions: [
          { id: 'q-12', text: 'Are 5S audits conducted regularly?', type: 'yes_no', required: true, weight: 1, riskLevel: 'low', evidenceRequired: false },
          { id: 'q-13', text: 'Is there evidence of continuous improvement activities?', type: 'yes_no', required: true, weight: 1, riskLevel: 'low', evidenceRequired: false },
          { id: 'q-14', text: 'Overall 5S score for this area', type: 'score', required: true, weight: 2, riskLevel: 'medium', evidenceRequired: false },
        ],
      },
    ];
  }

  // Default generic audit template
  return [
    {
      id: 'sec-1',
      title: 'Management & Leadership',
      description: 'Leadership commitment and management system',
      questions: [
        { id: 'q-1', text: 'Is there documented evidence of top management commitment?', type: 'pass_fail', required: true, weight: 2, riskLevel: 'high', evidenceRequired: true },
        { id: 'q-2', text: 'Are roles, responsibilities, and authorities defined and communicated?', type: 'yes_no', required: true, weight: 2, riskLevel: 'medium', evidenceRequired: false },
        { id: 'q-3', text: 'Are objectives established at relevant functions and levels?', type: 'yes_no', required: true, weight: 1, riskLevel: 'medium', evidenceRequired: false },
      ],
    },
    {
      id: 'sec-2',
      title: 'Resources & Competence',
      description: 'Human resources and competence requirements',
      questions: [
        { id: 'q-4', text: 'Are resources adequate for maintaining the management system?', type: 'pass_fail', required: true, weight: 2, riskLevel: 'medium', evidenceRequired: false },
        { id: 'q-5', text: 'Is there evidence of competence assessment for personnel?', type: 'pass_fail', required: true, weight: 2, riskLevel: 'high', evidenceRequired: true },
        { id: 'q-6', text: 'Are training records maintained and up to date?', type: 'yes_no', required: true, weight: 1, riskLevel: 'medium', evidenceRequired: true },
      ],
    },
    {
      id: 'sec-3',
      title: 'Operations & Processes',
      description: 'Operational controls and processes',
      questions: [
        { id: 'q-7', text: 'Are operational processes defined and controlled?', type: 'pass_fail', required: true, weight: 2, riskLevel: 'high', evidenceRequired: false },
        { id: 'q-8', text: 'Are process outputs meeting specified requirements?', type: 'pass_fail', required: true, weight: 2, riskLevel: 'high', evidenceRequired: true },
        { id: 'q-9', text: 'Are changes to processes managed effectively?', type: 'yes_no', required: true, weight: 1, riskLevel: 'medium', evidenceRequired: false },
      ],
    },
    {
      id: 'sec-4',
      title: 'Performance & Improvement',
      description: 'Monitoring, measurement, and improvement',
      questions: [
        { id: 'q-10', text: 'Are key performance indicators defined and monitored?', type: 'pass_fail', required: true, weight: 2, riskLevel: 'medium', evidenceRequired: true },
        { id: 'q-11', text: 'Are internal audits conducted as planned?', type: 'yes_no', required: true, weight: 2, riskLevel: 'high', evidenceRequired: true },
        { id: 'q-12', text: 'Is there evidence of corrective actions for nonconformities?', type: 'pass_fail', required: true, weight: 2, riskLevel: 'high', evidenceRequired: true },
        { id: 'q-13', text: 'Is there evidence of continual improvement?', type: 'yes_no', required: true, weight: 1, riskLevel: 'medium', evidenceRequired: false },
      ],
    },
  ];
};

// ============================================================================
// MAIN COMPONENT
// ============================================================================

export default function AITemplateGenerator({ onApply, onClose, applying }: AITemplateGeneratorProps) {
  const [prompt, setPrompt] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [generatedSections, setGeneratedSections] = useState<GeneratedSection[] | null>(null);
  const [selectedSections, setSelectedSections] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);

  const handleGenerate = async (customPrompt?: string) => {
    const promptToUse = customPrompt || prompt;
    if (!promptToUse.trim()) {
      setError('Please enter a description or select a preset');
      return;
    }

    setIsGenerating(true);
    setError(null);
    setGeneratedSections(null);

    try {
      const sections = await generateTemplateWithAI(promptToUse);
      setGeneratedSections(sections);
      setSelectedSections(new Set(sections.map(s => s.id)));
    } catch (err) {
      setError('Failed to generate template. Please try again.');
      console.error('Generation error:', err);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleApply = () => {
    if (!generatedSections) return;
    
    const sectionsToApply = generatedSections.filter(s => selectedSections.has(s.id));
    onApply(sectionsToApply);
  };

  const toggleSection = (sectionId: string) => {
    const newSelected = new Set(selectedSections);
    if (newSelected.has(sectionId)) {
      newSelected.delete(sectionId);
    } else {
      newSelected.add(sectionId);
    }
    setSelectedSections(newSelected);
  };

  const totalQuestions = generatedSections
    ?.filter(s => selectedSections.has(s.id))
    .reduce((sum, s) => sum + s.questions.length, 0) || 0;

  const dialogRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleKeyDown);
    document.body.style.overflow = 'hidden';
    dialogRef.current?.focus();
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = '';
    };
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={onClose} />
      
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="ai-generator-title"
        tabIndex={-1}
        className="relative w-full max-w-2xl max-h-[90vh] bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl flex flex-col overflow-hidden"
      >
        <div className="flex items-center justify-between p-6 border-b border-slate-800">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 bg-gradient-to-br from-purple-500 to-pink-500 rounded-xl flex items-center justify-center">
              <Wand2 className="w-6 h-6 text-white" />
            </div>
            <div>
              <h2 id="ai-generator-title" className="text-lg font-semibold text-white">AI Template Generator</h2>
              <p className="text-sm text-slate-400">Generate audit questions from standards or descriptions</p>
            </div>
          </div>
          <button
            onClick={onClose}
            aria-label="Close AI Template Generator"
            className="p-2 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {!generatedSections && (
            <>
              {/* Preset Templates */}
              <div>
                <h3 className="text-sm font-medium text-white mb-3">Quick Start Templates</h3>
                <div className="grid grid-cols-2 gap-3">
                  {PRESET_PROMPTS.map((preset) => (
                    <button
                      key={preset.id}
                      onClick={() => {
                        setPrompt(preset.prompt);
                        handleGenerate(preset.prompt);
                      }}
                      disabled={isGenerating}
                      className="flex items-start gap-3 p-3 bg-slate-800 border border-slate-700 rounded-xl text-left hover:border-purple-500/50 hover:bg-slate-800/80 transition-colors disabled:opacity-50"
                    >
                      <div className="w-10 h-10 bg-purple-500/20 rounded-lg flex items-center justify-center flex-shrink-0">
                        <preset.icon className="w-5 h-5 text-purple-400" />
                      </div>
                      <div>
                        <p className="text-sm font-medium text-white">{preset.label}</p>
                        <p className="text-xs text-slate-400 mt-0.5">{preset.description}</p>
                      </div>
                    </button>
                  ))}
                </div>
              </div>

              {/* Custom Prompt */}
              <div>
                <h3 className="text-sm font-medium text-white mb-3">Or Describe Your Audit</h3>
                <textarea
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  placeholder="e.g., 'Create a food safety inspection checklist for a commercial kitchen covering hygiene, temperature controls, pest management, and staff training'"
                  rows={4}
                  disabled={isGenerating}
                  className="w-full px-4 py-3 bg-slate-800 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-purple-500 resize-none"
                />
                
                {error && (
                  <div className="flex items-center gap-2 mt-2 text-red-400 text-sm">
                    <AlertTriangle className="w-4 h-4" />
                    {error}
                  </div>
                )}

                <button
                  onClick={() => handleGenerate()}
                  disabled={isGenerating || !prompt.trim()}
                  className="w-full mt-4 py-3 bg-gradient-to-r from-purple-500 to-pink-500 text-white font-medium rounded-xl hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                >
                  {isGenerating ? (
                    <>
                      <Loader2 className="w-5 h-5 animate-spin" />
                      Generating with AI...
                    </>
                  ) : (
                    <>
                      <Sparkles className="w-5 h-5" />
                      Generate Template
                    </>
                  )}
                </button>
              </div>
            </>
          )}

          {/* Generated Results */}
          {generatedSections && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="w-5 h-5 text-green-400" />
                  <span className="text-white font-medium">Generated {generatedSections.length} sections</span>
                </div>
                <button
                  onClick={() => {
                    setGeneratedSections(null);
                    setPrompt('');
                  }}
                  className="text-sm text-purple-400 hover:text-purple-300"
                >
                  Generate New
                </button>
              </div>

              <div className="space-y-3">
                {generatedSections.map((section) => (
                  <div
                    key={section.id}
                    className={`border rounded-xl overflow-hidden transition-colors ${
                      selectedSections.has(section.id)
                        ? 'border-purple-500/50 bg-purple-500/5'
                        : 'border-slate-700 bg-slate-800/50'
                    }`}
                  >
                    <button
                      onClick={() => toggleSection(section.id)}
                      className="w-full flex items-center gap-3 p-4 text-left"
                    >
                      <div className={`w-5 h-5 rounded border-2 flex items-center justify-center transition-colors ${
                        selectedSections.has(section.id)
                          ? 'bg-purple-500 border-purple-500'
                          : 'border-slate-600'
                      }`}>
                        {selectedSections.has(section.id) && (
                          <CheckCircle2 className="w-3 h-3 text-white" />
                        )}
                      </div>
                      <div className="flex-1">
                        <p className="font-medium text-white">{section.title}</p>
                        <p className="text-sm text-slate-400">{section.questions.length} questions</p>
                      </div>
                    </button>
                    
                    {selectedSections.has(section.id) && (
                      <div className="px-4 pb-4 space-y-2 border-t border-slate-700/50 pt-3">
                        {section.questions.slice(0, 3).map((q) => (
                          <div key={q.id} className="flex items-start gap-2 text-sm">
                            <div className="w-1.5 h-1.5 rounded-full bg-purple-400 mt-1.5" />
                            <span className="text-slate-300">{q.text}</span>
                          </div>
                        ))}
                        {section.questions.length > 3 && (
                          <p className="text-xs text-slate-500 pl-3.5">
                            +{section.questions.length - 3} more questions
                          </p>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        {generatedSections && (
          <div className="border-t border-slate-800 p-4 flex items-center justify-between bg-slate-900">
            <div className="text-sm text-slate-400">
              {selectedSections.size} sections, {totalQuestions} questions selected
            </div>
            <div className="flex gap-3">
              <button
                onClick={onClose}
                className="px-4 py-2 bg-slate-800 text-slate-300 rounded-lg hover:bg-slate-700"
              >
                Cancel
              </button>
              <button
                onClick={handleApply}
                disabled={selectedSections.size === 0 || applying}
                className="px-4 py-2 bg-gradient-to-r from-purple-500 to-pink-500 text-white rounded-lg hover:opacity-90 disabled:opacity-50 flex items-center gap-2"
              >
                {applying ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Adding sections...
                  </>
                ) : (
                  <>
                    <Plus className="w-4 h-4" />
                    Add to Template
                  </>
                )}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
