import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { usePortalAuth } from '../contexts/PortalAuthContext';
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
  AlertCircle,
} from 'lucide-react';
import FuzzySearchDropdown from '../components/FuzzySearchDropdown';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { Textarea } from '../components/ui/Textarea';
import { cn } from '../helpers/utils';

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
  const { user } = usePortalAuth();
  const [step, setStep] = useState<Step>(1);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [geolocating, setGeolocating] = useState(false);
  const [submittedRef, setSubmittedRef] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

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

  // Pre-fill user details from SSO
  useEffect(() => {
    if (user) {
      setFormData((prev) => ({
        ...prev,
        employeeName: user.name || '',
      }));
    }
  }, [user]);

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

  // Submit - uses public portal endpoint (no auth required)
  const handleSubmit = async () => {
    setIsSubmitting(true);
    setError(null);
    
    try {
      // Build detailed RTA description
      const thirdPartiesDesc = formData.thirdParties.length > 0 
        ? `\n\nThird Parties:\n${formData.thirdParties.map((tp, i) => 
            `${i + 1}. ${tp.registration || 'Unknown'} - Driver: ${tp.driverName || 'Unknown'}`
          ).join('\n')}`
        : '';
      
      const fullDescription = `${formData.fullDescription}

Vehicle: ${formData.peVehicle === 'other' ? formData.peVehicleOther : formData.peVehicle}
Damage: ${formData.damageDescription}
Weather: ${formData.weather || 'Not specified'}
Road Conditions: ${formData.roadCondition || 'Not specified'}
Drivable: ${formData.isDrivable ? 'Yes' : 'No'}${thirdPartiesDesc}`;

      // Build portal report payload (RTA is submitted as incident type)
      const payload: PortalReportPayload = {
        report_type: 'incident', // RTA is a type of incident
        title: `RTA - ${formData.accidentType} - ${formData.location}`,
        description: fullDescription,
        location: formData.location,
        severity: formData.isDrivable === false ? 'critical' : 'high',
        reporter_name: formData.employeeName,
        reporter_email: user?.email || undefined,
        department: undefined,
        is_anonymous: false,
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
      <div className="min-h-screen bg-surface flex items-center justify-center p-4">
        <Card className="p-8 max-w-md w-full text-center">
          <div className="w-20 h-20 bg-success/10 rounded-full flex items-center justify-center mx-auto mb-6">
            <Check className="w-10 h-10 text-success" />
          </div>
          <h1 className="text-2xl font-bold text-foreground mb-2">RTA Report Submitted</h1>
          <p className="text-muted-foreground mb-6">Your reference number is:</p>
          <div className="bg-surface border border-border rounded-xl px-6 py-4 mb-6">
            <span className="text-2xl font-mono font-bold text-orange-600 dark:text-orange-400">{submittedRef}</span>
          </div>
          <div className="flex gap-3">
            <Button
              onClick={() => navigate('/portal/track/' + submittedRef)}
              className="flex-1 bg-orange-600 hover:bg-orange-700"
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
              <Car className="w-5 h-5 text-orange-600 dark:text-orange-400" />
              <span className="font-semibold text-foreground">RTA Report</span>
            </div>
            <div className="text-xs text-muted-foreground">Step {step} of {totalSteps}</div>
          </div>
        </div>
        
        <div className="h-1 bg-border">
          <div
            className="h-full bg-gradient-to-r from-orange-500 to-red-500 transition-all duration-300"
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
              <p className="text-muted-foreground text-sm">Driver and vehicle information</p>
            </div>

            <div>
              <label className="block text-sm font-medium text-foreground mb-2">Your Name *</label>
              <div className="relative">
                <User className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                <Input
                  value={formData.employeeName}
                  onChange={(e) => setFormData((prev) => ({ ...prev, employeeName: e.target.value }))}
                  placeholder="Full name..."
                  className="pl-10"
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
              <Input
                value={formData.peVehicleOther}
                onChange={(e) => setFormData((prev) => ({ ...prev, peVehicleOther: e.target.value.toUpperCase() }))}
                placeholder="Enter registration..."
                className="uppercase"
              />
            )}

            <div>
              <label className="block text-sm font-medium text-foreground mb-2">Any passengers? *</label>
              <div className="grid grid-cols-2 gap-3">
                {[true, false].map((val) => (
                  <button
                    key={String(val)}
                    type="button"
                    onClick={() => setFormData((prev) => ({ ...prev, hasPassengers: val }))}
                    className={cn(
                      'px-4 py-3 rounded-xl border-2 font-medium transition-all',
                      formData.hasPassengers === val
                        ? 'bg-orange-100 dark:bg-orange-900/20 border-orange-500 text-orange-700 dark:text-orange-400'
                        : 'bg-card border-border text-foreground hover:border-border-strong'
                    )}
                  >
                    {val ? 'Yes' : 'No'}
                  </button>
                ))}
              </div>
            </div>

            {formData.hasPassengers && (
              <div>
                <label className="block text-sm font-medium text-foreground mb-2">Passenger Details</label>
                <Input
                  value={formData.passengerDetails}
                  onChange={(e) => setFormData((prev) => ({ ...prev, passengerDetails: e.target.value }))}
                  placeholder="Name and reason in vehicle..."
                />
              </div>
            )}
          </div>
        )}

        {/* Step 2: Accident Info */}
        {step === 2 && (
          <div className="space-y-5">
            <div>
              <h1 className="text-xl font-bold text-foreground mb-1">Accident Details</h1>
              <p className="text-muted-foreground text-sm">When and where did it happen?</p>
            </div>

            <div>
              <label className="block text-sm font-medium text-foreground mb-2">Location *</label>
              <div className="relative">
                <MapPin className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                <Input
                  value={formData.location}
                  onChange={(e) => setFormData((prev) => ({ ...prev, location: e.target.value }))}
                  placeholder="Road name, junction..."
                  className="pl-10 pr-16"
                />
                <button
                  type="button"
                  onClick={detectLocation}
                  disabled={geolocating}
                  className="absolute right-2 top-1/2 -translate-y-1/2 p-2 bg-orange-100 dark:bg-orange-900/20 text-orange-600 dark:text-orange-400 rounded-lg"
                >
                  {geolocating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Navigation className="w-4 h-4" />}
                </button>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm font-medium text-foreground mb-2">Date</label>
                <div className="relative">
                  <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                  <Input
                    type="date"
                    value={formData.accidentDate}
                    onChange={(e) => setFormData((prev) => ({ ...prev, accidentDate: e.target.value }))}
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
                    value={formData.accidentTime}
                    onChange={(e) => setFormData((prev) => ({ ...prev, accidentTime: e.target.value }))}
                    className="pl-10"
                  />
                </div>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-foreground mb-2">Type of Accident *</label>
              <div className="grid grid-cols-3 gap-2">
                {ACCIDENT_TYPES.map((type) => (
                  <button
                    key={type.value}
                    type="button"
                    onClick={() => setFormData((prev) => ({ ...prev, accidentType: type.value }))}
                    className={cn(
                      'flex flex-col items-center gap-1 p-3 rounded-xl border-2 transition-all',
                      formData.accidentType === type.value
                        ? 'bg-orange-100 dark:bg-orange-900/20 border-orange-500'
                        : 'bg-card border-border hover:border-border-strong'
                    )}
                  >
                    <span className="text-xl">{type.icon}</span>
                    <span className="text-xs text-foreground">{type.label}</span>
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-foreground mb-2">Other vehicles involved?</label>
              <Card className="p-4">
                <div className="flex items-center justify-center gap-6">
                  <button
                    type="button"
                    onClick={() => setVehicleCount(formData.vehicleCount - 1)}
                    disabled={formData.vehicleCount === 0}
                    className="w-10 h-10 flex items-center justify-center bg-surface hover:bg-muted disabled:opacity-30 rounded-xl"
                  >
                    <Minus className="w-5 h-5 text-foreground" />
                  </button>
                  <div className="text-center">
                    <span className="text-3xl font-bold text-foreground">{formData.vehicleCount}</span>
                    <p className="text-muted-foreground text-xs">vehicles</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setVehicleCount(formData.vehicleCount + 1)}
                    disabled={formData.vehicleCount >= 3}
                    className="w-10 h-10 flex items-center justify-center bg-surface hover:bg-muted disabled:opacity-30 rounded-xl"
                  >
                    <Plus className="w-5 h-5 text-foreground" />
                  </button>
                </div>
              </Card>
            </div>
          </div>
        )}

        {/* Step 3: Third Party Details */}
        {step === 3 && (
          <div className="space-y-5">
            <div>
              <h1 className="text-xl font-bold text-foreground mb-1">
                {formData.vehicleCount === 0 ? 'Witnesses' : 'Third Party Details'}
              </h1>
              <p className="text-muted-foreground text-sm">
                {formData.vehicleCount === 0 ? 'Any witnesses to the accident?' : 'Details of other vehicles involved'}
              </p>
            </div>

            {formData.thirdParties.map((party, index) => (
              <Card key={index} className="p-4 space-y-3">
                <h3 className="font-semibold text-foreground flex items-center gap-2">
                  <Car className="w-4 h-4 text-orange-600 dark:text-orange-400" />
                  Vehicle {index + 1}
                </h3>
                <div className="grid grid-cols-2 gap-2">
                  <Input
                    value={party.registration}
                    onChange={(e) => updateThirdParty(index, 'registration', e.target.value.toUpperCase())}
                    placeholder="Reg..."
                    className="uppercase text-sm"
                  />
                  <Input
                    value={party.driverName}
                    onChange={(e) => updateThirdParty(index, 'driverName', e.target.value)}
                    placeholder="Driver name..."
                    className="text-sm"
                  />
                </div>
                <Input
                  type="tel"
                  value={party.driverPhone}
                  onChange={(e) => updateThirdParty(index, 'driverPhone', e.target.value)}
                  placeholder="Driver phone..."
                  className="text-sm"
                />
                <div className="grid grid-cols-2 gap-2">
                  <Input
                    value={party.insuranceCompany}
                    onChange={(e) => updateThirdParty(index, 'insuranceCompany', e.target.value)}
                    placeholder="Insurance..."
                    className="text-sm"
                  />
                  <Input
                    value={party.policyNumber}
                    onChange={(e) => updateThirdParty(index, 'policyNumber', e.target.value)}
                    placeholder="Policy #..."
                    className="text-sm"
                  />
                </div>
              </Card>
            ))}

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
                        ? 'bg-orange-100 dark:bg-orange-900/20 border-orange-500 text-orange-700 dark:text-orange-400'
                        : 'bg-card border-border text-foreground hover:border-border-strong'
                    )}
                  >
                    {val ? 'Yes' : 'No'}
                  </button>
                ))}
              </div>
            </div>

            {formData.hasWitnesses && (
              <Input
                value={formData.witnessDetails}
                onChange={(e) => setFormData((prev) => ({ ...prev, witnessDetails: e.target.value }))}
                placeholder="Witness name and contact..."
              />
            )}
          </div>
        )}

        {/* Step 4: Damage & Conditions */}
        {step === 4 && (
          <div className="space-y-5">
            <div>
              <h1 className="text-xl font-bold text-foreground mb-1">Damage & Conditions</h1>
              <p className="text-muted-foreground text-sm">Impact and road conditions</p>
            </div>

            <div>
              <label className="block text-sm font-medium text-foreground mb-2">Point of Impact</label>
              <div className="grid grid-cols-4 gap-2">
                {IMPACT_POINTS.map((point) => (
                  <button
                    key={point.value}
                    type="button"
                    onClick={() => setFormData((prev) => ({ ...prev, impactPoint: point.value }))}
                    className={cn(
                      'px-2 py-2 rounded-lg border-2 text-xs font-medium transition-all',
                      formData.impactPoint === point.value
                        ? 'bg-orange-100 dark:bg-orange-900/20 border-orange-500 text-orange-700 dark:text-orange-400'
                        : 'bg-card border-border text-foreground hover:border-border-strong'
                    )}
                  >
                    {point.label}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-foreground mb-2">Damage Description *</label>
              <Textarea
                value={formData.damageDescription}
                onChange={(e) => setFormData((prev) => ({ ...prev, damageDescription: e.target.value }))}
                placeholder="Describe all damage..."
                rows={3}
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-foreground mb-2">Vehicle drivable?</label>
              <div className="grid grid-cols-2 gap-3">
                {[true, false].map((val) => (
                  <button
                    key={String(val)}
                    type="button"
                    onClick={() => setFormData((prev) => ({ ...prev, isDrivable: val }))}
                    className={cn(
                      'px-4 py-3 rounded-xl border-2 font-medium transition-all',
                      formData.isDrivable === val
                        ? val ? 'bg-success/10 border-success text-success' : 'bg-destructive/10 border-destructive text-destructive'
                        : 'bg-card border-border text-foreground hover:border-border-strong'
                    )}
                  >
                    {val ? 'Yes' : 'No'}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-foreground mb-2">Weather</label>
              <div className="grid grid-cols-6 gap-2">
                {WEATHER_OPTIONS.map((w) => (
                  <button
                    key={w.value}
                    type="button"
                    onClick={() => setFormData((prev) => ({ ...prev, weather: w.value }))}
                    className={cn(
                      'flex flex-col items-center gap-1 p-2 rounded-xl border-2 transition-all',
                      formData.weather === w.value
                        ? 'bg-orange-100 dark:bg-orange-900/20 border-orange-500'
                        : 'bg-card border-border hover:border-border-strong'
                    )}
                  >
                    <w.icon className={cn('w-5 h-5', formData.weather === w.value ? 'text-orange-600 dark:text-orange-400' : 'text-muted-foreground')} />
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-foreground mb-2">Road Condition</label>
              <div className="flex flex-wrap gap-2">
                {ROAD_CONDITIONS.map((cond) => (
                  <button
                    key={cond.value}
                    type="button"
                    onClick={() => setFormData((prev) => ({ ...prev, roadCondition: cond.value }))}
                    className={cn(
                      'px-4 py-2 rounded-full border-2 text-sm font-medium transition-all',
                      formData.roadCondition === cond.value
                        ? 'bg-orange-100 dark:bg-orange-900/20 border-orange-500 text-orange-700 dark:text-orange-400'
                        : 'bg-card border-border text-foreground hover:border-border-strong'
                    )}
                  >
                    {cond.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Photos */}
            <div>
              <label className="block text-sm font-medium text-foreground mb-2">Photos</label>
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

        {/* Step 5: Full Description */}
        {step === 5 && (
          <div className="space-y-5">
            <div>
              <h1 className="text-xl font-bold text-foreground mb-1">What Happened?</h1>
              <p className="text-muted-foreground text-sm">Describe the accident in full</p>
            </div>

            <div>
              <label className="block text-sm font-medium text-foreground mb-2">Full Description *</label>
              <div className="relative">
                <Textarea
                  value={formData.fullDescription}
                  onChange={(e) => setFormData((prev) => ({ ...prev, fullDescription: e.target.value }))}
                  placeholder="Describe exactly what happened..."
                  rows={6}
                />
                <button
                  type="button"
                  onClick={toggleVoiceRecording}
                  className={cn(
                    'absolute right-3 bottom-3 p-2 rounded-full transition-colors',
                    isRecording ? 'bg-destructive text-destructive-foreground animate-pulse' : 'bg-orange-100 dark:bg-orange-900/20 text-orange-600 dark:text-orange-400 hover:bg-orange-200 dark:hover:bg-orange-900/30'
                  )}
                >
                  {isRecording ? <MicOff className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
                </button>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm font-medium text-foreground mb-2">Purpose of Journey</label>
                <Input
                  value={formData.purposeOfJourney}
                  onChange={(e) => setFormData((prev) => ({ ...prev, purposeOfJourney: e.target.value }))}
                  placeholder="e.g. Work site visit"
                  className="text-sm"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-foreground mb-2">Speed at Impact</label>
                <Input
                  value={formData.speed}
                  onChange={(e) => setFormData((prev) => ({ ...prev, speed: e.target.value }))}
                  placeholder="e.g. 20 mph"
                  className="text-sm"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => setFormData((prev) => ({ ...prev, hasDashcam: !prev.hasDashcam }))}
                className={cn(
                  'flex items-center gap-2 p-3 rounded-xl border-2 transition-all',
                  formData.hasDashcam ? 'bg-success/10 border-success' : 'bg-card border-border hover:border-border-strong'
                )}
              >
                <Video className={cn('w-5 h-5', formData.hasDashcam ? 'text-success' : 'text-muted-foreground')} />
                <span className="text-sm text-foreground">Dashcam</span>
              </button>
              <button
                type="button"
                onClick={() => setFormData((prev) => ({ ...prev, hasCCTV: !prev.hasCCTV }))}
                className={cn(
                  'flex items-center gap-2 p-3 rounded-xl border-2 transition-all',
                  formData.hasCCTV ? 'bg-success/10 border-success' : 'bg-card border-border hover:border-border-strong'
                )}
              >
                <Eye className={cn('w-5 h-5', formData.hasCCTV ? 'text-success' : 'text-muted-foreground')} />
                <span className="text-sm text-foreground">CCTV Nearby</span>
              </button>
            </div>

            <div>
              <label className="block text-sm font-medium text-foreground mb-2">Emergency Services?</label>
              <div className="relative">
                <Siren className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                <Input
                  value={formData.emergencyServices}
                  onChange={(e) => setFormData((prev) => ({ ...prev, emergencyServices: e.target.value }))}
                  placeholder="No / Police / Ambulance..."
                  className="pl-10"
                />
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
              <AlertCircle className="w-5 h-5 text-destructive flex-shrink-0 mt-0.5" />
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
              className="flex-1 bg-orange-600 hover:bg-orange-700"
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
