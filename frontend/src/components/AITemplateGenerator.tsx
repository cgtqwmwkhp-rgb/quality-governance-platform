import { useState } from 'react';
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
  GraduationCap,
  UserCheck,
} from 'lucide-react';

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
  {
    id: 'staff-induction',
    label: 'Staff Induction',
    icon: GraduationCap,
    description: 'New starter onboarding checklist',
    prompt: 'Generate a comprehensive staff induction checklist for new starters covering company policies, health and safety essentials, site orientation, emergency procedures, PPE requirements, reporting lines, and role-specific training sign-off.',
  },
  {
    id: 'supervisor-assessment',
    label: 'Technical Assessment',
    icon: UserCheck,
    description: 'Supervisor competency evaluation',
    prompt: 'Generate a supervisor technical competency assessment template covering technical knowledge, risk assessment and method statements, safe systems of work, team supervision, equipment operation and safety, regulatory compliance awareness, problem solving, and incident reporting procedures.',
  },
];

// ============================================================================
// AI TEMPLATE GENERATION (calls backend API)
// ============================================================================

const generateTemplateWithAI = async (prompt: string): Promise<GeneratedSection[]> => {
  const response = await fetch('/api/v1/ai/generate-template', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt }),
  });

  if (!response.ok) {
    throw new Error(`AI generation failed: ${response.statusText}`);
  }

  const data: GeneratedSection[] = await response.json();
  return data;
};

// ============================================================================
// MAIN COMPONENT
// ============================================================================

export default function AITemplateGenerator({ onApply, onClose }: AITemplateGeneratorProps) {
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

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={onClose} />
      
      <div className="relative w-full max-w-2xl max-h-[90vh] bg-card border border-border rounded-2xl shadow-2xl flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-border">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 bg-primary rounded-xl flex items-center justify-center">
              <Wand2 className="w-6 h-6 text-primary-foreground" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-foreground">AI Template Generator</h2>
              <p className="text-sm text-muted-foreground">Generate audit questions from standards or descriptions</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-secondary text-muted-foreground hover:text-foreground transition-colors"
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
                <h3 className="text-sm font-medium text-foreground mb-3">Quick Start Templates</h3>
                <div className="grid grid-cols-2 gap-3">
                  {PRESET_PROMPTS.map((preset) => (
                    <button
                      key={preset.id}
                      onClick={() => {
                        setPrompt(preset.prompt);
                        handleGenerate(preset.prompt);
                      }}
                      disabled={isGenerating}
                      className="flex items-start gap-3 p-3 bg-secondary border border-border rounded-xl text-left hover:border-primary/50 hover:bg-secondary/80 transition-colors disabled:opacity-50"
                    >
                      <div className="w-10 h-10 bg-primary/20 rounded-lg flex items-center justify-center flex-shrink-0">
                        <preset.icon className="w-5 h-5 text-primary" />
                      </div>
                      <div>
                        <p className="text-sm font-medium text-foreground">{preset.label}</p>
                        <p className="text-xs text-muted-foreground mt-0.5">{preset.description}</p>
                      </div>
                    </button>
                  ))}
                </div>
              </div>

              {/* Custom Prompt */}
              <div>
                <h3 className="text-sm font-medium text-foreground mb-3">Or Describe Your Audit</h3>
                <textarea
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  placeholder="e.g., 'Create a food safety inspection checklist for a commercial kitchen covering hygiene, temperature controls, pest management, and staff training'"
                  rows={4}
                  disabled={isGenerating}
                  className="w-full px-4 py-3 bg-secondary border border-border rounded-xl text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-ring resize-none"
                />
                
                {error && (
                  <div className="flex items-center gap-2 mt-2 text-destructive text-sm">
                    <AlertTriangle className="w-4 h-4" />
                    {error}
                  </div>
                )}

                <button
                  onClick={() => handleGenerate()}
                  disabled={isGenerating || !prompt.trim()}
                  className="w-full mt-4 py-3 bg-primary text-primary-foreground font-medium rounded-xl hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
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
                  <CheckCircle2 className="w-5 h-5 text-success" />
                  <span className="text-foreground font-medium">Generated {generatedSections.length} sections</span>
                </div>
                <button
                  onClick={() => {
                    setGeneratedSections(null);
                    setPrompt('');
                  }}
                  className="text-sm text-primary hover:text-primary"
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
                        ? 'border-primary/50 bg-primary/5'
                        : 'border-border bg-secondary/50'
                    }`}
                  >
                    <button
                      onClick={() => toggleSection(section.id)}
                      className="w-full flex items-center gap-3 p-4 text-left"
                    >
                      <div className={`w-5 h-5 rounded border-2 flex items-center justify-center transition-colors ${
                        selectedSections.has(section.id)
                          ? 'bg-primary border-primary'
                          : 'border-input'
                      }`}>
                        {selectedSections.has(section.id) && (
                          <CheckCircle2 className="w-3 h-3 text-primary-foreground" />
                        )}
                      </div>
                      <div className="flex-1">
                        <p className="font-medium text-foreground">{section.title}</p>
                        <p className="text-sm text-muted-foreground">{section.questions.length} questions</p>
                      </div>
                    </button>
                    
                    {selectedSections.has(section.id) && (
                      <div className="px-4 pb-4 space-y-2 border-t border-border/50 pt-3">
                        {section.questions.slice(0, 3).map((q) => (
                          <div key={q.id} className="flex items-start gap-2 text-sm">
                            <div className="w-1.5 h-1.5 rounded-full bg-primary mt-1.5" />
                            <span className="text-foreground">{q.text}</span>
                          </div>
                        ))}
                        {section.questions.length > 3 && (
                          <p className="text-xs text-muted-foreground pl-3.5">
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
          <div className="border-t border-border p-4 flex items-center justify-between bg-card">
            <div className="text-sm text-muted-foreground">
              {selectedSections.size} sections, {totalQuestions} questions selected
            </div>
            <div className="flex gap-3">
              <button
                onClick={onClose}
                className="px-4 py-2 bg-secondary text-foreground rounded-lg hover:bg-muted"
              >
                Cancel
              </button>
              <button
                onClick={handleApply}
                disabled={selectedSections.size === 0}
                className="px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:opacity-90 disabled:opacity-50 flex items-center gap-2"
              >
                <Plus className="w-4 h-4" />
                Add to Template
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
