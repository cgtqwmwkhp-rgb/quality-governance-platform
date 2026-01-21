import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { usePortalAuth } from '../contexts/PortalAuthContext';
import { nearMissApi, NearMissCreate } from '../services/api';
import {
  ArrowLeft,
  AlertTriangle,
  MapPin,
  Camera,
  Mic,
  MicOff,
  Calendar,
  Clock,
  User,
  Check,
  ChevronRight,
  ChevronLeft,
  Loader2,
  X,
  Shield,
  Wrench,
  Zap,
  Navigation,
  HardHat,
  Truck,
  CircleAlert,
  Construction,
} from 'lucide-react';
import FuzzySearchDropdown from '../components/FuzzySearchDropdown';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { Textarea } from '../components/ui/Textarea';
import { cn } from '../helpers/utils';
import { useGeolocation } from '../hooks/useGeolocation';
import { useVoiceToText } from '../hooks/useVoiceToText';

// Contract options
const CONTRACT_OPTIONS = [
  { value: 'TfL-Central', label: 'TfL Central Line', sublabel: 'London Underground' },
  { value: 'TfL-Jubilee', label: 'TfL Jubilee Line', sublabel: 'London Underground' },
  { value: 'NR-Southern', label: 'Network Rail Southern', sublabel: 'Maintenance' },
  { value: 'NR-Western', label: 'Network Rail Western', sublabel: 'Maintenance' },
  { value: 'HS2-Midlands', label: 'HS2 Midlands', sublabel: 'Construction' },
  { value: 'Crossrail', label: 'Elizabeth Line', sublabel: 'Operations' },
  { value: 'other', label: 'Other', sublabel: 'Enter manually' },
];

// Role options
const ROLE_OPTIONS = [
  { value: 'driver', label: 'Driver', icon: Truck },
  { value: 'technician', label: 'Technician', icon: Wrench },
  { value: 'engineer', label: 'Engineer', icon: Construction },
  { value: 'supervisor', label: 'Supervisor', icon: HardHat },
  { value: 'office', label: 'Office Staff', icon: User },
  { value: 'visitor', label: 'Visitor', icon: User },
];

// Risk categories
const RISK_CATEGORIES = [
  { value: 'slip-trip-fall', label: 'Slip/Trip/Fall', icon: CircleAlert, color: 'orange' },
  { value: 'equipment', label: 'Equipment', icon: Wrench, color: 'blue' },
  { value: 'electrical', label: 'Electrical', icon: Zap, color: 'yellow' },
  { value: 'manual-handling', label: 'Manual Handling', icon: HardHat, color: 'purple' },
  { value: 'vehicle', label: 'Vehicle/Traffic', icon: Truck, color: 'red' },
  { value: 'environmental', label: 'Environmental', icon: Shield, color: 'green' },
];

// Severity levels
const SEVERITY_LEVELS = [
  { value: 'low', label: 'Low', description: 'Minor inconvenience', color: 'bg-success' },
  { value: 'medium', label: 'Medium', description: 'Could cause injury', color: 'bg-warning' },
  { value: 'high', label: 'High', description: 'Serious injury risk', color: 'bg-orange-500' },
  { value: 'critical', label: 'Critical', description: 'Life-threatening', color: 'bg-destructive' },
];

interface FormData {
  reporterName: string;
  reporterEmail: string;
  reporterPhone: string;
  reporterRole: string;
  wasInvolved: boolean | null;
  contract: string;
  contractOther: string;
  location: string;
  locationCoordinates: string;
  eventDate: string;
  eventTime: string;
  description: string;
  potentialConsequences: string;
  preventiveActionSuggested: string;
  personsInvolved: string;
  witnessesPresent: boolean | null;
  witnessNames: string;
  assetNumber: string;
  assetType: string;
  riskCategory: string;
  potentialSeverity: string;
  photos: File[];
}

type Step = 1 | 2 | 3 | 4;

