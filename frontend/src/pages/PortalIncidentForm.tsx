import { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  ArrowLeft,
  AlertTriangle,
  AlertCircle,
  MessageSquare,
  MapPin,
  Camera,
  Mic,
  MicOff,
  Calendar,
  Clock,
  User,
  Building,
  Phone,
  Check,
  ChevronRight,
  ChevronLeft,
  Loader2,
  Truck,
  Users,
  X,
  AlertCircle as AlertIcon,
} from 'lucide-react';
import FuzzySearchDropdown from '../components/FuzzySearchDropdown';
import BodyInjurySelector, { InjurySelection } from '../components/BodyInjurySelector';
import { usePortalAuth } from '../contexts/PortalAuthContext';
import { useGeolocation } from '../hooks/useGeolocation';
import { useVoiceToText } from '../hooks/useVoiceToText';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { Textarea } from '../components/ui/Textarea';
import { cn } from '../helpers/utils';
import { API_BASE_URL } from '../config/apiBase';

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

// Determine report type from URL path
const getReportTypeFromPath = (pathname: string) => {
  if (pathname.includes('near-miss')) return 'near-miss';
  if (pathname.includes('complaint')) return 'complaint';
  return 'incident';
};

// Report type configurations
const REPORT_CONFIGS = {
  'incident': {
    title: 'Incident Report',
    subtitle: 'Injury or Accident',
    icon: AlertTriangle,
    colorClass: 'text-destructive',
    bgClass: 'bg-destructive/10',
    gradientFrom: 'from-destructive',
    gradientTo: 'to-orange-500',
  },
  'near-miss': {
    title: 'Near Miss Report',
    subtitle: 'Close Call',
    icon: AlertCircle,
    colorClass: 'text-warning',
    bgClass: 'bg-warning/10',
    gradientFrom: 'from-warning',
    gradientTo: 'to-amber-500',
  },
  'complaint': {
    title: 'Customer Complaint',
    subtitle: 'Customer Concern',
    icon: MessageSquare,
    colorClass: 'text-info',
    bgClass: 'bg-info/10',
    gradientFrom: 'from-info',
    gradientTo: 'to-cyan-500',
  },
};

// Contract options
const CONTRACT_OPTIONS = [
  { value: 'ukpn', label: 'UKPN', sublabel: 'UK Power Networks' },
  { value: 'openreach', label: 'Openreach', sublabel: 'BT Group' },
  { value: 'thames-water', label: 'Thames Water', sublabel: 'Water & Sewerage' },
  { value: 'plantexpand', label: 'Plantexpand Ltd', sublabel: 'Internal' },
  { value: 'cadent', label: 'Cadent', sublabel: 'Gas Distribution' },
  { value: 'sgn', label: 'SGN', sublabel: 'Southern Gas Networks' },
  { value: 'southern-water', label: 'Southern Water', sublabel: 'Water Services' },
  { value: 'zenith', label: 'Zenith', sublabel: 'Fleet Management' },
  { value: 'novuna', label: 'Novuna', sublabel: 'Scottish Power' },
  { value: 'enterprise', label: 'Enterprise', sublabel: 'Fleet Solutions' },
  { value: 'other', label: 'Other', sublabel: 'Specify below' },
];

// Role options
const ROLE_OPTIONS = [
  { value: 'mobile-engineer', label: 'Mobile Engineer' },
  { value: 'workshop-pehq', label: 'Workshop (PE HQ)' },
  { value: 'workshop-fixed', label: 'Vehicle Workshop (Fixed Customer Site)' },
  { value: 'office', label: 'Office Based Employee' },
  { value: 'trainee', label: 'Trainee/Apprentice' },
  { value: 'non-pe', label: 'Non-Plantexpand Employee' },
  { value: 'other', label: 'Other' },
];

// Medical assistance options
const MEDICAL_OPTIONS = [
  { value: 'none', label: 'No assistance needed' },
  { value: 'self', label: 'Self application' },
  { value: 'first-aider', label: 'First aider on site' },
  { value: 'ambulance', label: 'Ambulance / A&E' },
  { value: 'gp', label: 'GP / Hospital' },
];

type Step = 1 | 2 | 3 | 4;

