import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
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
  Mail,
  FileText,
  Upload,
  Check,
  ChevronRight,
  ChevronLeft,
  Loader2,
  Shield,
  Car,
  Truck,
  Eye,
  Users,
  Stethoscope,
  X,
  Sparkles,
} from 'lucide-react';
import FuzzySearchDropdown from '../components/FuzzySearchDropdown';

// Contract options based on CSV data
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

const ROLE_OPTIONS = [
  { value: 'mobile-engineer', label: 'Mobile Engineer' },
  { value: 'workshop-pehq', label: 'Workshop (PE HQ)' },
  { value: 'workshop-fixed', label: 'Vehicle Workshop (Fixed Customer Site)' },
  { value: 'office', label: 'Office Based Employee' },
  { value: 'trainee', label: 'Trainee/Apprentice' },
  { value: 'non-pe', label: 'Non-Plantexpand Employee' },
  { value: 'other', label: 'Other' },
];

const BODY_PARTS = [
  { value: 'head', label: 'Head', icon: '🧠' },
  { value: 'neck', label: 'Neck', icon: '🦴' },
  { value: 'torso', label: 'Torso/Back', icon: '🫁' },
  { value: 'arms', label: 'Arms', icon: '💪' },
  { value: 'hands', label: 'Hands/Fingers', icon: '🤚' },
  { value: 'legs', label: 'Legs', icon: '🦵' },
  { value: 'feet', label: 'Feet', icon: '🦶' },
];

const MEDICAL_ASSISTANCE_OPTIONS = [
  { value: 'none', label: 'No medical assistance needed' },
  { value: 'self', label: 'Self application' },
  { value: 'first-aider', label: 'First aider on site' },
  { value: 'ambulance', label: 'Ambulance/A&E' },
  { value: 'gp', label: 'GP/Hospital visit' },
];

type ReportType = 'accident' | 'near-miss' | 'complaint';
type Step = 1 | 2 | 3 | 4;

interface FormData {
  reportType: ReportType | '';
  contract: string;
  contractOther: string;
  // Person details
  wasInvolved: boolean | null;
  personName: string;
  personRole: string;
  personRoleOther: string;
  personContact: string;
  // Incident details
  location: string;
  incidentDate: string;
  incidentTime: string;
  description: string;
  assetNumber: string;
  // Witnesses
  hasWitnesses: boolean | null;
  witnessNames: string;
  // Injury details (for accidents)
  hasInjuries: boolean | null;
  injuredBodyParts: string[];
  medicalAssistance: string;
  // Complaint specifics
  complainantName: string;
  complainantRole: string;
  complainantContact: string;
  complaintDescription: string;
  // Files
  photos: File[];
}

