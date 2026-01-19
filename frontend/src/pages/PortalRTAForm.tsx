import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  Car,
  Truck,
  MapPin,
  Camera,
  Mic,
  MicOff,
  Calendar,
  Clock,
  User,
  Phone,
  FileText,
  Check,
  ChevronRight,
  ChevronLeft,
  Loader2,
  Shield,
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
  Users,
  Siren,
  Video,
  Navigation,
} from 'lucide-react';
import FuzzySearchDropdown from '../components/FuzzySearchDropdown';

// PE Vehicle options (sample - would come from API)
const PE_VEHICLES = [
  { value: 'HV72ZUA', label: 'HV72ZUA', sublabel: 'Renault Trafic' },
  { value: 'ML23RRZ', label: 'ML23RRZ', sublabel: 'Ford Transit' },
  { value: 'LD24VLP', label: 'LD24VLP', sublabel: 'Mercedes Sprinter' },
  { value: 'LA72VSM', label: 'LA72VSM', sublabel: 'VW Transporter' },
  { value: 'DY72EOX', label: 'DY72EOX', sublabel: 'Peugeot Expert' },
  { value: 'BD21NTJ', label: 'BD21NTJ', sublabel: 'Renault Master' },
  { value: 'GK65RKA', label: 'GK65RKA', sublabel: 'Iveco Daily' },
  { value: 'other', label: 'Other', sublabel: 'Enter manually' },
];

// Accident types with icons
const ACCIDENT_TYPES = [
  { value: 'rear-end', label: 'Rear-end', icon: '🚗💥🚙', desc: 'Hit from behind or hit vehicle in front' },
  { value: 'side-impact', label: 'Side Impact', icon: '🚗💥', desc: 'T-bone or sideswipe' },
  { value: 'head-on', label: 'Head-on', icon: '🚗💥🚗', desc: 'Front to front collision' },
  { value: 'animal', label: 'Animal', icon: '🦌', desc: 'Collision with animal' },
  { value: 'hit-run', label: 'Hit & Run', icon: '🏃', desc: 'Other party fled scene' },
  { value: 'single-vehicle', label: 'Single Vehicle', icon: '🚗', desc: 'Only your vehicle involved' },
  { value: 'parking', label: 'Parking', icon: '🅿️', desc: 'Parking lot incident' },
];

// Point of impact options
const IMPACT_POINTS = [
  { value: 'front', label: 'Front', position: 'top-0 left-1/2 -translate-x-1/2' },
  { value: 'front-left', label: 'Front Left', position: 'top-0 left-0' },
  { value: 'front-right', label: 'Front Right', position: 'top-0 right-0' },
  { value: 'left', label: 'Left Side', position: 'top-1/2 left-0 -translate-y-1/2' },
  { value: 'right', label: 'Right Side', position: 'top-1/2 right-0 -translate-y-1/2' },
  { value: 'rear', label: 'Rear', position: 'bottom-0 left-1/2 -translate-x-1/2' },
  { value: 'rear-left', label: 'Rear Left', position: 'bottom-0 left-0' },
  { value: 'rear-right', label: 'Rear Right', position: 'bottom-0 right-0' },
];

// Weather options
const WEATHER_OPTIONS = [
  { value: 'clear', label: 'Clear/Sunny', icon: Sun },
  { value: 'cloudy', label: 'Cloudy', icon: Cloud },
  { value: 'rain', label: 'Rain', icon: CloudRain },
  { value: 'fog', label: 'Fog/Mist', icon: CloudFog },
  { value: 'wind', label: 'Windy', icon: Wind },
  { value: 'snow', label: 'Snow/Ice', icon: Snowflake },
];

// Road conditions
const ROAD_CONDITIONS = [
  { value: 'dry', label: 'Dry' },
  { value: 'wet', label: 'Wet' },
  { value: 'icy', label: 'Icy' },
  { value: 'muddy', label: 'Muddy' },
  { value: 'gravel', label: 'Gravel/Loose' },
];