interface FormData {
  contract: string;
  contractOther: string;
  wasInvolved: boolean | null;
  personName: string;
  personRole: string;
  personContact: string;
  location: string;
  incidentDate: string;
  incidentTime: string;
  description: string;
  assetNumber: string;
  hasWitnesses: boolean | null;
  witnessNames: string;
  hasInjuries: boolean | null;
  injuries: InjurySelection[];
  medicalAssistance: string;
  complainantName: string;
  complainantRole: string;
  complainantContact: string;
  photos: File[];
}

export default function PortalIncidentForm() {
  const navigate = useNavigate();
  const location = useLocation();
  const { user } = usePortalAuth();
  const reportType = getReportTypeFromPath(location.pathname);
  const config = REPORT_CONFIGS[reportType];
  
  const [step, setStep] = useState<Step>(1);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submittedRef, setSubmittedRef] = useState<string | null>(null);
  const [locationError, setLocationError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Geolocation hook
  const { isLoading: geolocating, error: geoError, getLocationString } = useGeolocation();

  // Voice-to-text hook
  const { isListening: isRecording, isSupported: voiceSupported, toggleListening, error: voiceError } = useVoiceToText({
    onResult: (transcript) => {
      setFormData((prev) => ({
        ...prev,
        description: prev.description + (prev.description ? ' ' : '') + transcript,
      }));
    },
  });

  const [formData, setFormData] = useState<FormData>({
    contract: '',
    contractOther: '',
    wasInvolved: null,
    personName: '',
    personRole: '',
    personContact: '',
    location: '',
    incidentDate: new Date().toISOString().split('T')[0],
    incidentTime: new Date().toTimeString().slice(0, 5),
    description: '',
    assetNumber: '',
    hasWitnesses: null,
    witnessNames: '',
    hasInjuries: null,
    injuries: [],
    medicalAssistance: '',
    complainantName: '',
    complainantRole: '',
    complainantContact: '',
    photos: [],
  });

  // Pre-fill user details from SSO
  useEffect(() => {
    if (user) {
      setFormData((prev) => ({
        ...prev,
        personName: user.name || '',
        personRole: user.jobTitle || '',
        personContact: user.email || '',
      }));
    }
  }, [user]);

  const totalSteps = reportType === 'complaint' ? 3 : 4;

  // GPS location detection using hook
  const detectLocation = async () => {
    setLocationError(null);
    const locationString = await getLocationString();
    if (locationString) {
      setFormData((prev) => ({ ...prev, location: locationString }));
    } else if (geoError) {
      setLocationError(geoError);
    }
  };

  // Voice recording using Web Speech API hook
  const toggleVoiceRecording = () => {
    if (voiceSupported) {
      toggleListening();
    }
  };

  // Photo handling
  const handlePhotoCapture = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const newPhotos = Array.from(e.target.files);
      setFormData((prev) => ({ ...prev, photos: [...prev.photos, ...newPhotos] }));
    }
  };

  const removePhoto = (index: number) => {
    setFormData((prev) => ({
      ...prev,
      photos: prev.photos.filter((_, i) => i !== index),
    }));
  };

  // Form submission - uses public portal endpoint (no auth required)
  const handleSubmit = async () => {
    setIsSubmitting(true);
    setError(null);
    
    try {
      // Determine severity based on form data
      const severity = formData.hasInjuries && formData.medicalAssistance === 'ambulance' ? 'critical' :
        formData.hasInjuries ? 'high' : 
        reportType === 'near-miss' ? 'low' : 'medium';
      
      // Build portal report payload
      const payload: PortalReportPayload = {
        report_type: reportType === 'complaint' ? 'complaint' : 'incident',
        title: reportType === 'complaint' 
          ? `Complaint - ${formData.contract} - ${formData.location}`
          : `${reportType === 'near-miss' ? 'Near Miss' : 'Incident'} - ${formData.contract} - ${formData.location}`,
        description: formData.description,
        location: formData.location || undefined,
        severity: severity,
        reporter_name: reportType === 'complaint' ? formData.complainantName : formData.personName,
        reporter_email: user?.email || undefined,
        reporter_phone: formData.complainantContact || undefined,
        department: formData.contract !== 'other' ? formData.contract : formData.contractOther,
        is_anonymous: false, // Portal users are identified
      };
      
      const response = await submitPortalReport(payload);
      setSubmittedRef(response.reference_number);
      // Store tracking code for anonymous access if needed
      if (response.tracking_code) {
        sessionStorage.setItem(`tracking_${response.reference_number}`, response.tracking_code);
      }
    } catch (error) {
      console.error('Submission error:', error);
      // Show real error - do NOT generate fake reference numbers
      setError(error instanceof Error ? error.message : 'Failed to submit report. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  // Step validation
  const canProceed = (): boolean => {
    switch (step) {
      case 1:
        return !!formData.contract;
      case 2:
        if (reportType === 'complaint') {
          return !!formData.complainantName && !!formData.location;
        }
        return formData.wasInvolved !== null && !!formData.personName && !!formData.location;
      case 3:
        return !!formData.description;
      case 4:
        return true;
      default:
        return false;
    }
  };

  // Success screen
  if (submittedRef) {
    return (
      <div className="min-h-screen bg-surface flex items-center justify-center p-4">
        <Card className="p-8 max-w-md w-full text-center">
          <div className="w-20 h-20 bg-success/10 rounded-full flex items-center justify-center mx-auto mb-6">
            <Check className="w-10 h-10 text-success" />
          </div>
          <h1 className="text-2xl font-bold text-foreground mb-2">Report Submitted</h1>
          <p className="text-muted-foreground mb-6">Your reference number is:</p>
          <div className="bg-surface border border-border rounded-xl px-6 py-4 mb-6">
            <span className="text-2xl font-mono font-bold text-primary">{submittedRef}</span>
          </div>
          <div className="flex gap-3">
            <Button
              onClick={() => navigate('/portal/track/' + submittedRef)}
              className="flex-1"
            >
              Track Status
            </Button>
            <Button
              variant="outline"
              onClick={() => navigate('/portal')}
              className="flex-1"
            >
              Done
            </Button>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-surface">
      {/* Header */}
      <header className="bg-card/95 backdrop-blur-lg border-b border-border sticky top-0 z-40">
        <div className="max-w-lg mx-auto px-4 sm:px-6 py-4 flex items-center gap-4">
          <button
            onClick={() => step === 1 ? navigate('/portal/report') : setStep((s) => (s - 1) as Step)}
            className="w-10 h-10 flex items-center justify-center rounded-xl bg-surface hover:bg-muted transition-colors"
          >
            <ArrowLeft className="w-5 h-5 text-foreground" />
          </button>
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <config.icon className={cn('w-5 h-5', config.colorClass)} />
              <span className="font-semibold text-foreground">{config.title}</span>
            </div>
            <div className="text-xs text-muted-foreground">Step {step} of {totalSteps}</div>
          </div>
        </div>
        
        {/* Progress bar */}
        <div className="h-1 bg-border">
          <div
            className={cn('h-full transition-all duration-300 bg-gradient-to-r', config.gradientFrom, config.gradientTo)}
            style={{ width: `${(step / totalSteps) * 100}%` }}
          />
        </div>
      </header>

      <main className="max-w-lg mx-auto px-4 sm:px-6 py-6 pb-28">
        {/* Step 1: Contract */}
        {step === 1 && (
          <div className="space-y-6">
            <div>
              <h1 className="text-xl font-bold text-foreground mb-1">Contract Details</h1>
              <p className="text-muted-foreground text-sm">Which contract does this relate to?</p>
            </div>

            <FuzzySearchDropdown
              label="Select Contract"
              options={CONTRACT_OPTIONS}
              value={formData.contract}
              onChange={(val) => setFormData((prev) => ({ ...prev, contract: val }))}
              placeholder="Search or select contract..."
              required
            />

            {formData.contract === 'other' && (
              <Input
                value={formData.contractOther}
                onChange={(e) => setFormData((prev) => ({ ...prev, contractOther: e.target.value }))}
                placeholder="Specify contract..."
              />
            )}
          </div>
        )}

        {/* Step 2: Person & Location */}
        {step === 2 && (
          <div className="space-y-5">
            <div>
              <h1 className="text-xl font-bold text-foreground mb-1">
                {reportType === 'complaint' ? 'Complainant Details' : 'People & Location'}
              </h1>
              <p className="text-muted-foreground text-sm">
                {reportType === 'complaint' ? 'Who raised the complaint?' : 'Who was involved and where?'}
              </p>
            </div>

            {reportType !== 'complaint' && (
              <>
                {/* Were you involved? */}
                <div>
                  <label className="block text-sm font-medium text-foreground mb-2">
                    Were you directly involved?
                  </label>
                  <div className="grid grid-cols-2 gap-3">
                    {[true, false].map((val) => (
                      <button
                        key={String(val)}
                        type="button"
                        onClick={() => setFormData((prev) => ({ ...prev, wasInvolved: val }))}
                        className={cn(
                          'px-4 py-3 rounded-xl border-2 font-medium transition-all',
                          formData.wasInvolved === val
                            ? 'bg-primary/10 border-primary text-primary'
                            : 'bg-card border-border text-foreground hover:border-border-strong'
                        )}
                      >
                        {val ? 'Yes' : 'No'}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Person Name */}
                <div>
                  <label className="block text-sm font-medium text-foreground mb-2">
                    {formData.wasInvolved ? 'Your Name' : 'Name of Person Involved'} *
                  </label>
                  <div className="relative">
                    <User className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                    <Input
                      value={formData.personName}
                      onChange={(e) => setFormData((prev) => ({ ...prev, personName: e.target.value }))}
                      placeholder="Full name..."
                      className="pl-10"
                    />
                  </div>
                </div>

                {/* Role */}
                <FuzzySearchDropdown
                  label="Role"
                  options={ROLE_OPTIONS}
                  value={formData.personRole}
                  onChange={(val) => setFormData((prev) => ({ ...prev, personRole: val }))}
                  placeholder="Select role..."
                />
              </>
            )}

            {reportType === 'complaint' && (
              <>
                {/* Complainant Name */}
                <div>
                  <label className="block text-sm font-medium text-foreground mb-2">Complainant Name *</label>
                  <div className="relative">
                    <User className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                    <Input
                      value={formData.complainantName}
                      onChange={(e) => setFormData((prev) => ({ ...prev, complainantName: e.target.value }))}
                      placeholder="Full name..."
                      className="pl-10"
                    />
                  </div>
                </div>

                {/* Complainant Role */}
                <div>
                  <label className="block text-sm font-medium text-foreground mb-2">Their Role/Title</label>
                  <div className="relative">
                    <Building className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                    <Input
                      value={formData.complainantRole}
                      onChange={(e) => setFormData((prev) => ({ ...prev, complainantRole: e.target.value }))}
                      placeholder="e.g. Site Manager..."
                      className="pl-10"
                    />
                  </div>
                </div>

                {/* Complainant Contact */}
                <div>
                  <label className="block text-sm font-medium text-foreground mb-2">Contact Details</label>
                  <div className="relative">
                    <Phone className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                    <Input
                      value={formData.complainantContact}
                      onChange={(e) => setFormData((prev) => ({ ...prev, complainantContact: e.target.value }))}
                      placeholder="Phone or email..."
                      className="pl-10"
                    />
                  </div>
                </div>
              </>
            )}

            {/* Location */}
            <div>
              <label className="block text-sm font-medium text-foreground mb-2">Location *</label>
              <div className="relative">
                <MapPin className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                <Input
                  value={formData.location}
                  onChange={(e) => {
                    setFormData((prev) => ({ ...prev, location: e.target.value }));
                    setLocationError(null);
                  }}
                  placeholder="Where did this occur?"
                  className="pl-10 pr-16"
                />
                <button
                  type="button"
                  onClick={detectLocation}
                  disabled={geolocating}
                  className="absolute right-2 top-1/2 -translate-y-1/2 px-3 py-1.5 bg-primary/10 text-primary rounded-lg text-sm font-medium hover:bg-primary/20 transition-colors disabled:opacity-50"
                >
                  {geolocating ? <Loader2 className="w-4 h-4 animate-spin" /> : 'GPS'}
                </button>
              </div>
              {(locationError || geoError) && (
                <div className="mt-2 flex items-start gap-2 text-sm text-destructive">
                  <AlertIcon className="w-4 h-4 mt-0.5 flex-shrink-0" />
                  <span>{locationError || geoError}</span>
                </div>
              )}
              <p className="mt-1 text-xs text-muted-foreground">
                Tap GPS to auto-detect, or type manually
              </p>
            </div>

            {/* Date & Time */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm font-medium text-foreground mb-2">Date</label>
                <div className="relative">
                  <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                  <Input
                    type="date"
                    value={formData.incidentDate}
                    onChange={(e) => setFormData((prev) => ({ ...prev, incidentDate: e.target.value }))}
                    className="pl-10"
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-foreground mb-2">Time</label>
                <div className="relative">
                  <Clock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                  <Input
                    type="time"
                    value={formData.incidentTime}
                    onChange={(e) => setFormData((prev) => ({ ...prev, incidentTime: e.target.value }))}
                    className="pl-10"
                  />
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Step 3: Description & Details */}
        {step === 3 && (
          <div className="space-y-5">
            <div>
              <h1 className="text-xl font-bold text-foreground mb-1">What Happened?</h1>
              <p className="text-muted-foreground text-sm">Describe the {reportType === 'complaint' ? 'complaint' : 'incident'} in detail</p>
            </div>

            {/* Description */}
            <div>
              <label className="block text-sm font-medium text-foreground mb-2">Description *</label>
              <div className="relative">
                <Textarea
                  value={formData.description}
                  onChange={(e) => setFormData((prev) => ({ ...prev, description: e.target.value }))}
                  placeholder="What happened? Be specific..."
                  rows={5}
                />
                {voiceSupported && (
                  <button
                    type="button"
                    onClick={toggleVoiceRecording}
                    title={isRecording ? 'Stop recording' : 'Start voice input'}
                    className={cn(
                      'absolute right-3 bottom-3 p-2 rounded-full transition-colors',
                      isRecording ? 'bg-destructive text-destructive-foreground animate-pulse' : 'bg-primary/10 text-primary hover:bg-primary/20'
                    )}
                  >
                    {isRecording ? <MicOff className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
                  </button>
                )}
              </div>
              {isRecording && (
                <div className="mt-2 flex items-center gap-2 text-sm text-primary animate-pulse">
                  <div className="w-2 h-2 bg-destructive rounded-full" />
                  <span>Listening... speak now</span>
                </div>
              )}
              {voiceError && (
                <div className="mt-2 flex items-start gap-2 text-sm text-destructive">
                  <AlertIcon className="w-4 h-4 mt-0.5 flex-shrink-0" />
                  <span>{voiceError}</span>
                </div>
              )}
              <p className="mt-1 text-xs text-muted-foreground">
                {voiceSupported ? 'Type or tap the microphone to dictate' : 'Type your description'}
              </p>
            </div>

            {/* Asset Number */}
            <div>
              <label className="block text-sm font-medium text-foreground mb-2">Asset / Vehicle Registration</label>
              <div className="relative">
                <Truck className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                <Input
                  value={formData.assetNumber}
                  onChange={(e) => setFormData((prev) => ({ ...prev, assetNumber: e.target.value.toUpperCase() }))}
                  placeholder="e.g. PN22P102..."
                  className="pl-10 uppercase"
                />
              </div>
            </div>

            {/* Witnesses */}
            <div>
              <label className="block text-sm font-medium text-foreground mb-2">Any witnesses?</label>
              <div className="grid grid-cols-2 gap-3">
                {[true, false].map((val) => (
                  <button
                    key={String(val)}
                    type="button"
                    onClick={() => setFormData((prev) => ({ ...prev, hasWitnesses: val }))}
                    className={cn(
                      'px-4 py-3 rounded-xl border-2 font-medium transition-all',
                      formData.hasWitnesses === val
                        ? 'bg-primary/10 border-primary text-primary'
                        : 'bg-card border-border text-foreground hover:border-border-strong'
                    )}
                  >
                    {val ? 'Yes' : 'No'}
                  </button>
                ))}
              </div>
            </div>

            {formData.hasWitnesses && (
              <div>
                <label className="block text-sm font-medium text-foreground mb-2">Witness Names</label>
                <div className="relative">
                  <Users className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                  <Input
                    value={formData.witnessNames}
                    onChange={(e) => setFormData((prev) => ({ ...prev, witnessNames: e.target.value }))}
                    placeholder="Names of witnesses..."
                    className="pl-10"
                  />
                </div>
              </div>
            )}
          </div>
        )}

        {/* Step 4: Injuries & Photos (incident only) */}
        {step === 4 && reportType !== 'complaint' && (
          <div className="space-y-5">
            <div>
              <h1 className="text-xl font-bold text-foreground mb-1">Injuries & Evidence</h1>
              <p className="text-muted-foreground text-sm">Any injuries and supporting photos</p>
            </div>

            {/* Injuries */}
            <div>
              <label className="block text-sm font-medium text-foreground mb-2">Any injuries sustained?</label>
              <div className="grid grid-cols-2 gap-3">
                {[true, false].map((val) => (
                  <button
                    key={String(val)}
                    type="button"
                    onClick={() => setFormData((prev) => ({ ...prev, hasInjuries: val }))}
                    className={cn(
                      'px-4 py-3 rounded-xl border-2 font-medium transition-all',
                      formData.hasInjuries === val
                        ? val ? 'bg-destructive/10 border-destructive text-destructive' : 'bg-success/10 border-success text-success'
                        : 'bg-card border-border text-foreground hover:border-border-strong'
                    )}
                  >
                    {val ? 'Yes' : 'No'}
                  </button>
                ))}
              </div>
            </div>

            {formData.hasInjuries && (
              <>
                {/* Interactive Body Diagram */}
                <BodyInjurySelector
                  injuries={formData.injuries}
                  onChange={(injuries) => setFormData((prev) => ({ ...prev, injuries }))}
                />

                {/* Medical Assistance */}
                <FuzzySearchDropdown
                  label="Medical assistance required?"
                  options={MEDICAL_OPTIONS}
                  value={formData.medicalAssistance}
                  onChange={(val) => setFormData((prev) => ({ ...prev, medicalAssistance: val }))}
                  placeholder="Select..."
                />
              </>
            )}

            {/* Photos */}
            <div>
              <label className="block text-sm font-medium text-foreground mb-2">Photos</label>
              <div className="grid grid-cols-4 gap-2">
                {formData.photos.map((photo, index) => (
                  <div key={index} className="relative aspect-square">
                    <img
                      src={URL.createObjectURL(photo)}
                      alt={`Photo ${index + 1}`}
                      className="w-full h-full object-cover rounded-xl"
                    />
                    <button
                      type="button"
                      onClick={() => removePhoto(index)}
                      className="absolute -top-1 -right-1 w-5 h-5 bg-destructive text-destructive-foreground rounded-full flex items-center justify-center"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </div>
                ))}
                <label className="aspect-square flex flex-col items-center justify-center bg-surface border-2 border-dashed border-border rounded-xl cursor-pointer hover:border-primary/30 transition-colors">
                  <Camera className="w-6 h-6 text-muted-foreground" />
                  <span className="text-xs text-muted-foreground mt-1">Add</span>
                  <input
                    type="file"
                    accept="image/*"
                    capture="environment"
                    onChange={handlePhotoCapture}
                    className="hidden"
                    multiple
                  />
                </label>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Fixed Bottom Navigation */}
      <div className="fixed bottom-0 left-0 right-0 bg-card/95 backdrop-blur-lg border-t border-border p-4">
        <div className="max-w-lg mx-auto">
          {/* Error display */}
          {error && (
            <div className="mb-3 p-3 bg-destructive/10 border border-destructive/30 rounded-lg flex items-start gap-2">
              <AlertIcon className="w-5 h-5 text-destructive flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-medium text-destructive">Submission Failed</p>
                <p className="text-sm text-destructive/80">{error}</p>
              </div>
              <button 
                onClick={() => setError(null)} 
                className="ml-auto text-destructive/60 hover:text-destructive"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          )}
        </div>
        <div className="max-w-lg mx-auto flex gap-3">
          {step > 1 && (
            <Button
              variant="outline"
              onClick={() => setStep((s) => (s - 1) as Step)}
            >
              <ChevronLeft className="w-5 h-5" />
              Back
            </Button>
          )}
          
          {step < totalSteps ? (
            <Button
              onClick={() => setStep((s) => (s + 1) as Step)}
              disabled={!canProceed()}
              className="flex-1"
            >
              Continue
              <ChevronRight className="w-5 h-5" />
            </Button>
          ) : (
            <Button
              onClick={handleSubmit}
              disabled={isSubmitting}
              className="flex-1 bg-success hover:bg-success/90"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  Submitting...
                </>
              ) : (
                <>
                  <Check className="w-5 h-5" />
                  Submit
                </>
              )}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
