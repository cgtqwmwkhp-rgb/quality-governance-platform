/**
 * PortalDynamicForm - Dynamic form page that renders forms from configuration
 * 
 * This page:
 * 1. Loads form template from API or uses fallback config
 * 2. Loads contracts and lookup options from API
 * 3. Renders the form using DynamicFormRenderer
 * 4. Handles submission to the portal API
 */

import { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { ArrowLeft, Loader2, AlertCircle, RefreshCw } from 'lucide-react';
import { DynamicFormRenderer } from '../components/DynamicForm';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { usePortalAuth } from '../contexts/PortalAuthContext';
import { cn } from '../helpers/utils';
import { API_BASE_URL } from '../config/apiBase';
import type { FormTemplate, Contract, LookupOption } from '../services/api';
import type { DynamicFormData } from '../components/DynamicForm';

// Portal report submission - uses public endpoint (no auth required)
interface PortalReportPayload {
  report_type: 'incident' | 'complaint';
  title: string;
  description: string;
  location?: string;
  severity: string;
  reporter_name?: string;
  reporter_email?: string;
  reporter_phone?: string;
  department?: string;
  is_anonymous: boolean;
}

interface PortalReportResponse {
  success: boolean;
  reference_number: string;
  tracking_code: string;
  message: string;
  estimated_response: string;
}

async function submitPortalReport(payload: PortalReportPayload): Promise<PortalReportResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/portal/reports/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.message || `Submission failed: ${response.status}`);
  }
  
  return response.json();
}