interface ThirdPartyVehicle {
  registration: string;
  driverName: string;
  driverPhone: string;
  driverAddress: string;
  passengerCount: number;
  passengerNames: string;
  insuranceCompany: string;
  policyNumber: string;
  damageDescription: string;
  hasInjuries: boolean | null;
  injuryDetails: string;
  photos: File[];
}

interface FormData {
  // Employee & Vehicle
  employeeName: string;
  peVehicleReg: string;
  peVehicleRegOther: string;
  hasPassengers: boolean | null;
  passengerDetails: string;
  
  // Location & Time
  location: string;
  accidentDate: string;
  accidentTime: string;
  
  // Accident Details
  vehicleCount: number;
  thirdPartyVehicles: ThirdPartyVehicle[];
  accidentType: string;
  impactPoint: string;
  damageDescription: string;
  isVehicleDrivable: boolean | null;
  
  // Conditions
  weather: string;
  roadCondition: string;
  
  // Additional Info
  hasWitnesses: boolean | null;
  witnessDetails: string;
  emergencyServicesAttended: string;
  policeReference: string;
  purposeOfJourney: string;
  speedAtImpact: string;
  hasDashcam: boolean | null;
  hasCCTV: boolean | null;
  cctvDetails: string;
  
  // Description
  fullDescription: string;
  
  // Photos
  vehiclePhotos: File[];
  additionalPhotos: File[];
}

type Step = 1 | 2 | 3 | 4 | 5;