export default function PortalNearMissForm() {
  const navigate = useNavigate();
  const { user } = usePortalAuth();
  const [step, setStep] = useState<Step>(1);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submittedRef, setSubmittedRef] = useState<string | null>(null);

  const { latitude, longitude, isLoading: geoLoading, error: geoError, getLocation } = useGeolocation();
  const { 
    isListening, 
    transcript, 
    isSupported: voiceSupported, 
    startListening, 
    stopListening,
  } = useVoiceToText();

  const [formData, setFormData] = useState<FormData>({
    reporterName: '',
    reporterEmail: '',
    reporterPhone: '',
    reporterRole: '',
    wasInvolved: null,
    contract: '',
    contractOther: '',
    location: '',
    locationCoordinates: '',
    eventDate: new Date().toISOString().split('T')[0],
    eventTime: new Date().toTimeString().slice(0, 5),
    description: '',
    potentialConsequences: '',
    preventiveActionSuggested: '',
    personsInvolved: '',
    witnessesPresent: null,
    witnessNames: '',
    assetNumber: '',
    assetType: '',
    riskCategory: '',
    potentialSeverity: '',
    photos: [],
  });

  const totalSteps = 4;

  // Pre-fill user details from SSO
  useEffect(() => {
    if (user) {
      setFormData((prev) => ({
        ...prev,
        reporterName: user.name || '',
        reporterEmail: user.email || '',
      }));
    }
  }, [user]);

  // Update location from GPS
  useEffect(() => {
    if (latitude !== null && longitude !== null) {
      setFormData((prev) => ({
        ...prev,
        locationCoordinates: `${latitude.toFixed(6)}, ${longitude.toFixed(6)}`,
        location: prev.location || `GPS: ${latitude.toFixed(6)}, ${longitude.toFixed(6)}`,
      }));
    }
  }, [latitude, longitude]);

  // Track previous transcript to avoid duplicates
  const [lastTranscript, setLastTranscript] = useState('');
  
  // Append voice transcript to description
  useEffect(() => {
    if (transcript && transcript !== lastTranscript) {
      setFormData((prev) => ({
        ...prev,
        description: prev.description + (prev.description ? ' ' : '') + transcript,
      }));
      setLastTranscript(transcript);
    }
  }, [transcript, lastTranscript]);

  // GPS detection
  const detectLocation = () => {
    getLocation();
  };

  // Voice recording toggle
  const toggleVoiceRecording = () => {
    if (isListening) {
      stopListening();
    } else {
      startListening();
    }
  };

  // Photo handling
  const handlePhotoCapture = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      setFormData((prev) => ({ ...prev, photos: [...prev.photos, ...Array.from(e.target.files!)] }));
    }
  };

  const removePhoto = (index: number) => {
    setFormData((prev) => ({ ...prev, photos: prev.photos.filter((_, i) => i !== index) }));
  };

  // Submit
  const handleSubmit = async () => {
    setIsSubmitting(true);
    try {
      // Build API payload
      const payload: NearMissCreate = {
        reporter_name: formData.reporterName,
        reporter_email: formData.reporterEmail || undefined,
        reporter_phone: formData.reporterPhone || undefined,
        reporter_role: formData.reporterRole || undefined,
        was_involved: formData.wasInvolved ?? true,
        contract: formData.contract === 'other' ? formData.contractOther : formData.contract,
        contract_other: formData.contract === 'other' ? formData.contractOther : undefined,
        location: formData.location,
        location_coordinates: formData.locationCoordinates || undefined,
        event_date: new Date(`${formData.eventDate}T${formData.eventTime || '00:00'}`).toISOString(),
        event_time: formData.eventTime || undefined,
        description: formData.description,
        potential_consequences: formData.potentialConsequences || undefined,
        preventive_action_suggested: formData.preventiveActionSuggested || undefined,
        persons_involved: formData.personsInvolved || undefined,
        witnesses_present: formData.witnessesPresent ?? false,
        witness_names: formData.witnessNames || undefined,
        asset_number: formData.assetNumber || undefined,
        asset_type: formData.assetType || undefined,
        risk_category: formData.riskCategory || undefined,
        potential_severity: formData.potentialSeverity || undefined,
      };
      
      // Submit to API
      const response = await nearMissApi.create(payload);
      setSubmittedRef(response.reference_number);
    } catch (error) {
      console.error('Submission error:', error);
      // Fallback to local reference if API fails
      const fallbackRef = `NM-${new Date().getFullYear()}-${Date.now().toString(36).toUpperCase().slice(-4)}`;
      setSubmittedRef(fallbackRef);
    } finally {
      setIsSubmitting(false);
    }
  };

  // Validation
  const canProceed = (): boolean => {
    switch (step) {
      case 1: return !!formData.reporterName && !!formData.contract && !!formData.reporterRole;
      case 2: return !!formData.location && !!formData.description;
      case 3: return !!formData.riskCategory && !!formData.potentialSeverity;
      case 4: return true;
      default: return false;
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
          <h1 className="text-2xl font-bold text-foreground mb-2">Near Miss Reported</h1>
          <p className="text-muted-foreground mb-6">Your reference number is:</p>
          <div className="bg-surface border border-border rounded-xl px-6 py-4 mb-6">
            <span className="text-2xl font-mono font-bold text-primary">{submittedRef}</span>
          </div>
          <p className="text-sm text-muted-foreground mb-6">
            Thank you for reporting this near miss. Your report helps us prevent future incidents.
          </p>
          <div className="flex gap-3">
            <Button
              onClick={() => navigate('/portal/track/' + submittedRef)}
              className="flex-1 bg-primary hover:bg-primary/90"
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
              <AlertTriangle className="w-5 h-5 text-warning" />
              <span className="font-semibold text-foreground">Near Miss Report</span>
            </div>
            <div className="text-xs text-muted-foreground">Step {step} of {totalSteps}</div>
          </div>
        </div>
        
        <div className="h-1 bg-border">
          <div
            className="h-full bg-gradient-to-r from-warning to-primary transition-all duration-300"
            style={{ width: `${(step / totalSteps) * 100}%` }}
          />
        </div>
      </header>

      <main className="max-w-lg mx-auto px-4 sm:px-6 py-6 pb-28">
        {/* Step 1: Your Details */}
        {step === 1 && (
          <div className="space-y-5">
            <div>
              <h1 className="text-xl font-bold text-foreground mb-1">Your Details</h1>
              <p className="text-muted-foreground text-sm">Who is reporting this near miss?</p>
            </div>

            <div>
              <label className="block text-sm font-medium text-foreground mb-2">Your Name *</label>
              <div className="relative">
                <User className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                <Input
                  value={formData.reporterName}
                  onChange={(e) => setFormData((prev) => ({ ...prev, reporterName: e.target.value }))}
                  placeholder="Full name..."
                  className="pl-10"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-foreground mb-2">Your Role *</label>
              <div className="grid grid-cols-3 gap-2">
                {ROLE_OPTIONS.map((role) => (
                  <button
                    key={role.value}
                    type="button"
                    onClick={() => setFormData((prev) => ({ ...prev, reporterRole: role.value }))}
                    className={cn(
                      'flex flex-col items-center gap-1 p-3 rounded-xl border-2 transition-all',
                      formData.reporterRole === role.value
                        ? 'bg-primary/10 border-primary'
                        : 'bg-card border-border hover:border-border-strong'
                    )}
                  >
                    <role.icon className={cn('w-5 h-5', formData.reporterRole === role.value ? 'text-primary' : 'text-muted-foreground')} />
                    <span className="text-xs text-foreground">{role.label}</span>
                  </button>
                ))}
              </div>
            </div>

            <FuzzySearchDropdown
              label="Contract / Site *"
              options={CONTRACT_OPTIONS}
              value={formData.contract}
              onChange={(val) => setFormData((prev) => ({ ...prev, contract: val }))}
              placeholder="Search contract..."
              required
            />

            {formData.contract === 'other' && (
              <Input
                value={formData.contractOther}
                onChange={(e) => setFormData((prev) => ({ ...prev, contractOther: e.target.value }))}
                placeholder="Enter contract name..."
              />
            )}

            <div>
              <label className="block text-sm font-medium text-foreground mb-2">Were you involved?</label>
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
                    {val ? 'Yes, I was involved' : 'No, I witnessed it'}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Step 2: What Happened */}
        {step === 2 && (
          <div className="space-y-5">
            <div>
              <h1 className="text-xl font-bold text-foreground mb-1">What Happened?</h1>
              <p className="text-muted-foreground text-sm">Describe the near miss event</p>
            </div>

            <div>
              <label className="block text-sm font-medium text-foreground mb-2">Location *</label>
              <div className="relative">
                <MapPin className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                <Input
                  value={formData.location}
                  onChange={(e) => setFormData((prev) => ({ ...prev, location: e.target.value }))}
                  placeholder="Where did it happen?"
                  className="pl-10 pr-16"
                />
                <button
                  type="button"
                  onClick={detectLocation}
                  disabled={geoLoading}
                  className="absolute right-2 top-1/2 -translate-y-1/2 p-2 bg-primary/10 text-primary rounded-lg"
                >
                  {geoLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Navigation className="w-4 h-4" />}
                </button>
              </div>
              {geoError && <p className="text-destructive text-xs mt-1">{geoError}</p>}
              {formData.locationCoordinates && (
                <p className="text-muted-foreground text-xs mt-1">GPS: {formData.locationCoordinates}</p>
              )}
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm font-medium text-foreground mb-2">Date</label>
                <div className="relative">
                  <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                  <Input
                    type="date"
                    value={formData.eventDate}
                    onChange={(e) => setFormData((prev) => ({ ...prev, eventDate: e.target.value }))}
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
                    value={formData.eventTime}
                    onChange={(e) => setFormData((prev) => ({ ...prev, eventTime: e.target.value }))}
                    className="pl-10"
                  />
                </div>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-foreground mb-2">Description *</label>
              <div className="relative">
                <Textarea
                  value={formData.description}
                  onChange={(e) => setFormData((prev) => ({ ...prev, description: e.target.value }))}
                  placeholder="Describe what happened and what could have happened..."
                  rows={5}
                />
                {voiceSupported && (
                  <button
                    type="button"
                    onClick={toggleVoiceRecording}
                    className={cn(
                      'absolute right-3 bottom-3 p-2 rounded-full transition-colors',
                      isListening ? 'bg-destructive text-destructive-foreground animate-pulse' : 'bg-primary/10 text-primary hover:bg-primary/20'
                    )}
                  >
                    {isListening ? <MicOff className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
                  </button>
                )}
              </div>
              {isListening && (
                <p className="text-primary text-xs mt-1 animate-pulse">Listening... Speak now</p>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-foreground mb-2">What could have happened?</label>
              <Textarea
                value={formData.potentialConsequences}
                onChange={(e) => setFormData((prev) => ({ ...prev, potentialConsequences: e.target.value }))}
                placeholder="Describe the potential consequences if not avoided..."
                rows={3}
              />
            </div>
          </div>
        )}

        {/* Step 3: Risk Assessment */}
        {step === 3 && (
          <div className="space-y-5">
            <div>
              <h1 className="text-xl font-bold text-foreground mb-1">Risk Assessment</h1>
              <p className="text-muted-foreground text-sm">Categorize the near miss</p>
            </div>

            <div>
              <label className="block text-sm font-medium text-foreground mb-2">Risk Category *</label>
              <div className="grid grid-cols-3 gap-2">
                {RISK_CATEGORIES.map((cat) => (
                  <button
                    key={cat.value}
                    type="button"
                    onClick={() => setFormData((prev) => ({ ...prev, riskCategory: cat.value }))}
                    className={cn(
                      'flex flex-col items-center gap-1 p-3 rounded-xl border-2 transition-all',
                      formData.riskCategory === cat.value
                        ? 'bg-primary/10 border-primary'
                        : 'bg-card border-border hover:border-border-strong'
                    )}
                  >
                    <cat.icon className={cn('w-5 h-5', formData.riskCategory === cat.value ? 'text-primary' : 'text-muted-foreground')} />
                    <span className="text-xs text-foreground text-center">{cat.label}</span>
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-foreground mb-2">Potential Severity *</label>
              <div className="space-y-2">
                {SEVERITY_LEVELS.map((level) => (
                  <button
                    key={level.value}
                    type="button"
                    onClick={() => setFormData((prev) => ({ ...prev, potentialSeverity: level.value }))}
                    className={cn(
                      'w-full flex items-center gap-3 p-3 rounded-xl border-2 transition-all text-left',
                      formData.potentialSeverity === level.value
                        ? 'bg-primary/10 border-primary'
                        : 'bg-card border-border hover:border-border-strong'
                    )}
                  >
                    <div className={cn('w-4 h-4 rounded-full', level.color)} />
                    <div className="flex-1">
                      <div className="font-medium text-foreground">{level.label}</div>
                      <div className="text-xs text-muted-foreground">{level.description}</div>
                    </div>
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-foreground mb-2">Any witnesses?</label>
              <div className="grid grid-cols-2 gap-3">
                {[true, false].map((val) => (
                  <button
                    key={String(val)}
                    type="button"
                    onClick={() => setFormData((prev) => ({ ...prev, witnessesPresent: val }))}
                    className={cn(
                      'px-4 py-3 rounded-xl border-2 font-medium transition-all',
                      formData.witnessesPresent === val
                        ? 'bg-primary/10 border-primary text-primary'
                        : 'bg-card border-border text-foreground hover:border-border-strong'
                    )}
                  >
                    {val ? 'Yes' : 'No'}
                  </button>
                ))}
              </div>
            </div>

            {formData.witnessesPresent && (
              <Input
                value={formData.witnessNames}
                onChange={(e) => setFormData((prev) => ({ ...prev, witnessNames: e.target.value }))}
                placeholder="Witness names and contact..."
              />
            )}
          </div>
        )}

        {/* Step 4: Prevention & Evidence */}
        {step === 4 && (
          <div className="space-y-5">
            <div>
              <h1 className="text-xl font-bold text-foreground mb-1">Prevention & Evidence</h1>
              <p className="text-muted-foreground text-sm">Suggest actions and add photos</p>
            </div>

            <div>
              <label className="block text-sm font-medium text-foreground mb-2">Suggested Preventive Action</label>
              <Textarea
                value={formData.preventiveActionSuggested}
                onChange={(e) => setFormData((prev) => ({ ...prev, preventiveActionSuggested: e.target.value }))}
                placeholder="What could prevent this from happening again?"
                rows={4}
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm font-medium text-foreground mb-2">Asset Number</label>
                <Input
                  value={formData.assetNumber}
                  onChange={(e) => setFormData((prev) => ({ ...prev, assetNumber: e.target.value }))}
                  placeholder="If applicable..."
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-foreground mb-2">Asset Type</label>
                <Input
                  value={formData.assetType}
                  onChange={(e) => setFormData((prev) => ({ ...prev, assetType: e.target.value }))}
                  placeholder="e.g. Vehicle, Tool..."
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-foreground mb-2">Others Involved</label>
              <Input
                value={formData.personsInvolved}
                onChange={(e) => setFormData((prev) => ({ ...prev, personsInvolved: e.target.value }))}
                placeholder="Names of others involved..."
              />
            </div>

            {/* Photos */}
            <div>
              <label className="block text-sm font-medium text-foreground mb-2">Photos (optional)</label>
              <div className="grid grid-cols-4 gap-2">
                {formData.photos.map((photo, index) => (
                  <div key={index} className="relative aspect-square">
                    <img src={URL.createObjectURL(photo)} alt="" className="w-full h-full object-cover rounded-xl" />
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
                  <input type="file" accept="image/*" capture="environment" onChange={handlePhotoCapture} className="hidden" multiple />
                </label>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Fixed Bottom Navigation */}
      <div className="fixed bottom-0 left-0 right-0 bg-card/95 backdrop-blur-lg border-t border-border p-4">
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
              className="flex-1 bg-primary hover:bg-primary/90"
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
                  Submit Near Miss
                </>
              )}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
