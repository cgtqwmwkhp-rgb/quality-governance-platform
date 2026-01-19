import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  Car,
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
  Plus,
  Minus,
  X,
  AlertTriangle,
  CloudRain,
  Sun,
  Cloud,
  CloudFog,
  Wind,
  Snowflake,
  Eye,
  Siren,
  Video,
  Navigation,
} from 'lucide-react';
import FuzzySearchDropdown from '../components/FuzzySearchDropdown';

// PE Vehicle options
const PE_VEHICLES = [
  { value: 'HV72ZUA', label: 'HV72ZUA', sublabel: 'Renault Trafic' },
  { value: 'ML23RRZ', label: 'ML23RRZ', sublabel: 'Ford Transit' },
  { value: 'LD24VLP', label: 'LD24VLP', sublabel: 'Mercedes Sprinter' },
  { value: 'LA72VSM', label: 'LA72VSM', sublabel: 'VW Transporter' },
  { value: 'DY72EOX', label: 'DY72EOX', sublabel: 'Peugeot Expert' },
  { value: 'BD21NTJ', label: 'BD21NTJ', sublabel: 'Renault Master' },
  { value: 'other', label: 'Other', sublabel: 'Enter manually' },
];

// Accident types
const ACCIDENT_TYPES = [
  { value: 'rear-end', label: 'Rear-end', icon: '🚗💥🚙' },
  { value: 'side-impact', label: 'Side Impact', icon: '🚗💥' },
  { value: 'head-on', label: 'Head-on', icon: '🚗💥🚗' },
  { value: 'animal', label: 'Animal', icon: '🦌' },
  { value: 'hit-run', label: 'Hit & Run', icon: '🏃' },
  { value: 'single', label: 'Single Vehicle', icon: '🚗' },
];

// Impact points
const IMPACT_POINTS = [
  { value: 'front', label: 'Front' },
  { value: 'front-left', label: 'Front Left' },
  { value: 'front-right', label: 'Front Right' },
  { value: 'left', label: 'Left Side' },
  { value: 'right', label: 'Right Side' },
  { value: 'rear', label: 'Rear' },
  { value: 'rear-left', label: 'Rear Left' },
  { value: 'rear-right', label: 'Rear Right' },
];

// Weather options
const WEATHER_OPTIONS = [
  { value: 'clear', label: 'Clear', icon: Sun },
  { value: 'cloudy', label: 'Cloudy', icon: Cloud },
  { value: 'rain', label: 'Rain', icon: CloudRain },
  { value: 'fog', label: 'Fog', icon: CloudFog },
  { value: 'wind', label: 'Windy', icon: Wind },
  { value: 'snow', label: 'Snow', icon: Snowflake },
];

// Road conditions
const ROAD_CONDITIONS = [
  { value: 'dry', label: 'Dry' },
  { value: 'wet', label: 'Wet' },
  { value: 'icy', label: 'Icy' },
  { value: 'muddy', label: 'Muddy' },
];

interface ThirdParty {
  registration: string;
  driverName: string;
  driverPhone: string;
  insuranceCompany: string;
  policyNumber: string;
  damage: string;
  hasInjuries: boolean | null;
}

interface FormData {
  employeeName: string;
  peVehicle: string;
  peVehicleOther: string;
  hasPassengers: boolean | null;
  passengerDetails: string;
  location: string;
  accidentDate: string;
  accidentTime: string;
  accidentType: string;
  vehicleCount: number;
  thirdParties: ThirdParty[];
  impactPoint: string;
  damageDescription: string;
  isDrivable: boolean | null;
  weather: string;
  roadCondition: string;
  hasWitnesses: boolean | null;
  witnessDetails: string;
  emergencyServices: string;
  policeRef: string;
  purposeOfJourney: string;
  speed: string;
  hasDashcam: boolean | null;
  hasCCTV: boolean | null;
  fullDescription: string;
  photos: File[];
}

type Step = 1 | 2 | 3 | 4 | 5;