// Fallback form configurations when API is unavailable
const FALLBACK_TEMPLATES: Record<string, FormTemplate> = {
  incident: {
    id: 1,
    name: 'Incident Report',
    slug: 'incident',
    description: 'Report workplace incidents and injuries',
    form_type: 'incident',
    version: 1,
    is_active: true,
    is_published: true,
    icon: 'AlertTriangle',
    color: '#ef4444',
    allow_drafts: true,
    allow_attachments: true,
    require_signature: false,
    auto_assign_reference: true,
    reference_prefix: 'INC',
    notify_on_submit: true,
    steps: [
      {
        id: 1,
        name: 'Contract Details',
        description: 'Which contract does this relate to?',
        order: 0,
        fields: [
          { id: 1, name: 'contract', label: 'Select Contract', field_type: 'select', order: 0, is_required: true, width: 'full' },
        ],
      },
      {
        id: 2,
        name: 'People & Location',
        description: 'Who was involved and where did it happen?',
        order: 1,
        fields: [
          { id: 2, name: 'was_involved', label: 'Were you directly involved?', field_type: 'toggle', order: 0, is_required: true, width: 'full', options: [{ value: 'yes', label: 'Yes' }, { value: 'no', label: 'No' }] },
          { id: 3, name: 'person_name', label: 'Full Name', field_type: 'text', order: 1, is_required: true, width: 'half', placeholder: 'Enter full name' },
          { id: 4, name: 'person_role', label: 'Role', field_type: 'select', order: 2, is_required: true, width: 'half' },
          { id: 5, name: 'person_contact', label: 'Contact Number', field_type: 'phone', order: 3, is_required: false, width: 'full', placeholder: '+44...' },
          { id: 6, name: 'location', label: 'Location', field_type: 'location', order: 4, is_required: true, width: 'full', placeholder: 'Where did this occur?' },
          { id: 7, name: 'incident_date', label: 'Date', field_type: 'date', order: 5, is_required: true, width: 'half' },
          { id: 8, name: 'incident_time', label: 'Time', field_type: 'time', order: 6, is_required: true, width: 'half' },
        ],
      },
      {
        id: 3,
        name: 'What Happened',
        description: 'Describe the incident in detail',
        order: 2,
        fields: [
          { id: 9, name: 'description', label: 'Description', field_type: 'textarea', order: 0, is_required: true, width: 'full', placeholder: 'What happened? Be as detailed as possible...', help_text: 'Tip: Use voice input to dictate your description' },
          { id: 10, name: 'asset_number', label: 'Asset / Vehicle Registration', field_type: 'text', order: 1, is_required: false, width: 'full', placeholder: 'e.g. PN22P102' },
          { id: 11, name: 'has_witnesses', label: 'Were there any witnesses?', field_type: 'toggle', order: 2, is_required: true, width: 'full', options: [{ value: 'yes', label: 'Yes' }, { value: 'no', label: 'No' }] },
          { id: 12, name: 'witness_names', label: 'Witness Names', field_type: 'textarea', order: 3, is_required: false, width: 'full', placeholder: 'Enter witness names and contact details' },
        ],
      },
      {
        id: 4,
        name: 'Injuries & Evidence',
        description: 'Document any injuries and upload evidence',
        order: 3,
        fields: [
          { id: 13, name: 'has_injuries', label: 'Any injuries sustained?', field_type: 'toggle', order: 0, is_required: true, width: 'full', options: [{ value: 'yes', label: 'Yes' }, { value: 'no', label: 'No' }] },
          { id: 14, name: 'injuries', label: 'Injury Details', field_type: 'body_map', order: 1, is_required: false, width: 'full' },
          { id: 15, name: 'medical_assistance', label: 'Medical Assistance', field_type: 'select', order: 2, is_required: false, width: 'full', options: [
            { value: 'none', label: 'No assistance needed' },
            { value: 'self', label: 'Self application' },
            { value: 'first-aider', label: 'First aider on site' },
            { value: 'ambulance', label: 'Ambulance / A&E' },
            { value: 'gp', label: 'GP / Hospital' },
          ]},
          { id: 16, name: 'photos', label: 'Upload Photos', field_type: 'image', order: 3, is_required: false, width: 'full', help_text: 'Upload photos of the scene, injuries, or damage' },
        ],
      },
    ],
  },
  'near-miss': {
    id: 2,
    name: 'Near Miss Report',
    slug: 'near-miss',
    description: 'Report close calls and near misses',
    form_type: 'near_miss',
    version: 1,
    is_active: true,
    is_published: true,
    icon: 'AlertCircle',
    color: '#f59e0b',
    allow_drafts: true,
    allow_attachments: true,
    require_signature: false,
    auto_assign_reference: true,
    reference_prefix: 'NM',
    notify_on_submit: true,
    steps: [
      {
        id: 1,
        name: 'Contract Details',
        description: 'Which contract does this relate to?',
        order: 0,
        fields: [
          { id: 1, name: 'contract', label: 'Select Contract', field_type: 'select', order: 0, is_required: true, width: 'full' },
        ],
      },
      {
        id: 2,
        name: 'Location & Time',
        description: 'Where and when did this occur?',
        order: 1,
        fields: [
          { id: 2, name: 'location', label: 'Location', field_type: 'location', order: 0, is_required: true, width: 'full' },
          { id: 3, name: 'incident_date', label: 'Date', field_type: 'date', order: 1, is_required: true, width: 'half' },
          { id: 4, name: 'incident_time', label: 'Time', field_type: 'time', order: 2, is_required: true, width: 'half' },
        ],
      },
      {
        id: 3,
        name: 'What Happened',
        description: 'Describe the near miss',
        order: 2,
        fields: [
          { id: 5, name: 'description', label: 'Description', field_type: 'textarea', order: 0, is_required: true, width: 'full', placeholder: 'Describe what happened and what could have happened...' },
          { id: 6, name: 'potential_consequences', label: 'Potential Consequences', field_type: 'textarea', order: 1, is_required: true, width: 'full', placeholder: 'What could have happened if this wasn\'t avoided?' },
          { id: 7, name: 'preventive_action', label: 'Suggested Preventive Action', field_type: 'textarea', order: 2, is_required: false, width: 'full', placeholder: 'How can this be prevented in the future?' },
          { id: 8, name: 'photos', label: 'Upload Photos', field_type: 'image', order: 3, is_required: false, width: 'full' },
        ],
      },
    ],
  },
  complaint: {
    id: 3,
    name: 'Customer Complaint',
    slug: 'complaint',
    description: 'Submit customer complaints',
    form_type: 'complaint',
    version: 1,
    is_active: true,
    is_published: true,
    icon: 'MessageSquare',
    color: '#3b82f6',
    allow_drafts: true,
    allow_attachments: true,
    require_signature: false,
    auto_assign_reference: true,
    reference_prefix: 'CMP',
    notify_on_submit: true,
    steps: [
      {
        id: 1,
        name: 'Contract Details',
        description: 'Which contract does this relate to?',
        order: 0,
        fields: [
          { id: 1, name: 'contract', label: 'Select Contract', field_type: 'select', order: 0, is_required: true, width: 'full' },
        ],
      },
      {
        id: 2,
        name: 'Complainant Details',
        description: 'Who raised this complaint?',
        order: 1,
        fields: [
          { id: 2, name: 'complainant_name', label: 'Complainant Name', field_type: 'text', order: 0, is_required: true, width: 'half' },
          { id: 3, name: 'complainant_role', label: 'Role / Title', field_type: 'text', order: 1, is_required: false, width: 'half' },
          { id: 4, name: 'complainant_contact', label: 'Contact Details', field_type: 'text', order: 2, is_required: true, width: 'full', placeholder: 'Phone or email' },
          { id: 5, name: 'complaint_date', label: 'Date of Complaint', field_type: 'date', order: 3, is_required: true, width: 'half' },
          { id: 6, name: 'location', label: 'Location / Site', field_type: 'text', order: 4, is_required: false, width: 'half' },
        ],
      },
      {
        id: 3,
        name: 'Complaint Details',
        description: 'Describe the complaint',
        order: 2,
        fields: [
          { id: 7, name: 'description', label: 'Complaint Description', field_type: 'textarea', order: 0, is_required: true, width: 'full', placeholder: 'Describe the complaint in detail...' },
          { id: 8, name: 'impact', label: 'Impact / Consequences', field_type: 'textarea', order: 1, is_required: false, width: 'full', placeholder: 'What impact has this had?' },
          { id: 9, name: 'resolution_requested', label: 'Resolution Requested', field_type: 'textarea', order: 2, is_required: false, width: 'full', placeholder: 'What resolution is the complainant seeking?' },
          { id: 10, name: 'photos', label: 'Supporting Evidence', field_type: 'file', order: 3, is_required: false, width: 'full' },
        ],
      },
    ],
  },
};

