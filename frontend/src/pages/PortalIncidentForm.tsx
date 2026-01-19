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
} from 'lucide-react';
import FuzzySearchDropdown from '../components/FuzzySearchDropdown';
import BodyInjurySelector, { InjurySelection } from '../components/BodyInjurySelector';
import { usePortalAuth } from '../contexts/PortalAuthContext';

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
    color: 'red',
    gradient: 'from-red-500 to-orange-500',
  },
  'near-miss': {
    title: 'Near Miss Report',
    subtitle: 'Close Call',
    icon: AlertCircle,
    color: 'yellow',
    gradient: 'from-yellow-500 to-amber-500',
  },
  'complaint': {
    title: 'Customer Complaint',
    subtitle: 'Customer Concern',
    icon: MessageSquare,
    color: 'blue',
    gradient: 'from-blue-500 to-cyan-500',
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

// Body parts removed - now using BodyInjurySelector component

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
  // Complaint specific
  complainantName: string;
  complainantRole: string;
  complainantContact: string;
  // Photos
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
  const [isRecording, setIsRecording] = useState(false);
  const [geolocating, setGeolocating] = useState(false);
  const [submittedRef, setSubmittedRef] = useState<string | null>(null);

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

  // Total steps depends on report type
  const totalSteps = reportType === 'complaint' ? 3 : 4;

  // GPS location detection
  const detectLocation = () => {
    setGeolocating(true);
    if ('geolocation' in navigator) {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          const coords = `GPS: ${position.coords.latitude.toFixed(6)}, ${position.coords.longitude.toFixed(6)}`;
          setFormData((prev) => ({ ...prev, location: coords }));
          setGeolocating(false);
        },
        () => {
          setGeolocating(false);
          alert('Could not detect location');
        }
      );
    }
  };

  // Voice recording
  const toggleVoiceRecording = () => {
    if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
      setIsRecording(!isRecording);
      // In production, implement actual speech recognition
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

  // Form submission
  const handleSubmit = async () => {
    setIsSubmitting(true);
    try {
      const prefix = reportType === 'incident' ? 'INC' : reportType === 'near-miss' ? 'NM' : 'CMP';
      const refNumber = `${prefix}-${Date.now().toString(36).toUpperCase()}`;
      await new Promise((resolve) => setTimeout(resolve, 1500));
      setSubmittedRef(refNumber);
    } catch {
      alert('Failed to submit');
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
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-green-900/20 to-slate-900 flex items-center justify-center p-4">
        <div className="bg-white/10 backdrop-blur-xl border border-white/20 rounded-3xl p-8 max-w-md w-full text-center">
          <div className="w-20 h-20 bg-green-500/20 rounded-full flex items-center justify-center mx-auto mb-6">
            <Check className="w-10 h-10 text-green-400" />
          </div>
          <h1 className="text-2xl font-bold text-white mb-2">Report Submitted</h1>
          <p className="text-gray-400 mb-6">Your reference number is:</p>
          <div className="bg-white/5 border border-white/20 rounded-xl px-6 py-4 mb-6">
            <span className="text-2xl font-mono font-bold text-purple-400">{submittedRef}</span>
          </div>
          <div className="flex gap-3">
            <button
              onClick={() => navigate('/portal/track/' + submittedRef)}
              className="flex-1 px-4 py-3 bg-purple-500 hover:bg-purple-600 text-white rounded-xl font-medium transition-colors"
            >
              Track Status
            </button>
            <button
              onClick={() => navigate('/portal')}
              className="flex-1 px-4 py-3 bg-white/10 hover:bg-white/20 text-white rounded-xl font-medium transition-colors"
            >
              Done
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900/20 to-slate-900">
      {/* Header */}
      <header className="sticky top-0 z-50 bg-black/30 backdrop-blur-xl border-b border-white/10">
        <div className="max-w-lg mx-auto px-4 py-4 flex items-center gap-4">
          <button
            onClick={() => step === 1 ? navigate('/portal/report') : setStep((s) => (s - 1) as Step)}
            className="w-10 h-10 flex items-center justify-center rounded-xl bg-white/5 hover:bg-white/10 transition-colors"
          >
            <ArrowLeft className="w-5 h-5 text-white" />
          </button>
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <config.icon className={`w-5 h-5 text-${config.color}-400`} style={{ color: config.color === 'red' ? '#f87171' : config.color === 'yellow' ? '#facc15' : '#60a5fa' }} />
              <span className="font-semibold text-white">{config.title}</span>
            </div>
            <div className="text-xs text-gray-500">Step {step} of {totalSteps}</div>
          </div>
        </div>
        
        {/* Progress bar */}
        <div className="h-1 bg-white/10">
          <div
            className={`h-full bg-gradient-to-r ${config.gradient} transition-all duration-300`}
            style={{ width: `${(step / totalSteps) * 100}%` }}
          />
        </div>
      </header>

      <main className="max-w-lg mx-auto px-4 py-6 pb-28">
        {/* Step 1: Contract */}
        {step === 1 && (
          <div className="space-y-6">
            <div>
              <h1 className="text-xl font-bold text-white mb-1">Contract Details</h1>
              <p className="text-gray-400 text-sm">Which contract does this relate to?</p>
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
              <input
                type="text"
                value={formData.contractOther}
                onChange={(e) => setFormData((prev) => ({ ...prev, contractOther: e.target.value }))}
                placeholder="Specify contract..."
                className="w-full px-4 py-3 bg-white/5 border border-white/20 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-purple-500"
              />
            )}
          </div>
        )}

        {/* Step 2: Person & Location */}
        {step === 2 && (
          <div className="space-y-5">
            <div>
              <h1 className="text-xl font-bold text-white mb-1">
                {reportType === 'complaint' ? 'Complainant Details' : 'People & Location'}
              </h1>
              <p className="text-gray-400 text-sm">
                {reportType === 'complaint' ? 'Who raised the complaint?' : 'Who was involved and where?'}
              </p>
            </div>

            {reportType !== 'complaint' && (
              <>
                {/* Were you involved? */}
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    Were you directly involved?
                  </label>
                  <div className="grid grid-cols-2 gap-3">
                    {[true, false].map((val) => (
                      <button
                        key={String(val)}
                        type="button"
                        onClick={() => setFormData((prev) => ({ ...prev, wasInvolved: val }))}
                        className={`px-4 py-3 rounded-xl border-2 font-medium transition-all ${
                          formData.wasInvolved === val
                            ? 'bg-purple-500/20 border-purple-500 text-white'
                            : 'bg-white/5 border-white/20 text-gray-300'
                        }`}
                      >
                        {val ? 'Yes' : 'No'}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Person Name */}
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    {formData.wasInvolved ? 'Your Name' : 'Name of Person Involved'} *
                  </label>
                  <div className="relative">
                    <User className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                    <input
                      type="text"
                      value={formData.personName}
                      onChange={(e) => setFormData((prev) => ({ ...prev, personName: e.target.value }))}
                      placeholder="Full name..."
                      className="w-full pl-12 pr-4 py-3 bg-white/5 border border-white/20 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-purple-500"
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
                  <label className="block text-sm font-medium text-gray-300 mb-2">Complainant Name *</label>
                  <div className="relative">
                    <User className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                    <input
                      type="text"
                      value={formData.complainantName}
                      onChange={(e) => setFormData((prev) => ({ ...prev, complainantName: e.target.value }))}
                      placeholder="Full name..."
                      className="w-full pl-12 pr-4 py-3 bg-white/5 border border-white/20 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-purple-500"
                    />
                  </div>
                </div>

                {/* Complainant Role */}
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">Their Role/Title</label>
                  <div className="relative">
                    <Building className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                    <input
                      type="text"
                      value={formData.complainantRole}
                      onChange={(e) => setFormData((prev) => ({ ...prev, complainantRole: e.target.value }))}
                      placeholder="e.g. Site Manager..."
                      className="w-full pl-12 pr-4 py-3 bg-white/5 border border-white/20 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-purple-500"
                    />
                  </div>
                </div>

                {/* Complainant Contact */}
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">Contact Details</label>
                  <div className="relative">
                    <Phone className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                    <input
                      type="text"
                      value={formData.complainantContact}
                      onChange={(e) => setFormData((prev) => ({ ...prev, complainantContact: e.target.value }))}
                      placeholder="Phone or email..."
                      className="w-full pl-12 pr-4 py-3 bg-white/5 border border-white/20 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-purple-500"
                    />
                  </div>
                </div>
              </>
            )}

            {/* Location */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">Location *</label>
              <div className="relative">
                <MapPin className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                <input
                  type="text"
                  value={formData.location}
                  onChange={(e) => setFormData((prev) => ({ ...prev, location: e.target.value }))}
                  placeholder="Where did this occur?"
                  className="w-full pl-12 pr-20 py-3 bg-white/5 border border-white/20 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-purple-500"
                />
                <button
                  type="button"
                  onClick={detectLocation}
                  disabled={geolocating}
                  className="absolute right-2 top-1/2 -translate-y-1/2 px-3 py-1.5 bg-purple-500/20 text-purple-400 rounded-lg text-sm font-medium"
                >
                  {geolocating ? <Loader2 className="w-4 h-4 animate-spin" /> : 'GPS'}
                </button>
              </div>
            </div>

            {/* Date & Time */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">Date</label>
                <div className="relative">
                  <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                  <input
                    type="date"
                    value={formData.incidentDate}
                    onChange={(e) => setFormData((prev) => ({ ...prev, incidentDate: e.target.value }))}
                    className="w-full pl-10 pr-3 py-3 bg-white/5 border border-white/20 rounded-xl text-white focus:outline-none focus:border-purple-500"
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">Time</label>
                <div className="relative">
                  <Clock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                  <input
                    type="time"
                    value={formData.incidentTime}
                    onChange={(e) => setFormData((prev) => ({ ...prev, incidentTime: e.target.value }))}
                    className="w-full pl-10 pr-3 py-3 bg-white/5 border border-white/20 rounded-xl text-white focus:outline-none focus:border-purple-500"
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
              <h1 className="text-xl font-bold text-white mb-1">What Happened?</h1>
              <p className="text-gray-400 text-sm">Describe the {reportType === 'complaint' ? 'complaint' : 'incident'} in detail</p>
            </div>

            {/* Description */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">Description *</label>
              <div className="relative">
                <textarea
                  value={formData.description}
                  onChange={(e) => setFormData((prev) => ({ ...prev, description: e.target.value }))}
                  placeholder="What happened? Be specific..."
                  rows={5}
                  className="w-full px-4 py-3 bg-white/5 border border-white/20 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-purple-500 resize-none"
                />
                <button
                  type="button"
                  onClick={toggleVoiceRecording}
                  className={`absolute right-3 bottom-3 p-2 rounded-full ${isRecording ? 'bg-red-500 animate-pulse' : 'bg-purple-500/20 text-purple-400'}`}
                >
                  {isRecording ? <MicOff className="w-5 h-5 text-white" /> : <Mic className="w-5 h-5" />}
                </button>
              </div>
            </div>

            {/* Asset Number */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">Asset / Vehicle Registration</label>
              <div className="relative">
                <Truck className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                <input
                  type="text"
                  value={formData.assetNumber}
                  onChange={(e) => setFormData((prev) => ({ ...prev, assetNumber: e.target.value.toUpperCase() }))}
                  placeholder="e.g. PN22P102..."
                  className="w-full pl-12 pr-4 py-3 bg-white/5 border border-white/20 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-purple-500 uppercase"
                />
              </div>
            </div>

            {/* Witnesses */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">Any witnesses?</label>
              <div className="grid grid-cols-2 gap-3">
                {[true, false].map((val) => (
                  <button
                    key={String(val)}
                    type="button"
                    onClick={() => setFormData((prev) => ({ ...prev, hasWitnesses: val }))}
                    className={`px-4 py-3 rounded-xl border-2 font-medium transition-all ${
                      formData.hasWitnesses === val
                        ? 'bg-purple-500/20 border-purple-500 text-white'
                        : 'bg-white/5 border-white/20 text-gray-300'
                    }`}
                  >
                    {val ? 'Yes' : 'No'}
                  </button>
                ))}
              </div>
            </div>

            {formData.hasWitnesses && (
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">Witness Names</label>
                <div className="relative">
                  <Users className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                  <input
                    type="text"
                    value={formData.witnessNames}
                    onChange={(e) => setFormData((prev) => ({ ...prev, witnessNames: e.target.value }))}
                    placeholder="Names of witnesses..."
                    className="w-full pl-12 pr-4 py-3 bg-white/5 border border-white/20 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-purple-500"
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
              <h1 className="text-xl font-bold text-white mb-1">Injuries & Evidence</h1>
              <p className="text-gray-400 text-sm">Any injuries and supporting photos</p>
            </div>

            {/* Injuries */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">Any injuries sustained?</label>
              <div className="grid grid-cols-2 gap-3">
                {[true, false].map((val) => (
                  <button
                    key={String(val)}
                    type="button"
                    onClick={() => setFormData((prev) => ({ ...prev, hasInjuries: val }))}
                    className={`px-4 py-3 rounded-xl border-2 font-medium transition-all ${
                      formData.hasInjuries === val
                        ? val ? 'bg-red-500/20 border-red-500 text-red-400' : 'bg-green-500/20 border-green-500 text-green-400'
                        : 'bg-white/5 border-white/20 text-gray-300'
                    }`}
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
              <label className="block text-sm font-medium text-gray-300 mb-2">Photos</label>
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
                      className="absolute -top-1 -right-1 w-5 h-5 bg-red-500 text-white rounded-full flex items-center justify-center"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </div>
                ))}
                <label className="aspect-square flex flex-col items-center justify-center bg-white/5 border-2 border-dashed border-white/20 rounded-xl cursor-pointer hover:bg-white/10">
                  <Camera className="w-6 h-6 text-gray-400" />
                  <span className="text-xs text-gray-400 mt-1">Add</span>
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
      <div className="fixed bottom-0 left-0 right-0 bg-black/50 backdrop-blur-xl border-t border-white/10 p-4">
        <div className="max-w-lg mx-auto flex gap-3">
          {step > 1 && (
            <button
              type="button"
              onClick={() => setStep((s) => (s - 1) as Step)}
              className="px-5 py-3 bg-white/10 hover:bg-white/20 text-white rounded-xl font-medium transition-colors flex items-center gap-2"
            >
              <ChevronLeft className="w-5 h-5" />
              Back
            </button>
          )}
          
          {step < totalSteps ? (
            <button
              type="button"
              onClick={() => setStep((s) => (s + 1) as Step)}
              disabled={!canProceed()}
              className={`flex-1 px-5 py-3 bg-gradient-to-r ${config.gradient} disabled:opacity-50 text-white rounded-xl font-semibold transition-all flex items-center justify-center gap-2`}
            >
              Continue
              <ChevronRight className="w-5 h-5" />
            </button>
          ) : (
            <button
              type="button"
              onClick={handleSubmit}
              disabled={isSubmitting}
              className="flex-1 px-5 py-3 bg-gradient-to-r from-green-500 to-emerald-500 disabled:opacity-50 text-white rounded-xl font-semibold transition-all flex items-center justify-center gap-2"
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
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