export default function PortalRTAForm() {
  const navigate = useNavigate();
  const [step, setStep] = useState<Step>(1);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [geolocating, setGeolocating] = useState(false);
  const [submittedRef, setSubmittedRef] = useState<string | null>(null);

  const createEmptyThirdParty = (): ThirdParty => ({
    registration: '',
    driverName: '',
    driverPhone: '',
    insuranceCompany: '',
    policyNumber: '',
    damage: '',
    hasInjuries: null,
  });

  const [formData, setFormData] = useState<FormData>({
    employeeName: '',
    peVehicle: '',
    peVehicleOther: '',
    hasPassengers: null,
    passengerDetails: '',
    location: '',
    accidentDate: new Date().toISOString().split('T')[0],
    accidentTime: new Date().toTimeString().slice(0, 5),
    accidentType: '',
    vehicleCount: 0,
    thirdParties: [],
    impactPoint: '',
    damageDescription: '',
    isDrivable: null,
    weather: '',
    roadCondition: '',
    hasWitnesses: null,
    witnessDetails: '',
    emergencyServices: '',
    policeRef: '',
    purposeOfJourney: '',
    speed: '',
    hasDashcam: null,
    hasCCTV: null,
    fullDescription: '',
    photos: [],
  });

  const totalSteps = 5;

  // Update vehicle count
  const setVehicleCount = (count: number) => {
    const newCount = Math.max(0, Math.min(3, count));
    const parties = [...formData.thirdParties];
    while (parties.length < newCount) parties.push(createEmptyThirdParty());
    while (parties.length > newCount) parties.pop();
    setFormData((prev) => ({ ...prev, vehicleCount: newCount, thirdParties: parties }));
  };

  // Update third party
  const updateThirdParty = (index: number, field: keyof ThirdParty, value: any) => {
    const updated = [...formData.thirdParties];
    updated[index] = { ...updated[index], [field]: value };
    setFormData((prev) => ({ ...prev, thirdParties: updated }));
  };

  // GPS detection
  const detectLocation = () => {
    setGeolocating(true);
    if ('geolocation' in navigator) {
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          setFormData((prev) => ({
            ...prev,
            location: `GPS: ${pos.coords.latitude.toFixed(6)}, ${pos.coords.longitude.toFixed(6)}`,
          }));
          setGeolocating(false);
        },
        () => {
          setGeolocating(false);
          alert('Could not detect location');
        }
      );
    }
  };

  // Voice recording toggle
  const toggleVoiceRecording = () => setIsRecording(!isRecording);

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
      const refNumber = `RTA-${Date.now().toString(36).toUpperCase()}`;
      await new Promise((resolve) => setTimeout(resolve, 1500));
      setSubmittedRef(refNumber);
    } catch {
      alert('Failed to submit');
    } finally {
      setIsSubmitting(false);
    }
  };

  // Validation
  const canProceed = (): boolean => {
    switch (step) {
      case 1: return !!formData.employeeName && !!formData.peVehicle && formData.hasPassengers !== null;
      case 2: return !!formData.location && !!formData.accidentType;
      case 3: return true;
      case 4: return !!formData.damageDescription;
      case 5: return !!formData.fullDescription;
      default: return false;
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
          <h1 className="text-2xl font-bold text-white mb-2">RTA Report Submitted</h1>
          <p className="text-gray-400 mb-6">Your reference number is:</p>
          <div className="bg-white/5 border border-white/20 rounded-xl px-6 py-4 mb-6">
            <span className="text-2xl font-mono font-bold text-orange-400">{submittedRef}</span>
          </div>
          <div className="flex gap-3">
            <button
              onClick={() => navigate('/portal/track/' + submittedRef)}
              className="flex-1 px-4 py-3 bg-orange-500 hover:bg-orange-600 text-white rounded-xl font-medium transition-colors"
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
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-orange-900/10 to-slate-900">
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
              <Car className="w-5 h-5 text-orange-400" />
              <span className="font-semibold text-white">RTA Report</span>
            </div>
            <div className="text-xs text-gray-500">Step {step} of {totalSteps}</div>
          </div>
        </div>
        
        <div className="h-1 bg-white/10">
          <div
            className="h-full bg-gradient-to-r from-orange-500 to-red-500 transition-all duration-300"
            style={{ width: `${(step / totalSteps) * 100}%` }}
          />
        </div>
      </header>

      <main className="max-w-lg mx-auto px-4 py-6 pb-28">
        {/* Step 1: Your Details */}
        {step === 1 && (
          <div className="space-y-5">
            <div>
              <h1 className="text-xl font-bold text-white mb-1">Your Details</h1>
              <p className="text-gray-400 text-sm">Driver and vehicle information</p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">Your Name *</label>
              <div className="relative">
                <User className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                <input
                  type="text"
                  value={formData.employeeName}
                  onChange={(e) => setFormData((prev) => ({ ...prev, employeeName: e.target.value }))}
                  placeholder="Full name..."
                  className="w-full pl-12 pr-4 py-3 bg-white/5 border border-white/20 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-orange-500"
                />
              </div>
            </div>

            <FuzzySearchDropdown
              label="PE Vehicle Registration"
              options={PE_VEHICLES}
              value={formData.peVehicle}
              onChange={(val) => setFormData((prev) => ({ ...prev, peVehicle: val }))}
              placeholder="Search vehicle..."
              required
            />

            {formData.peVehicle === 'other' && (
              <input
                type="text"
                value={formData.peVehicleOther}
                onChange={(e) => setFormData((prev) => ({ ...prev, peVehicleOther: e.target.value.toUpperCase() }))}
                placeholder="Enter registration..."
                className="w-full px-4 py-3 bg-white/5 border border-white/20 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-orange-500 uppercase"
              />
            )}

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">Any passengers? *</label>
              <div className="grid grid-cols-2 gap-3">
                {[true, false].map((val) => (
                  <button
                    key={String(val)}
                    type="button"
                    onClick={() => setFormData((prev) => ({ ...prev, hasPassengers: val }))}
                    className={`px-4 py-3 rounded-xl border-2 font-medium transition-all ${
                      formData.hasPassengers === val
                        ? 'bg-orange-500/20 border-orange-500 text-white'
                        : 'bg-white/5 border-white/20 text-gray-300'
                    }`}
                  >
                    {val ? 'Yes' : 'No'}
                  </button>
                ))}
              </div>
            </div>

            {formData.hasPassengers && (
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">Passenger Details</label>
                <input
                  type="text"
                  value={formData.passengerDetails}
                  onChange={(e) => setFormData((prev) => ({ ...prev, passengerDetails: e.target.value }))}
                  placeholder="Name and reason in vehicle..."
                  className="w-full px-4 py-3 bg-white/5 border border-white/20 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-orange-500"
                />
              </div>
            )}
          </div>
        )}

        {/* Step 2: Accident Info */}
        {step === 2 && (
          <div className="space-y-5">
            <div>
              <h1 className="text-xl font-bold text-white mb-1">Accident Details</h1>
              <p className="text-gray-400 text-sm">When and where did it happen?</p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">Location *</label>
              <div className="relative">
                <MapPin className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                <input
                  type="text"
                  value={formData.location}
                  onChange={(e) => setFormData((prev) => ({ ...prev, location: e.target.value }))}
                  placeholder="Road name, junction..."
                  className="w-full pl-12 pr-20 py-3 bg-white/5 border border-white/20 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-orange-500"
                />
                <button
                  type="button"
                  onClick={detectLocation}
                  disabled={geolocating}
                  className="absolute right-2 top-1/2 -translate-y-1/2 px-3 py-1.5 bg-orange-500/20 text-orange-400 rounded-lg text-sm font-medium"
                >
                  {geolocating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Navigation className="w-4 h-4" />}
                </button>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">Date</label>
                <div className="relative">
                  <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                  <input
                    type="date"
                    value={formData.accidentDate}
                    onChange={(e) => setFormData((prev) => ({ ...prev, accidentDate: e.target.value }))}
                    className="w-full pl-10 pr-3 py-3 bg-white/5 border border-white/20 rounded-xl text-white focus:outline-none focus:border-orange-500"
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">Time</label>
                <div className="relative">
                  <Clock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                  <input
                    type="time"
                    value={formData.accidentTime}
                    onChange={(e) => setFormData((prev) => ({ ...prev, accidentTime: e.target.value }))}
                    className="w-full pl-10 pr-3 py-3 bg-white/5 border border-white/20 rounded-xl text-white focus:outline-none focus:border-orange-500"
                  />
                </div>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">Type of Accident *</label>
              <div className="grid grid-cols-3 gap-2">
                {ACCIDENT_TYPES.map((type) => (
                  <button
                    key={type.value}
                    type="button"
                    onClick={() => setFormData((prev) => ({ ...prev, accidentType: type.value }))}
                    className={`flex flex-col items-center gap-1 p-3 rounded-xl border-2 transition-all ${
                      formData.accidentType === type.value
                        ? 'bg-orange-500/20 border-orange-500'
                        : 'bg-white/5 border-white/20'
                    }`}
                  >
                    <span className="text-xl">{type.icon}</span>
                    <span className="text-xs text-white">{type.label}</span>
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">Other vehicles involved?</label>
              <div className="flex items-center justify-center gap-6 bg-white/5 rounded-xl p-4">
                <button
                  type="button"
                  onClick={() => setVehicleCount(formData.vehicleCount - 1)}
                  disabled={formData.vehicleCount === 0}
                  className="w-10 h-10 flex items-center justify-center bg-white/10 hover:bg-white/20 disabled:opacity-30 rounded-xl"
                >
                  <Minus className="w-5 h-5 text-white" />
                </button>
                <div className="text-center">
                  <span className="text-3xl font-bold text-white">{formData.vehicleCount}</span>
                  <p className="text-gray-400 text-xs">vehicles</p>
                </div>
                <button
                  type="button"
                  onClick={() => setVehicleCount(formData.vehicleCount + 1)}
                  disabled={formData.vehicleCount >= 3}
                  className="w-10 h-10 flex items-center justify-center bg-white/10 hover:bg-white/20 disabled:opacity-30 rounded-xl"
                >
                  <Plus className="w-5 h-5 text-white" />
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Step 3: Third Party Details */}
        {step === 3 && (
          <div className="space-y-5">
            <div>
              <h1 className="text-xl font-bold text-white mb-1">
                {formData.vehicleCount === 0 ? 'Witnesses' : 'Third Party Details'}
              </h1>
              <p className="text-gray-400 text-sm">
                {formData.vehicleCount === 0 ? 'Any witnesses to the accident?' : 'Details of other vehicles involved'}
              </p>
            </div>

            {formData.thirdParties.map((party, index) => (
              <div key={index} className="bg-white/5 border border-white/20 rounded-2xl p-4 space-y-3">
                <h3 className="font-semibold text-white flex items-center gap-2">
                  <Car className="w-4 h-4 text-orange-400" />
                  Vehicle {index + 1}
                </h3>
                <div className="grid grid-cols-2 gap-2">
                  <input
                    type="text"
                    value={party.registration}
                    onChange={(e) => updateThirdParty(index, 'registration', e.target.value.toUpperCase())}
                    placeholder="Reg..."
                    className="px-3 py-2 bg-white/5 border border-white/20 rounded-lg text-white placeholder-gray-500 text-sm uppercase"
                  />
                  <input
                    type="text"
                    value={party.driverName}
                    onChange={(e) => updateThirdParty(index, 'driverName', e.target.value)}
                    placeholder="Driver name..."
                    className="px-3 py-2 bg-white/5 border border-white/20 rounded-lg text-white placeholder-gray-500 text-sm"
                  />
                </div>
                <input
                  type="tel"
                  value={party.driverPhone}
                  onChange={(e) => updateThirdParty(index, 'driverPhone', e.target.value)}
                  placeholder="Driver phone..."
                  className="w-full px-3 py-2 bg-white/5 border border-white/20 rounded-lg text-white placeholder-gray-500 text-sm"
                />
                <div className="grid grid-cols-2 gap-2">
                  <input
                    type="text"
                    value={party.insuranceCompany}
                    onChange={(e) => updateThirdParty(index, 'insuranceCompany', e.target.value)}
                    placeholder="Insurance..."
                    className="px-3 py-2 bg-white/5 border border-white/20 rounded-lg text-white placeholder-gray-500 text-sm"
                  />
                  <input
                    type="text"
                    value={party.policyNumber}
                    onChange={(e) => updateThirdParty(index, 'policyNumber', e.target.value)}
                    placeholder="Policy #..."
                    className="px-3 py-2 bg-white/5 border border-white/20 rounded-lg text-white placeholder-gray-500 text-sm"
                  />
                </div>
              </div>
            ))}

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
                        ? 'bg-orange-500/20 border-orange-500 text-white'
                        : 'bg-white/5 border-white/20 text-gray-300'
                    }`}
                  >
                    {val ? 'Yes' : 'No'}
                  </button>
                ))}
              </div>
            </div>

            {formData.hasWitnesses && (
              <input
                type="text"
                value={formData.witnessDetails}
                onChange={(e) => setFormData((prev) => ({ ...prev, witnessDetails: e.target.value }))}
                placeholder="Witness name and contact..."
                className="w-full px-4 py-3 bg-white/5 border border-white/20 rounded-xl text-white placeholder-gray-500"
              />
            )}
          </div>
        )}

        {/* Step 4: Damage & Conditions */}
        {step === 4 && (
          <div className="space-y-5">
            <div>
              <h1 className="text-xl font-bold text-white mb-1">Damage & Conditions</h1>
              <p className="text-gray-400 text-sm">Impact and road conditions</p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">Point of Impact</label>
              <div className="grid grid-cols-4 gap-2">
                {IMPACT_POINTS.map((point) => (
                  <button
                    key={point.value}
                    type="button"
                    onClick={() => setFormData((prev) => ({ ...prev, impactPoint: point.value }))}
                    className={`px-2 py-2 rounded-lg border-2 text-xs font-medium transition-all ${
                      formData.impactPoint === point.value
                        ? 'bg-orange-500/20 border-orange-500 text-orange-400'
                        : 'bg-white/5 border-white/20 text-gray-300'
                    }`}
                  >
                    {point.label}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">Damage Description *</label>
              <textarea
                value={formData.damageDescription}
                onChange={(e) => setFormData((prev) => ({ ...prev, damageDescription: e.target.value }))}
                placeholder="Describe all damage..."
                rows={3}
                className="w-full px-4 py-3 bg-white/5 border border-white/20 rounded-xl text-white placeholder-gray-500 resize-none"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">Vehicle drivable?</label>
              <div className="grid grid-cols-2 gap-3">
                {[true, false].map((val) => (
                  <button
                    key={String(val)}
                    type="button"
                    onClick={() => setFormData((prev) => ({ ...prev, isDrivable: val }))}
                    className={`px-4 py-3 rounded-xl border-2 font-medium transition-all ${
                      formData.isDrivable === val
                        ? val ? 'bg-green-500/20 border-green-500 text-green-400' : 'bg-red-500/20 border-red-500 text-red-400'
                        : 'bg-white/5 border-white/20 text-gray-300'
                    }`}
                  >
                    {val ? 'Yes' : 'No'}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">Weather</label>
              <div className="grid grid-cols-6 gap-2">
                {WEATHER_OPTIONS.map((w) => (
                  <button
                    key={w.value}
                    type="button"
                    onClick={() => setFormData((prev) => ({ ...prev, weather: w.value }))}
                    className={`flex flex-col items-center gap-1 p-2 rounded-xl border-2 transition-all ${
                      formData.weather === w.value
                        ? 'bg-orange-500/20 border-orange-500'
                        : 'bg-white/5 border-white/20'
                    }`}
                  >
                    <w.icon className={`w-5 h-5 ${formData.weather === w.value ? 'text-orange-400' : 'text-gray-400'}`} />
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">Road Condition</label>
              <div className="flex flex-wrap gap-2">
                {ROAD_CONDITIONS.map((cond) => (
                  <button
                    key={cond.value}
                    type="button"
                    onClick={() => setFormData((prev) => ({ ...prev, roadCondition: cond.value }))}
                    className={`px-4 py-2 rounded-full border-2 text-sm font-medium transition-all ${
                      formData.roadCondition === cond.value
                        ? 'bg-orange-500/20 border-orange-500 text-orange-400'
                        : 'bg-white/5 border-white/20 text-gray-300'
                    }`}
                  >
                    {cond.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Photos */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">Photos</label>
              <div className="grid grid-cols-4 gap-2">
                {formData.photos.map((photo, index) => (
                  <div key={index} className="relative aspect-square">
                    <img src={URL.createObjectURL(photo)} alt="" className="w-full h-full object-cover rounded-xl" />
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
                  <input type="file" accept="image/*" capture="environment" onChange={handlePhotoCapture} className="hidden" multiple />
                </label>
              </div>
            </div>
          </div>
        )}

        {/* Step 5: Full Description */}
        {step === 5 && (
          <div className="space-y-5">
            <div>
              <h1 className="text-xl font-bold text-white mb-1">What Happened?</h1>
              <p className="text-gray-400 text-sm">Describe the accident in full</p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">Full Description *</label>
              <div className="relative">
                <textarea
                  value={formData.fullDescription}
                  onChange={(e) => setFormData((prev) => ({ ...prev, fullDescription: e.target.value }))}
                  placeholder="Describe exactly what happened..."
                  rows={6}
                  className="w-full px-4 py-3 bg-white/5 border border-white/20 rounded-xl text-white placeholder-gray-500 resize-none"
                />
                <button
                  type="button"
                  onClick={toggleVoiceRecording}
                  className={`absolute right-3 bottom-3 p-2 rounded-full ${isRecording ? 'bg-red-500 animate-pulse' : 'bg-orange-500/20 text-orange-400'}`}
                >
                  {isRecording ? <MicOff className="w-5 h-5 text-white" /> : <Mic className="w-5 h-5" />}
                </button>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">Purpose of Journey</label>
                <input
                  type="text"
                  value={formData.purposeOfJourney}
                  onChange={(e) => setFormData((prev) => ({ ...prev, purposeOfJourney: e.target.value }))}
                  placeholder="e.g. Work site visit"
                  className="w-full px-3 py-2 bg-white/5 border border-white/20 rounded-lg text-white placeholder-gray-500 text-sm"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">Speed at Impact</label>
                <input
                  type="text"
                  value={formData.speed}
                  onChange={(e) => setFormData((prev) => ({ ...prev, speed: e.target.value }))}
                  placeholder="e.g. 20 mph"
                  className="w-full px-3 py-2 bg-white/5 border border-white/20 rounded-lg text-white placeholder-gray-500 text-sm"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => setFormData((prev) => ({ ...prev, hasDashcam: !prev.hasDashcam }))}
                className={`flex items-center gap-2 p-3 rounded-xl border-2 transition-all ${
                  formData.hasDashcam ? 'bg-green-500/20 border-green-500' : 'bg-white/5 border-white/20'
                }`}
              >
                <Video className={`w-5 h-5 ${formData.hasDashcam ? 'text-green-400' : 'text-gray-400'}`} />
                <span className="text-sm text-white">Dashcam</span>
              </button>
              <button
                type="button"
                onClick={() => setFormData((prev) => ({ ...prev, hasCCTV: !prev.hasCCTV }))}
                className={`flex items-center gap-2 p-3 rounded-xl border-2 transition-all ${
                  formData.hasCCTV ? 'bg-green-500/20 border-green-500' : 'bg-white/5 border-white/20'
                }`}
              >
                <Eye className={`w-5 h-5 ${formData.hasCCTV ? 'text-green-400' : 'text-gray-400'}`} />
                <span className="text-sm text-white">CCTV Nearby</span>
              </button>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">Emergency Services?</label>
              <div className="relative">
                <Siren className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                <input
                  type="text"
                  value={formData.emergencyServices}
                  onChange={(e) => setFormData((prev) => ({ ...prev, emergencyServices: e.target.value }))}
                  placeholder="No / Police / Ambulance..."
                  className="w-full pl-12 pr-4 py-3 bg-white/5 border border-white/20 rounded-xl text-white placeholder-gray-500"
                />
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
              className="flex-1 px-5 py-3 bg-gradient-to-r from-orange-500 to-red-500 disabled:opacity-50 text-white rounded-xl font-semibold transition-all flex items-center justify-center gap-2"
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