const FALLBACK_CONTRACTS: Contract[] = [
  { id: 1, name: 'UKPN', code: 'ukpn', client_name: 'UK Power Networks', is_active: true, display_order: 1 },
  { id: 2, name: 'Openreach', code: 'openreach', client_name: 'BT Group', is_active: true, display_order: 2 },
  { id: 3, name: 'Thames Water', code: 'thames-water', client_name: 'Thames Water Utilities', is_active: true, display_order: 3 },
  { id: 4, name: 'Plantexpand Ltd', code: 'plantexpand', client_name: 'Internal', is_active: true, display_order: 4 },
  { id: 5, name: 'Cadent', code: 'cadent', client_name: 'Cadent Gas', is_active: true, display_order: 5 },
  { id: 6, name: 'SGN', code: 'sgn', client_name: 'Southern Gas Networks', is_active: true, display_order: 6 },
  { id: 7, name: 'Southern Water', code: 'southern-water', client_name: 'Southern Water Services', is_active: true, display_order: 7 },
  { id: 8, name: 'Zenith', code: 'zenith', client_name: 'Zenith Vehicle Solutions', is_active: true, display_order: 8 },
  { id: 9, name: 'Novuna', code: 'novuna', client_name: 'Scottish Power', is_active: true, display_order: 9 },
  { id: 10, name: 'Enterprise', code: 'enterprise', client_name: 'Enterprise Fleet Management', is_active: true, display_order: 10 },
];

const FALLBACK_ROLES: LookupOption[] = [
  { id: 1, category: 'roles', code: 'mobile-engineer', label: 'Mobile Engineer', is_active: true, display_order: 1 },
  { id: 2, category: 'roles', code: 'workshop-pehq', label: 'Workshop (PE HQ)', is_active: true, display_order: 2 },
  { id: 3, category: 'roles', code: 'workshop-fixed', label: 'Vehicle Workshop (Fixed Customer Site)', is_active: true, display_order: 3 },
  { id: 4, category: 'roles', code: 'office', label: 'Office Based Employee', is_active: true, display_order: 4 },
  { id: 5, category: 'roles', code: 'trainee', label: 'Trainee/Apprentice', is_active: true, display_order: 5 },
  { id: 6, category: 'roles', code: 'non-pe', label: 'Non-Plantexpand Employee', is_active: true, display_order: 6 },
  { id: 7, category: 'roles', code: 'other', label: 'Other', is_active: true, display_order: 7 },
];