export default function PortalIncidentForm() {
  const navigate = useNavigate();
  const [step, setStep] = useState<Step>(1);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [geolocating, setGeolocating] = useState(false);
  const [submittedRef, setSubmittedRef] = useState<string | null>(null);

  const [formData, setFormData] = useState<FormData>({
    reportType: '',
    contract: '',
    contractOther: '',
    wasInvolved: null,
    personName: '',
    personRole: '',
    personRoleOther: '',
    personContact: '',
    location: '',
    incidentDate: new Date().toISOString().split('T')[0],
    incidentTime: new Date().toTimeString().slice(0, 5),
    description: '',
    assetNumber: '',
    hasWitnesses: null,
    witnessNames: '',
    hasInjuries: null,
    injuredBodyParts: [],
    medicalAssistance: '',
    complainantName: '',
    complainantRole: '',
    complainantContact: '',
    complaintDescription: '',
    photos: [],
  });

  // Auto-detect location
  const detectLocation = () => {
    setGeolocating(true);
    if ('geolocation' in navigator) {
      navigator.geolocation.getCurrentPosition(
        async (position) => {
          try {
            // Reverse geocode (in real app, call a geocoding API)
            const coords = `${position.coords.latitude.toFixed(6)}, ${position.coords.longitude.toFixed(6)}`;
            setFormData((prev) => ({ ...prev, location: `GPS: ${coords}` }));
          } catch {
            setFormData((prev) => ({ ...prev, location: `GPS: ${position.coords.latitude.toFixed(6)}, ${position.coords.longitude.toFixed(6)}` }));
          } finally {
            setGeolocating(false);
          }
        },
        () => {
          setGeolocating(false);
          alert('Could not detect location. Please enter manually.');
        }
      );
    }
  };

  // Voice recording for description
  const toggleVoiceRecording = () => {
    if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
      const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
      const recognition = new SpeechRecognition();
      recognition.continuous = true;
      recognition.interimResults = true;

      if (!isRecording) {
        recognition.onresult = (event: any) => {
          const transcript = Array.from(event.results)
            .map((result: any) => result[0].transcript)
            .join('');
          setFormData((prev) => ({ ...prev, description: prev.description + ' ' + transcript }));
        };
        recognition.start();
        setIsRecording(true);
      } else {
        recognition.stop();
        setIsRecording(false);
      }
    } else {
      alert('Voice recording not supported in this browser');
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
      // Generate reference number
      const refNumber = `INC-${Date.now().toString(36).toUpperCase()}`;
      
      // In production, this would POST to the API
      await new Promise((resolve) => setTimeout(resolve, 1500));
      
      setSubmittedRef(refNumber);
    } catch {
      alert('Failed to submit. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  // Step validation
  const canProceed = (): boolean => {
    switch (step) {
      case 1:
        return !!formData.reportType && !!formData.contract;
      case 2:
        if (formData.reportType === 'complaint') {
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

  // Render success screen
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
          <p className="text-sm text-gray-500 mb-6">
            Save this reference to track your report status
          </p>
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
        <div className="max-w-2xl mx-auto px-4 py-4 flex items-center justify-between">
          <button
            onClick={() => (step === 1 ? navigate('/portal') : setStep((s) => (s - 1) as Step))}
            className="flex items-center gap-2 text-white hover:text-gray-300 transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
            <span className="hidden sm:inline">{step === 1 ? 'Back' : 'Previous'}</span>
          </button>
          
          <div className="flex items-center gap-2">
            <Shield className="w-6 h-6 text-purple-400" />
            <span className="font-semibold text-white">Incident Report</span>
          </div>

          <div className="text-sm text-gray-400">
            Step {step}/4
          </div>
        </div>
        
        {/* Progress bar */}
        <div className="h-1 bg-white/10">
          <div
            className="h-full bg-gradient-to-r from-purple-500 to-cyan-500 transition-all duration-300"
            style={{ width: `${(step / 4) * 100}%` }}
          />
        </div>
      </header>

      <main className="max-w-2xl mx-auto px-4 py-6 pb-32">
        {/* Step 1: Type & Contract */}
        {step === 1 && (
          <div className="space-y-6 animate-in fade-in slide-in-from-right duration-300">
            <div>
              <h1 className="text-2xl font-bold text-white mb-2">What are you reporting?</h1>
              <p className="text-gray-400">Select the type of report</p>
            </div>

            {/* Report Type Selection - Large touch targets */}
            <div className="grid gap-3">
              {[
                { type: 'accident' as ReportType, icon: AlertTriangle, label: 'Injury / Accident', desc: 'Physical injury or accident', color: 'red' },
                { type: 'near-miss' as ReportType, icon: AlertCircle, label: 'Near Miss', desc: 'Close call, no injury', color: 'yellow' },
                { type: 'complaint' as ReportType, icon: MessageSquare, label: 'Customer Complaint', desc: 'Customer concern or issue', color: 'blue' },
              ].map((item) => (
                <button
                  key={item.type}
                  onClick={() => setFormData((prev) => ({ ...prev, reportType: item.type }))}
                  className={`
                    flex items-center gap-4 p-4 rounded-2xl border-2 transition-all text-left
                    ${formData.reportType === item.type
                      ? `bg-${item.color}-500/20 border-${item.color}-500`
                      : 'bg-white/5 border-white/20 hover:bg-white/10'
                    }
                  `}
                  style={{
                    backgroundColor: formData.reportType === item.type 
                      ? item.color === 'red' ? 'rgba(239, 68, 68, 0.2)' 
                      : item.color === 'yellow' ? 'rgba(234, 179, 8, 0.2)'
                      : 'rgba(59, 130, 246, 0.2)'
                      : undefined,
                    borderColor: formData.reportType === item.type
                      ? item.color === 'red' ? '#ef4444'
                      : item.color === 'yellow' ? '#eab308'
                      : '#3b82f6'
                      : undefined,
                  }}
                >
                  <div className={`
                    p-3 rounded-xl
                    ${item.color === 'red' ? 'bg-red-500/30 text-red-400' : ''}
                    ${item.color === 'yellow' ? 'bg-yellow-500/30 text-yellow-400' : ''}
                    ${item.color === 'blue' ? 'bg-blue-500/30 text-blue-400' : ''}
                  `}>
                    <item.icon className="w-6 h-6" />
                  </div>
                  <div className="flex-1">
                    <div className="text-white font-semibold">{item.label}</div>
                    <div className="text-gray-400 text-sm">{item.desc}</div>
                  </div>
                  {formData.reportType === item.type && (
                    <Check className="w-6 h-6 text-green-400" />
                  )}
                </button>
              ))}
            </div>

            {/* Contract Selection with Fuzzy Search */}
            <div className="pt-4">
              <FuzzySearchDropdown
                label="Which contract does this relate to?"
                options={CONTRACT_OPTIONS}
                value={formData.contract}
                onChange={(val) => setFormData((prev) => ({ ...prev, contract: val }))}
                placeholder="Search contract..."
                required
              />
            </div>

            {formData.contract === 'other' && (
              <input
                type="text"
                value={formData.contractOther}
                onChange={(e) => setFormData((prev) => ({ ...prev, contractOther: e.target.value }))}
                placeholder="Specify contract..."
                className="w-full px-4 py-3.5 bg-white/5 border border-white/20 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-purple-500"
              />
            )}
          </div>
        )}

        {/* Step 2: People & Location */}
        {step === 2 && (
          <div className="space-y-6 animate-in fade-in slide-in-from-right duration-300">
            <div>
              <h1 className="text-2xl font-bold text-white mb-2">
                {formData.reportType === 'complaint' ? 'Complaint Details' : 'Who was involved?'}
              </h1>
              <p className="text-gray-400">
                {formData.reportType === 'complaint' ? 'Who raised the complaint?' : 'Tell us about the people involved'}
              </p>
            </div>

            {formData.reportType !== 'complaint' && (
              <>
                {/* Were you involved? */}
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-3">
                    Were you directly involved?
                  </label>
                  <div className="grid grid-cols-2 gap-3">
                    {[
                      { value: true, label: 'Yes, I was involved' },
                      { value: false, label: 'No, someone else' },
                    ].map((opt) => (
                      <button
                        key={String(opt.value)}
                        type="button"
                        onClick={() => setFormData((prev) => ({ ...prev, wasInvolved: opt.value }))}
                        className={`
                          px-4 py-3 rounded-xl border-2 transition-all font-medium
                          ${formData.wasInvolved === opt.value
                            ? 'bg-purple-500/20 border-purple-500 text-white'
                            : 'bg-white/5 border-white/20 text-gray-300 hover:bg-white/10'
                          }
                        `}
                      >
                        {opt.label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Person Name */}
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    {formData.wasInvolved ? 'Your name' : 'Name of person involved'} <span className="text-red-400">*</span>
                  </label>
                  <div className="relative">
                    <User className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                    <input
                      type="text"
                      value={formData.personName}
                      onChange={(e) => setFormData((prev) => ({ ...prev, personName: e.target.value }))}
                      placeholder="Full name..."
                      className="w-full pl-12 pr-4 py-3.5 bg-white/5 border border-white/20 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-purple-500"
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

            {formData.reportType === 'complaint' && (
              <>
                {/* Complainant Name */}
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    Complainant Name <span className="text-red-400">*</span>
                  </label>
                  <div className="relative">
                    <User className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                    <input
                      type="text"
                      value={formData.complainantName}
                      onChange={(e) => setFormData((prev) => ({ ...prev, complainantName: e.target.value }))}
                      placeholder="Full name..."
                      className="w-full pl-12 pr-4 py-3.5 bg-white/5 border border-white/20 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-purple-500"
                    />
                  </div>
                </div>

                {/* Complainant Role */}
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">Role/Title</label>
                  <div className="relative">
                    <Building className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                    <input
                      type="text"
                      value={formData.complainantRole}
                      onChange={(e) => setFormData((prev) => ({ ...prev, complainantRole: e.target.value }))}
                      placeholder="e.g. Site Manager, Engineer..."
                      className="w-full pl-12 pr-4 py-3.5 bg-white/5 border border-white/20 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-purple-500"
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
                      className="w-full pl-12 pr-4 py-3.5 bg-white/5 border border-white/20 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-purple-500"
                    />
                  </div>
                </div>
              </>
            )}

            {/* Location */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Location <span className="text-red-400">*</span>
              </label>
              <div className="relative">
                <MapPin className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                <input
                  type="text"
                  value={formData.location}
                  onChange={(e) => setFormData((prev) => ({ ...prev, location: e.target.value }))}
                  placeholder="Where did this occur?"
                  className="w-full pl-12 pr-24 py-3.5 bg-white/5 border border-white/20 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-purple-500"
                />
                <button
                  type="button"
                  onClick={detectLocation}
                  disabled={geolocating}
                  className="absolute right-2 top-1/2 -translate-y-1/2 px-3 py-1.5 bg-purple-500/20 hover:bg-purple-500/30 text-purple-400 rounded-lg text-sm font-medium transition-colors flex items-center gap-1"
                >
                  {geolocating ? <Loader2 className="w-4 h-4 animate-spin" /> : <MapPin className="w-4 h-4" />}
                  GPS
                </button>
              </div>
            </div>

            {/* Date & Time */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">Date</label>
                <div className="relative">
                  <Calendar className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                  <input
                    type="date"
                    value={formData.incidentDate}
                    onChange={(e) => setFormData((prev) => ({ ...prev, incidentDate: e.target.value }))}
                    className="w-full pl-12 pr-4 py-3.5 bg-white/5 border border-white/20 rounded-xl text-white focus:outline-none focus:border-purple-500"
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">Time</label>
                <div className="relative">
                  <Clock className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                  <input
                    type="time"
                    value={formData.incidentTime}
                    onChange={(e) => setFormData((prev) => ({ ...prev, incidentTime: e.target.value }))}
                    className="w-full pl-12 pr-4 py-3.5 bg-white/5 border border-white/20 rounded-xl text-white focus:outline-none focus:border-purple-500"
                  />
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Step 3: Details */}
        {step === 3 && (
          <div className="space-y-6 animate-in fade-in slide-in-from-right duration-300">
            <div>
              <h1 className="text-2xl font-bold text-white mb-2">Describe what happened</h1>
              <p className="text-gray-400">Provide as much detail as possible</p>
            </div>

            {/* Description with voice input */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Description <span className="text-red-400">*</span>
              </label>
              <div className="relative">
                <textarea
                  value={formData.description}
                  onChange={(e) => setFormData((prev) => ({ ...prev, description: e.target.value }))}
                  placeholder="What happened? Be specific about actions, conditions, and sequence of events..."
                  rows={5}
                  className="w-full px-4 py-3.5 bg-white/5 border border-white/20 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-purple-500 resize-none"
                />
                <button
                  type="button"
                  onClick={toggleVoiceRecording}
                  className={`
                    absolute right-3 bottom-3 p-2.5 rounded-full transition-all
                    ${isRecording
                      ? 'bg-red-500 text-white animate-pulse'
                      : 'bg-purple-500/20 text-purple-400 hover:bg-purple-500/30'
                    }
                  `}
                  title="Voice to text"
                >
                  {isRecording ? <MicOff className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
                </button>
              </div>
              {isRecording && (
                <p className="text-sm text-red-400 mt-2 flex items-center gap-2">
                  <span className="w-2 h-2 bg-red-500 rounded-full animate-pulse" />
                  Recording... Tap to stop
                </p>
              )}
            </div>

            {/* Asset Number */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Asset Number / Vehicle Registration
              </label>
              <div className="relative">
                <Truck className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                <input
                  type="text"
                  value={formData.assetNumber}
                  onChange={(e) => setFormData((prev) => ({ ...prev, assetNumber: e.target.value.toUpperCase() }))}
                  placeholder="e.g. PN22P102, BD21NTJ..."
                  className="w-full pl-12 pr-4 py-3.5 bg-white/5 border border-white/20 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-purple-500 uppercase"
                />
              </div>
            </div>

            {/* Witnesses */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-3">
                Were there any witnesses?
              </label>
              <div className="grid grid-cols-2 gap-3">
                {[
                  { value: true, label: 'Yes' },
                  { value: false, label: 'No' },
                ].map((opt) => (
                  <button
                    key={String(opt.value)}
                    type="button"
                    onClick={() => setFormData((prev) => ({ ...prev, hasWitnesses: opt.value }))}
                    className={`
                      px-4 py-3 rounded-xl border-2 transition-all font-medium
                      ${formData.hasWitnesses === opt.value
                        ? 'bg-purple-500/20 border-purple-500 text-white'
                        : 'bg-white/5 border-white/20 text-gray-300 hover:bg-white/10'
                      }
                    `}
                  >
                    {opt.label}
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
                    className="w-full pl-12 pr-4 py-3.5 bg-white/5 border border-white/20 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-purple-500"
                  />
                </div>
              </div>
            )}

            {/* Injury Details (for accidents) */}
            {formData.reportType === 'accident' && (
              <>
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-3">
                    Were any injuries sustained?
                  </label>
                  <div className="grid grid-cols-2 gap-3">
                    {[
                      { value: true, label: 'Yes' },
                      { value: false, label: 'No' },
                    ].map((opt) => (
                      <button
                        key={String(opt.value)}
                        type="button"
                        onClick={() => setFormData((prev) => ({ ...prev, hasInjuries: opt.value }))}
                        className={`
                          px-4 py-3 rounded-xl border-2 transition-all font-medium
                          ${formData.hasInjuries === opt.value
                            ? 'bg-purple-500/20 border-purple-500 text-white'
                            : 'bg-white/5 border-white/20 text-gray-300 hover:bg-white/10'
                          }
                        `}
                      >
                        {opt.label}
                      </button>
                    ))}
                  </div>
                </div>

                {formData.hasInjuries && (
                  <>
                    {/* Body Part Selection */}
                    <div>
                      <label className="block text-sm font-medium text-gray-300 mb-3">
                        Which body parts were injured? (tap all that apply)
                      </label>
                      <div className="grid grid-cols-4 gap-2">
                        {BODY_PARTS.map((part) => (
                          <button
                            key={part.value}
                            type="button"
                            onClick={() => {
                              setFormData((prev) => ({
                                ...prev,
                                injuredBodyParts: prev.injuredBodyParts.includes(part.value)
                                  ? prev.injuredBodyParts.filter((p) => p !== part.value)
                                  : [...prev.injuredBodyParts, part.value],
                              }));
                            }}
                            className={`
                              flex flex-col items-center gap-1 p-3 rounded-xl border-2 transition-all
                              ${formData.injuredBodyParts.includes(part.value)
                                ? 'bg-red-500/20 border-red-500 text-white'
                                : 'bg-white/5 border-white/20 text-gray-300 hover:bg-white/10'
                              }
                            `}
                          >
                            <span className="text-2xl">{part.icon}</span>
                            <span className="text-xs">{part.label}</span>
                          </button>
                        ))}
                      </div>
                    </div>

                    {/* Medical Assistance */}
                    <FuzzySearchDropdown
                      label="Medical assistance required?"
                      options={MEDICAL_ASSISTANCE_OPTIONS}
                      value={formData.medicalAssistance}
                      onChange={(val) => setFormData((prev) => ({ ...prev, medicalAssistance: val }))}
                      placeholder="Select..."
                    />
                  </>
                )}
              </>
            )}
          </div>
        )}

        {/* Step 4: Photos & Review */}
        {step === 4 && (
          <div className="space-y-6 animate-in fade-in slide-in-from-right duration-300">
            <div>
              <h1 className="text-2xl font-bold text-white mb-2">Photos & Submit</h1>
              <p className="text-gray-400">Add supporting photos and review your report</p>
            </div>

            {/* Photo Upload */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-3">
                Upload Photos
              </label>
              <div className="grid grid-cols-3 gap-3">
                {formData.photos.map((photo, index) => (
                  <div key={index} className="relative aspect-square">
                    <img
                      src={URL.createObjectURL(photo)}
                      alt={`Upload ${index + 1}`}
                      className="w-full h-full object-cover rounded-xl"
                    />
                    <button
                      type="button"
                      onClick={() => removePhoto(index)}
                      className="absolute -top-2 -right-2 w-6 h-6 bg-red-500 text-white rounded-full flex items-center justify-center"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                ))}
                <label className="aspect-square flex flex-col items-center justify-center bg-white/5 border-2 border-dashed border-white/20 rounded-xl cursor-pointer hover:bg-white/10 hover:border-white/30 transition-all">
                  <Camera className="w-8 h-8 text-gray-400 mb-2" />
                  <span className="text-xs text-gray-400">Add Photo</span>
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

            {/* Summary */}
            <div className="bg-white/5 border border-white/20 rounded-2xl p-4 space-y-3">
              <h3 className="font-semibold text-white flex items-center gap-2">
                <FileText className="w-5 h-5 text-purple-400" />
                Report Summary
              </h3>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-400">Type:</span>
                  <span className="text-white capitalize">{formData.reportType?.replace('-', ' ')}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Contract:</span>
                  <span className="text-white">{CONTRACT_OPTIONS.find((c) => c.value === formData.contract)?.label}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Location:</span>
                  <span className="text-white truncate ml-4">{formData.location || 'Not specified'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Date/Time:</span>
                  <span className="text-white">{formData.incidentDate} {formData.incidentTime}</span>
                </div>
                {formData.assetNumber && (
                  <div className="flex justify-between">
                    <span className="text-gray-400">Asset:</span>
                    <span className="text-white">{formData.assetNumber}</span>
                  </div>
                )}
                <div className="flex justify-between">
                  <span className="text-gray-400">Photos:</span>
                  <span className="text-white">{formData.photos.length} attached</span>
                </div>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Fixed Bottom Navigation */}
      <div className="fixed bottom-0 left-0 right-0 bg-black/50 backdrop-blur-xl border-t border-white/10 p-4">
        <div className="max-w-2xl mx-auto flex gap-3">
          {step > 1 && (
            <button
              type="button"
              onClick={() => setStep((s) => (s - 1) as Step)}
              className="px-6 py-3.5 bg-white/10 hover:bg-white/20 text-white rounded-xl font-medium transition-colors flex items-center gap-2"
            >
              <ChevronLeft className="w-5 h-5" />
              Back
            </button>
          )}
          
          {step < 4 ? (
            <button
              type="button"
              onClick={() => setStep((s) => (s + 1) as Step)}
              disabled={!canProceed()}
              className="flex-1 px-6 py-3.5 bg-gradient-to-r from-purple-500 to-cyan-500 hover:from-purple-600 hover:to-cyan-600 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-xl font-semibold transition-all flex items-center justify-center gap-2"
            >
              Continue
              <ChevronRight className="w-5 h-5" />
            </button>
          ) : (
            <button
              type="button"
              onClick={handleSubmit}
              disabled={isSubmitting}
              className="flex-1 px-6 py-3.5 bg-gradient-to-r from-green-500 to-emerald-500 hover:from-green-600 hover:to-emerald-600 disabled:opacity-50 text-white rounded-xl font-semibold transition-all flex items-center justify-center gap-2"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  Submitting...
                </>
              ) : (
                <>
                  <Check className="w-5 h-5" />
                  Submit Report
                </>
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