export default function PortalRTAForm() {
  const navigate = useNavigate();
  const [step, setStep] = useState<Step>(1);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [geolocating, setGeolocating] = useState(false);
  const [submittedRef, setSubmittedRef] = useState<string | null>(null);

  const createEmptyThirdParty = (): ThirdPartyVehicle => ({
    registration: '',
    driverName: '',
    driverPhone: '',
    driverAddress: '',
    passengerCount: 0,
    passengerNames: '',
    insuranceCompany: '',
    policyNumber: '',
    damageDescription: '',
    hasInjuries: null,
    injuryDetails: '',
    photos: [],
  });

  const [formData, setFormData] = useState<FormData>({
    employeeName: '',
    peVehicleReg: '',
    peVehicleRegOther: '',
    hasPassengers: null,
    passengerDetails: '',
    location: '',
    accidentDate: new Date().toISOString().split('T')[0],
    accidentTime: new Date().toTimeString().slice(0, 5),
    vehicleCount: 0,
    thirdPartyVehicles: [],
    accidentType: '',
    impactPoint: '',
    damageDescription: '',
    isVehicleDrivable: null,
    weather: '',
    roadCondition: '',
    hasWitnesses: null,
    witnessDetails: '',
    emergencyServicesAttended: '',
    policeReference: '',
    purposeOfJourney: '',
    speedAtImpact: '',
    hasDashcam: null,
    hasCCTV: null,
    cctvDetails: '',
    fullDescription: '',
    vehiclePhotos: [],
    additionalPhotos: [],
  });

  // Update vehicle count and adjust third party array
  const setVehicleCount = (count: number) => {
    const newCount = Math.max(0, Math.min(3, count));
    const currentVehicles = [...formData.thirdPartyVehicles];
    
    while (currentVehicles.length < newCount) {
      currentVehicles.push(createEmptyThirdParty());
    }
    while (currentVehicles.length > newCount) {
      currentVehicles.pop();
    }
    
    setFormData((prev) => ({
      ...prev,
      vehicleCount: newCount,
      thirdPartyVehicles: currentVehicles,
    }));
  };

  // Update third party vehicle data
  const updateThirdParty = (index: number, field: keyof ThirdPartyVehicle, value: any) => {
    const updated = [...formData.thirdPartyVehicles];
    updated[index] = { ...updated[index], [field]: value };
    setFormData((prev) => ({ ...prev, thirdPartyVehicles: updated }));
  };

  // Auto-detect location
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
          alert('Could not detect location. Please enter manually.');
        }
      );
    }
  };

  // Voice recording
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
          setFormData((prev) => ({ ...prev, fullDescription: prev.fullDescription + ' ' + transcript }));
        };
        recognition.start();
        setIsRecording(true);
      } else {
        recognition.stop();
        setIsRecording(false);
      }
    }
  };

  // Photo handling
  const handlePhotoCapture = (field: 'vehiclePhotos' | 'additionalPhotos') => (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const newPhotos = Array.from(e.target.files);
      setFormData((prev) => ({ ...prev, [field]: [...prev[field], ...newPhotos] }));
    }
  };

  const removePhoto = (field: 'vehiclePhotos' | 'additionalPhotos', index: number) => {
    setFormData((prev) => ({
      ...prev,
      [field]: prev[field].filter((_, i) => i !== index),
    }));
  };

  // Submit
  const handleSubmit = async () => {
    setIsSubmitting(true);
    try {
      const refNumber = `RTA-${Date.now().toString(36).toUpperCase()}`;
      await new Promise((resolve) => setTimeout(resolve, 1500));
      setSubmittedRef(refNumber);
    } catch {
      alert('Failed to submit. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  // Validation
  const canProceed = (): boolean => {
    switch (step) {
      case 1:
        return !!formData.employeeName && !!formData.peVehicleReg && formData.hasPassengers !== null;
      case 2:
        return !!formData.location && !!formData.accidentType;
      case 3:
        if (formData.vehicleCount > 0) {
          return formData.thirdPartyVehicles.every((v) => v.driverName || v.registration);
        }
        return true;
      case 4:
        return !!formData.damageDescription;
      case 5:
        return !!formData.fullDescription;
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
          <h1 className="text-2xl font-bold text-white mb-2">RTA Report Submitted</h1>
          <p className="text-gray-400 mb-6">Your reference number is:</p>
          <div className="bg-white/5 border border-white/20 rounded-xl px-6 py-4 mb-6">
            <span className="text-2xl font-mono font-bold text-purple-400">{submittedRef}</span>
          </div>
          <p className="text-sm text-gray-500 mb-6">
            Keep this reference for insurance and tracking purposes
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
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-orange-900/10 to-slate-900">
      {/* Header */}
      <header className="sticky top-0 z-50 bg-black/30 backdrop-blur-xl border-b border-white/10">
        <div className="max-w-2xl mx-auto px-4 py-4 flex items-center justify-between">
          <button
            onClick={() => (step === 1 ? navigate('/portal') : setStep((s) => (s - 1) as Step))}
            className="flex items-center gap-2 text-white hover:text-gray-300 transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          
          <div className="flex items-center gap-2">
            <Car className="w-6 h-6 text-orange-400" />
            <span className="font-semibold text-white">RTA Report</span>
          </div>

          <div className="text-sm text-gray-400">
            Step {step}/5
          </div>
        </div>
        
        <div className="h-1 bg-white/10">
          <div
            className="h-full bg-gradient-to-r from-orange-500 to-red-500 transition-all duration-300"
            style={{ width: `${(step / 5) * 100}%` }}
          />
        </div>
      </header>

      <main className="max-w-2xl mx-auto px-4 py-6 pb-32">
        {/* Step 1: Your Details */}
        {step === 1 && (
          <div className="space-y-6 animate-in fade-in slide-in-from-right duration-300">
            <div>
              <h1 className="text-2xl font-bold text-white mb-2">Your Details</h1>
              <p className="text-gray-400">Driver and vehicle information</p>
            </div>

            {/* Employee Name */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Your Name <span className="text-red-400">*</span>
              </label>
              <div className="relative">
                <User className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                <input
                  type="text"
                  value={formData.employeeName}
                  onChange={(e) => setFormData((prev) => ({ ...prev, employeeName: e.target.value }))}
                  placeholder="Your full name..."
                  className="w-full pl-12 pr-4 py-3.5 bg-white/5 border border-white/20 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-orange-500"
                />
              </div>
            </div>

            {/* Vehicle Registration */}
            <FuzzySearchDropdown
              label="PE Vehicle Registration"
              options={PE_VEHICLES}
              value={formData.peVehicleReg}
              onChange={(val) => setFormData((prev) => ({ ...prev, peVehicleReg: val }))}
              placeholder="Search vehicle..."
              required
            />

            {formData.peVehicleReg === 'other' && (
              <input
                type="text"
                value={formData.peVehicleRegOther}
                onChange={(e) => setFormData((prev) => ({ ...prev, peVehicleRegOther: e.target.value.toUpperCase() }))}
                placeholder="Enter registration..."
                className="w-full px-4 py-3.5 bg-white/5 border border-white/20 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-orange-500 uppercase"
              />
            )}

            {/* Passengers */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-3">
                Did you have any passengers? <span className="text-red-400">*</span>
              </label>
              <div className="grid grid-cols-2 gap-3">
                {[
                  { value: true, label: 'Yes' },
                  { value: false, label: 'No' },
                ].map((opt) => (
                  <button
                    key={String(opt.value)}
                    type="button"
                    onClick={() => setFormData((prev) => ({ ...prev, hasPassengers: opt.value }))}
                    className={`
                      px-4 py-3 rounded-xl border-2 transition-all font-medium
                      ${formData.hasPassengers === opt.value
                        ? 'bg-orange-500/20 border-orange-500 text-white'
                        : 'bg-white/5 border-white/20 text-gray-300 hover:bg-white/10'
                      }
                    `}
                  >
                    {opt.label}
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
                  placeholder="Name and reason for being in vehicle..."
                  className="w-full px-4 py-3.5 bg-white/5 border border-white/20 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-orange-500"
                />
              </div>
            )}
          </div>
        )}

        {/* Step 2: Accident Details */}
        {step === 2 && (
          <div className="space-y-6 animate-in fade-in slide-in-from-right duration-300">
            <div>
              <h1 className="text-2xl font-bold text-white mb-2">Accident Details</h1>
              <p className="text-gray-400">When and where did it happen?</p>
            </div>

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
                  placeholder="Road name, junction, postcode..."
                  className="w-full pl-12 pr-24 py-3.5 bg-white/5 border border-white/20 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-orange-500"
                />
                <button
                  type="button"
                  onClick={detectLocation}
                  disabled={geolocating}
                  className="absolute right-2 top-1/2 -translate-y-1/2 px-3 py-1.5 bg-orange-500/20 hover:bg-orange-500/30 text-orange-400 rounded-lg text-sm font-medium transition-colors flex items-center gap-1"
                >
                  {geolocating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Navigation className="w-4 h-4" />}
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
                    value={formData.accidentDate}
                    onChange={(e) => setFormData((prev) => ({ ...prev, accidentDate: e.target.value }))}
                    className="w-full pl-12 pr-4 py-3.5 bg-white/5 border border-white/20 rounded-xl text-white focus:outline-none focus:border-orange-500"
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">Time</label>
                <div className="relative">
                  <Clock className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                  <input
                    type="time"
                    value={formData.accidentTime}
                    onChange={(e) => setFormData((prev) => ({ ...prev, accidentTime: e.target.value }))}
                    className="w-full pl-12 pr-4 py-3.5 bg-white/5 border border-white/20 rounded-xl text-white focus:outline-none focus:border-orange-500"
                  />
                </div>
              </div>
            </div>

            {/* Accident Type */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-3">
                Type of Accident <span className="text-red-400">*</span>
              </label>
              <div className="grid grid-cols-2 gap-2">
                {ACCIDENT_TYPES.map((type) => (
                  <button
                    key={type.value}
                    type="button"
                    onClick={() => setFormData((prev) => ({ ...prev, accidentType: type.value }))}
                    className={`
                      flex items-center gap-3 p-3 rounded-xl border-2 transition-all text-left
                      ${formData.accidentType === type.value
                        ? 'bg-orange-500/20 border-orange-500'
                        : 'bg-white/5 border-white/20 hover:bg-white/10'
                      }
                    `}
                  >
                    <span className="text-2xl">{type.icon}</span>
                    <div>
                      <div className="text-white font-medium text-sm">{type.label}</div>
                      <div className="text-gray-400 text-xs">{type.desc}</div>
                    </div>
                  </button>
                ))}
              </div>
            </div>

            {/* Number of other vehicles */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-3">
                How many other vehicles were involved?
              </label>
              <div className="flex items-center justify-center gap-6 bg-white/5 rounded-xl p-4">
                <button
                  type="button"
                  onClick={() => setVehicleCount(formData.vehicleCount - 1)}
                  disabled={formData.vehicleCount === 0}
                  className="w-12 h-12 flex items-center justify-center bg-white/10 hover:bg-white/20 disabled:opacity-30 rounded-xl transition-colors"
                >
                  <Minus className="w-6 h-6 text-white" />
                </button>
                <div className="text-center">
                  <span className="text-4xl font-bold text-white">{formData.vehicleCount}</span>
                  <p className="text-gray-400 text-sm mt-1">vehicles</p>
                </div>
                <button
                  type="button"
                  onClick={() => setVehicleCount(formData.vehicleCount + 1)}
                  disabled={formData.vehicleCount >= 3}
                  className="w-12 h-12 flex items-center justify-center bg-white/10 hover:bg-white/20 disabled:opacity-30 rounded-xl transition-colors"
                >
                  <Plus className="w-6 h-6 text-white" />
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Step 3: Third Party Details */}
        {step === 3 && (
          <div className="space-y-6 animate-in fade-in slide-in-from-right duration-300">
            <div>
              <h1 className="text-2xl font-bold text-white mb-2">
                {formData.vehicleCount === 0 ? 'Additional Information' : 'Third Party Details'}
              </h1>
              <p className="text-gray-400">
                {formData.vehicleCount === 0 ? 'Conditions and witnesses' : 'Details of other vehicles involved'}
              </p>
            </div>

            {formData.thirdPartyVehicles.map((vehicle, index) => (
              <div key={index} className="bg-white/5 border border-white/20 rounded-2xl p-4 space-y-4">
                <h3 className="font-semibold text-white flex items-center gap-2">
                  <Car className="w-5 h-5 text-orange-400" />
                  Vehicle {index + 1}
                </h3>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-medium text-gray-400 mb-1">Registration</label>
                    <input
                      type="text"
                      value={vehicle.registration}
                      onChange={(e) => updateThirdParty(index, 'registration', e.target.value.toUpperCase())}
                      placeholder="REG..."
                      className="w-full px-3 py-2.5 bg-white/5 border border-white/20 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-orange-500 text-sm uppercase"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-400 mb-1">Driver Name</label>
                    <input
                      type="text"
                      value={vehicle.driverName}
                      onChange={(e) => updateThirdParty(index, 'driverName', e.target.value)}
                      placeholder="Name..."
                      className="w-full px-3 py-2.5 bg-white/5 border border-white/20 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-orange-500 text-sm"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-medium text-gray-400 mb-1">Driver Phone</label>
                  <input
                    type="tel"
                    value={vehicle.driverPhone}
                    onChange={(e) => updateThirdParty(index, 'driverPhone', e.target.value)}
                    placeholder="Phone number..."
                    className="w-full px-3 py-2.5 bg-white/5 border border-white/20 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-orange-500 text-sm"
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-medium text-gray-400 mb-1">Insurance Company</label>
                    <input
                      type="text"
                      value={vehicle.insuranceCompany}
                      onChange={(e) => updateThirdParty(index, 'insuranceCompany', e.target.value)}
                      placeholder="Insurer..."
                      className="w-full px-3 py-2.5 bg-white/5 border border-white/20 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-orange-500 text-sm"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-400 mb-1">Policy Number</label>
                    <input
                      type="text"
                      value={vehicle.policyNumber}
                      onChange={(e) => updateThirdParty(index, 'policyNumber', e.target.value)}
                      placeholder="Policy #..."
                      className="w-full px-3 py-2.5 bg-white/5 border border-white/20 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-orange-500 text-sm"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-medium text-gray-400 mb-1">Damage to their vehicle</label>
                  <input
                    type="text"
                    value={vehicle.damageDescription}
                    onChange={(e) => updateThirdParty(index, 'damageDescription', e.target.value)}
                    placeholder="Describe damage..."
                    className="w-full px-3 py-2.5 bg-white/5 border border-white/20 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-orange-500 text-sm"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-gray-400 mb-2">Any injuries reported?</label>
                  <div className="grid grid-cols-2 gap-2">
                    {[false, true].map((hasInjury) => (
                      <button
                        key={String(hasInjury)}
                        type="button"
                        onClick={() => updateThirdParty(index, 'hasInjuries', hasInjury)}
                        className={`
                          px-3 py-2 rounded-lg border text-sm font-medium transition-all
                          ${vehicle.hasInjuries === hasInjury
                            ? hasInjury ? 'bg-red-500/20 border-red-500 text-red-400' : 'bg-green-500/20 border-green-500 text-green-400'
                            : 'bg-white/5 border-white/20 text-gray-300'
                          }
                        `}
                      >
                        {hasInjury ? 'Yes' : 'No'}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            ))}

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
                        ? 'bg-orange-500/20 border-orange-500 text-white'
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
                <label className="block text-sm font-medium text-gray-300 mb-2">Witness Details</label>
                <textarea
                  value={formData.witnessDetails}
                  onChange={(e) => setFormData((prev) => ({ ...prev, witnessDetails: e.target.value }))}
                  placeholder="Name, contact details..."
                  rows={2}
                  className="w-full px-4 py-3 bg-white/5 border border-white/20 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-orange-500 resize-none"
                />
              </div>
            )}
          </div>
        )}

        {/* Step 4: Damage & Conditions */}
        {step === 4 && (
          <div className="space-y-6 animate-in fade-in slide-in-from-right duration-300">
            <div>
              <h1 className="text-2xl font-bold text-white mb-2">Damage & Conditions</h1>
              <p className="text-gray-400">Impact details and road conditions</p>
            </div>

            {/* Point of Impact - Visual selector */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-3">
                Point of Impact on Your Vehicle
              </label>
              <div className="relative bg-white/5 border border-white/20 rounded-2xl p-8">
                {/* Vehicle diagram */}
                <div className="relative w-32 h-56 mx-auto">
                  {/* Vehicle body */}
                  <div className="absolute inset-0 bg-orange-500/20 rounded-lg border-2 border-orange-500/40" />
                  
                  {/* Impact points */}
                  {IMPACT_POINTS.map((point) => (
                    <button
                      key={point.value}
                      type="button"
                      onClick={() => setFormData((prev) => ({ ...prev, impactPoint: point.value }))}
                      className={`
                        absolute w-10 h-10 rounded-full flex items-center justify-center transition-all
                        ${point.position}
                        ${formData.impactPoint === point.value
                          ? 'bg-red-500 border-2 border-red-300 scale-110'
                          : 'bg-white/20 border border-white/40 hover:bg-white/30'
                        }
                      `}
                    >
                      <AlertTriangle className={`w-4 h-4 ${formData.impactPoint === point.value ? 'text-white' : 'text-gray-400'}`} />
                    </button>
                  ))}
                </div>
                
                {formData.impactPoint && (
                  <p className="text-center text-white mt-4">
                    Selected: <span className="text-orange-400 font-medium">{IMPACT_POINTS.find((p) => p.value === formData.impactPoint)?.label}</span>
                  </p>
                )}
              </div>
            </div>

            {/* Damage Description */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Damage Description <span className="text-red-400">*</span>
              </label>
              <textarea
                value={formData.damageDescription}
                onChange={(e) => setFormData((prev) => ({ ...prev, damageDescription: e.target.value }))}
                placeholder="Describe all damage to your vehicle..."
                rows={3}
                className="w-full px-4 py-3 bg-white/5 border border-white/20 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-orange-500 resize-none"
              />
            </div>

            {/* Vehicle Drivable */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-3">
                Is the vehicle still drivable?
              </label>
              <div className="grid grid-cols-2 gap-3">
                {[
                  { value: true, label: 'Yes', color: 'green' },
                  { value: false, label: 'No', color: 'red' },
                ].map((opt) => (
                  <button
                    key={String(opt.value)}
                    type="button"
                    onClick={() => setFormData((prev) => ({ ...prev, isVehicleDrivable: opt.value }))}
                    className={`
                      px-4 py-3 rounded-xl border-2 transition-all font-medium
                      ${formData.isVehicleDrivable === opt.value
                        ? opt.color === 'green' ? 'bg-green-500/20 border-green-500 text-green-400' : 'bg-red-500/20 border-red-500 text-red-400'
                        : 'bg-white/5 border-white/20 text-gray-300 hover:bg-white/10'
                      }
                    `}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Weather */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-3">Weather Conditions</label>
              <div className="grid grid-cols-3 gap-2">
                {WEATHER_OPTIONS.map((weather) => (
                  <button
                    key={weather.value}
                    type="button"
                    onClick={() => setFormData((prev) => ({ ...prev, weather: weather.value }))}
                    className={`
                      flex flex-col items-center gap-1 p-3 rounded-xl border-2 transition-all
                      ${formData.weather === weather.value
                        ? 'bg-orange-500/20 border-orange-500'
                        : 'bg-white/5 border-white/20 hover:bg-white/10'
                      }
                    `}
                  >
                    <weather.icon className={`w-6 h-6 ${formData.weather === weather.value ? 'text-orange-400' : 'text-gray-400'}`} />
                    <span className="text-xs text-white">{weather.label}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* Road Conditions */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-3">Road Conditions</label>
              <div className="flex flex-wrap gap-2">
                {ROAD_CONDITIONS.map((cond) => (
                  <button
                    key={cond.value}
                    type="button"
                    onClick={() => setFormData((prev) => ({ ...prev, roadCondition: cond.value }))}
                    className={`
                      px-4 py-2 rounded-full border-2 transition-all text-sm font-medium
                      ${formData.roadCondition === cond.value
                        ? 'bg-orange-500/20 border-orange-500 text-orange-400'
                        : 'bg-white/5 border-white/20 text-gray-300 hover:bg-white/10'
                      }
                    `}
                  >
                    {cond.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Vehicle Photos */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-3">
                Photos of Damage
              </label>
              <div className="grid grid-cols-4 gap-2">
                {formData.vehiclePhotos.map((photo, index) => (
                  <div key={index} className="relative aspect-square">
                    <img
                      src={URL.createObjectURL(photo)}
                      alt={`Damage ${index + 1}`}
                      className="w-full h-full object-cover rounded-xl"
                    />
                    <button
                      type="button"
                      onClick={() => removePhoto('vehiclePhotos', index)}
                      className="absolute -top-1 -right-1 w-5 h-5 bg-red-500 text-white rounded-full flex items-center justify-center"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </div>
                ))}
                <label className="aspect-square flex flex-col items-center justify-center bg-white/5 border-2 border-dashed border-white/20 rounded-xl cursor-pointer hover:bg-white/10 transition-all">
                  <Camera className="w-6 h-6 text-gray-400" />
                  <span className="text-xs text-gray-400 mt-1">Add</span>
                  <input
                    type="file"
                    accept="image/*"
                    capture="environment"
                    onChange={handlePhotoCapture('vehiclePhotos')}
                    className="hidden"
                    multiple
                  />
                </label>
              </div>
            </div>
          </div>
        )}

        {/* Step 5: Description & Submit */}
        {step === 5 && (
          <div className="space-y-6 animate-in fade-in slide-in-from-right duration-300">
            <div>
              <h1 className="text-2xl font-bold text-white mb-2">What Happened?</h1>
              <p className="text-gray-400">Describe the accident in your own words</p>
            </div>

            {/* Full Description */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Full Description <span className="text-red-400">*</span>
              </label>
              <div className="relative">
                <textarea
                  value={formData.fullDescription}
                  onChange={(e) => setFormData((prev) => ({ ...prev, fullDescription: e.target.value }))}
                  placeholder="Describe exactly what happened: where you were, what you were doing, what the other vehicle did, sequence of events..."
                  rows={6}
                  className="w-full px-4 py-3.5 bg-white/5 border border-white/20 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-orange-500 resize-none"
                />
                <button
                  type="button"
                  onClick={toggleVoiceRecording}
                  className={`
                    absolute right-3 bottom-3 p-2.5 rounded-full transition-all
                    ${isRecording
                      ? 'bg-red-500 text-white animate-pulse'
                      : 'bg-orange-500/20 text-orange-400 hover:bg-orange-500/30'
                    }
                  `}
                >
                  {isRecording ? <MicOff className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
                </button>
              </div>
            </div>

            {/* Additional Quick Fields */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">Purpose of Journey</label>
                <input
                  type="text"
                  value={formData.purposeOfJourney}
                  onChange={(e) => setFormData((prev) => ({ ...prev, purposeOfJourney: e.target.value }))}
                  placeholder="e.g. Work site visit"
                  className="w-full px-3 py-2.5 bg-white/5 border border-white/20 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-orange-500 text-sm"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">Speed at Impact</label>
                <input
                  type="text"
                  value={formData.speedAtImpact}
                  onChange={(e) => setFormData((prev) => ({ ...prev, speedAtImpact: e.target.value }))}
                  placeholder="e.g. 20 mph"
                  className="w-full px-3 py-2.5 bg-white/5 border border-white/20 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-orange-500 text-sm"
                />
              </div>
            </div>

            {/* Quick toggles */}
            <div className="grid grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => setFormData((prev) => ({ ...prev, hasDashcam: !prev.hasDashcam }))}
                className={`
                  flex items-center gap-3 p-3 rounded-xl border-2 transition-all
                  ${formData.hasDashcam
                    ? 'bg-green-500/20 border-green-500'
                    : 'bg-white/5 border-white/20 hover:bg-white/10'
                  }
                `}
              >
                <Video className={`w-5 h-5 ${formData.hasDashcam ? 'text-green-400' : 'text-gray-400'}`} />
                <span className="text-sm text-white">Dashcam Available</span>
              </button>
              
              <button
                type="button"
                onClick={() => setFormData((prev) => ({ ...prev, hasCCTV: !prev.hasCCTV }))}
                className={`
                  flex items-center gap-3 p-3 rounded-xl border-2 transition-all
                  ${formData.hasCCTV
                    ? 'bg-green-500/20 border-green-500'
                    : 'bg-white/5 border-white/20 hover:bg-white/10'
                  }
                `}
              >
                <Eye className={`w-5 h-5 ${formData.hasCCTV ? 'text-green-400' : 'text-gray-400'}`} />
                <span className="text-sm text-white">CCTV Nearby</span>
              </button>
            </div>

            {/* Emergency Services */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Emergency Services Attended?
              </label>
              <div className="relative">
                <Siren className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                <input
                  type="text"
                  value={formData.emergencyServicesAttended}
                  onChange={(e) => setFormData((prev) => ({ ...prev, emergencyServicesAttended: e.target.value }))}
                  placeholder="No / Police / Ambulance..."
                  className="w-full pl-12 pr-4 py-3 bg-white/5 border border-white/20 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-orange-500"
                />
              </div>
            </div>

            {formData.emergencyServicesAttended && formData.emergencyServicesAttended.toLowerCase().includes('police') && (
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">Police Reference</label>
                <input
                  type="text"
                  value={formData.policeReference}
                  onChange={(e) => setFormData((prev) => ({ ...prev, policeReference: e.target.value }))}
                  placeholder="Reference number..."
                  className="w-full px-4 py-3 bg-white/5 border border-white/20 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-orange-500"
                />
              </div>
            )}
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
          
          {step < 5 ? (
            <button
              type="button"
              onClick={() => setStep((s) => (s + 1) as Step)}
              disabled={!canProceed()}
              className="flex-1 px-6 py-3.5 bg-gradient-to-r from-orange-500 to-red-500 hover:from-orange-600 hover:to-red-600 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-xl font-semibold transition-all flex items-center justify-center gap-2"
            >
              Continue
              <ChevronRight className="w-5 h-5" />
            </button>
          ) : (
            <button
              type="button"
              onClick={handleSubmit}
              disabled={isSubmitting || !canProceed()}
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
                  Submit RTA Report
                </>
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