// Determine form type from URL
function getFormTypeFromPath(pathname: string): string {
  if (pathname.includes('near-miss')) return 'near-miss';
  if (pathname.includes('complaint')) return 'complaint';
  if (pathname.includes('rta')) return 'rta';
  return 'incident';
}

// Form type display config
const FORM_TYPE_CONFIG: Record<string, { title: string; icon: string; color: string; gradient: string }> = {
  incident: {
    title: 'Incident Report',
    icon: 'AlertTriangle',
    color: 'text-destructive',
    gradient: 'from-destructive to-orange-500',
  },
  'near-miss': {
    title: 'Near Miss Report',
    icon: 'AlertCircle',
    color: 'text-warning',
    gradient: 'from-warning to-amber-500',
  },
  complaint: {
    title: 'Customer Complaint',
    icon: 'MessageSquare',
    color: 'text-info',
    gradient: 'from-info to-cyan-500',
  },
  rta: {
    title: 'Road Traffic Collision',
    icon: 'Car',
    color: 'text-purple-600',
    gradient: 'from-purple-600 to-purple-400',
  },
};

export default function PortalDynamicForm() {
  const navigate = useNavigate();
  const location = useLocation();
  const { user } = usePortalAuth();
  const formType = getFormTypeFromPath(location.pathname);
  const config = FORM_TYPE_CONFIG[formType] || FORM_TYPE_CONFIG.incident;

  const [template, setTemplate] = useState<FormTemplate | null>(null);
  const [contracts, setContracts] = useState<Contract[]>([]);
  const [roles, setRoles] = useState<LookupOption[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Load configuration
  useEffect(() => {
    async function loadConfig() {
      setIsLoading(true);
      setError(null);

      try {
        // Try to load from API first
        // In production, this would be:
        // const [templateRes, contractsRes, rolesRes] = await Promise.all([
        //   formTemplatesApi.getBySlug(formType),
        //   contractsApi.list(true),
        //   lookupsApi.list('roles', true),
        // ]);

        // For now, use fallbacks with simulated delay
        await new Promise(resolve => setTimeout(resolve, 300));

        setTemplate(FALLBACK_TEMPLATES[formType] || FALLBACK_TEMPLATES.incident);
        setContracts(FALLBACK_CONTRACTS);
        setRoles(FALLBACK_ROLES);
      } catch (err) {
        console.error('Failed to load form configuration:', err);
        // Fall back to local config
        setTemplate(FALLBACK_TEMPLATES[formType] || FALLBACK_TEMPLATES.incident);
        setContracts(FALLBACK_CONTRACTS);
        setRoles(FALLBACK_ROLES);
      } finally {
        setIsLoading(false);
      }
    }

    loadConfig();
  }, [formType]);

  // Pre-fill user data
  const initialData: DynamicFormData = user ? {
    person_name: user.name,
    person_contact: user.email,
    incident_date: new Date().toISOString().split('T')[0],
    incident_time: new Date().toTimeString().slice(0, 5),
    complaint_date: new Date().toISOString().split('T')[0],
  } : {
    incident_date: new Date().toISOString().split('T')[0],
    incident_time: new Date().toTimeString().slice(0, 5),
    complaint_date: new Date().toISOString().split('T')[0],
  };

  const handleSubmit = async (formData: DynamicFormData): Promise<{ reference_number: string }> => {
    // Debug: log what we received
    console.log('[PortalDynamicForm] Form data received:', formData);
    
    // Build the portal report payload from dynamic form data
    const reportType = formType === 'complaint' ? 'complaint' : 'incident';
    
    // Extract description - try multiple possible field names
    const descriptionRaw = formData.description || 
                          formData.complaint_description || 
                          formData.full_description ||
                          formData.what_happened ||
                          '';
    // Ensure minimum length for API validation (10 chars required)
    const description = String(descriptionRaw).trim().length >= 10 
      ? String(descriptionRaw).trim()
      : `${template?.name || 'Report'} submitted via portal. ${String(descriptionRaw || 'No additional details provided.')}`;
    
    // Build a descriptive title (minimum 5 chars required)
    const contractName = formData.contract ? String(formData.contract) : '';
    const locationName = formData.location ? String(formData.location) : '';
    const titleSuffix = contractName || locationName || 'Report';
    const title = `${template?.name || 'Incident Report'} - ${titleSuffix}`.substring(0, 200);
    
    const payload: PortalReportPayload = {
      report_type: reportType,
      title: title.length >= 5 ? title : `${template?.name || 'Report'} - Submitted`,
      description: description,
      location: formData.location ? String(formData.location) : undefined,
      severity: formData.severity ? String(formData.severity) : 'medium',
      reporter_name: formData.person_name ? String(formData.person_name) : 
                     formData.complainant_name ? String(formData.complainant_name) : 
                     user?.name,
      // CRITICAL: reporter_email MUST match authenticated user's email for My Reports linkage
      // Always use the authenticated user's email, not form input (which may be a phone number)
      reporter_email: user?.email || undefined,
      reporter_phone: formData.complainant_contact ? String(formData.complainant_contact) : undefined,
      department: formData.contract ? String(formData.contract) : undefined,
      is_anonymous: false,
    };
    
    console.log('[PortalDynamicForm] Submitting payload:', payload);
    
    // Call the real API
    const result = await submitPortalReport(payload);
    
    console.log('[PortalDynamicForm] API response:', result);
    
    // Store tracking code for later access
    if (result.tracking_code) {
      sessionStorage.setItem(`tracking_${result.reference_number}`, result.tracking_code);
    }
    
    return { reference_number: result.reference_number };
  };

  const handleCancel = () => {
    navigate('/portal/report');
  };

  const handleRetry = () => {
    setError(null);
    setIsLoading(true);
    // Reload will trigger useEffect
    window.location.reload();
  };

  // Loading state
  if (isLoading) {
    return (
      <div className="min-h-screen bg-surface flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-12 h-12 animate-spin text-primary mx-auto mb-4" />
          <p className="text-muted-foreground">Loading form...</p>
        </div>
      </div>
    );
  }

  // Error state
  if (error || !template) {
    return (
      <div className="min-h-screen bg-surface flex items-center justify-center p-4">
        <Card className="max-w-md w-full p-8 text-center">
          <AlertCircle className="w-12 h-12 text-destructive mx-auto mb-4" />
          <h2 className="text-xl font-bold text-foreground mb-2">Unable to Load Form</h2>
          <p className="text-muted-foreground mb-6">
            {error || 'Form configuration could not be loaded. Please try again.'}
          </p>
          <div className="flex gap-3 justify-center">
            <Button variant="outline" onClick={handleCancel}>
              Go Back
            </Button>
            <Button onClick={handleRetry}>
              <RefreshCw className="w-4 h-4 mr-2" />
              Retry
            </Button>
          </div>
        </Card>
      </div>
    );
  }

  const contractOptions = contracts.map(c => ({
    value: c.code,
    label: c.name,
    sublabel: c.client_name,
  }));

  const roleOptions = roles.map(r => ({
    value: r.code,
    label: r.label,
  }));

  return (
    <div className="min-h-screen bg-surface">
      {/* Header */}
      <header className="bg-card/95 backdrop-blur-lg border-b border-border sticky top-0 z-40">
        <div className="max-w-2xl mx-auto px-4 sm:px-6 py-4 flex items-center gap-4">
          <button
            onClick={handleCancel}
            className="w-10 h-10 flex items-center justify-center rounded-xl bg-surface hover:bg-muted transition-colors"
          >
            <ArrowLeft className="w-5 h-5 text-foreground" />
          </button>
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <span className={cn('font-semibold text-foreground')}>{config.title}</span>
            </div>
            <div className="text-xs text-muted-foreground">
              v{template.version} • {template.steps.length} steps
            </div>
          </div>
        </div>
      </header>

      {/* Form Content */}
      <main className="max-w-2xl mx-auto px-4 sm:px-6 py-6 pb-24">
        <DynamicFormRenderer
          template={template}
          initialData={initialData}
          onSubmit={handleSubmit}
          onCancel={handleCancel}
          contractOptions={contractOptions}
          roleOptions={roleOptions}
        />
      </main>
    </div>
  );
}
