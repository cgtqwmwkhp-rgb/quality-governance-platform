import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  AlertTriangle,
  Phone,
  MapPin,
  Send,
  Shield,
  ArrowLeft,
  Loader2,
  CheckCircle,
  Mic,
  MicOff,
  Camera,
  X,
  Zap,
  Clock,
  Users,
  Heart,
} from 'lucide-react';

// Pulsing emergency background
const EmergencyBackground = () => (
  <div className="fixed inset-0 -z-10 overflow-hidden">
    <div className="absolute inset-0 bg-gradient-to-br from-red-950 via-red-900 to-slate-900" />
    <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_50%,rgba(239,68,68,0.3),transparent_50%)] animate-pulse" />
    <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjAiIGhlaWdodD0iNjAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PGRlZnM+PHBhdHRlcm4gaWQ9ImdyaWQiIHdpZHRoPSI2MCIgaGVpZ2h0PSI2MCIgcGF0dGVyblVuaXRzPSJ1c2VyU3BhY2VPblVzZSI+PHBhdGggZD0iTSA2MCAwIEwgMCAwIDAgNjAiIGZpbGw9Im5vbmUiIHN0cm9rZT0icmdiYSgyNTUsMjU1LDI1NSwwLjAzKSIgc3Ryb2tlLXdpZHRoPSIxIi8+PC9wYXR0ZXJuPjwvZGVmcz48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSJ1cmwoI2dyaWQpIi8+PC9zdmc+')] opacity-40" />
  </div>
);

// Emergency type card
const EmergencyTypeCard = ({
  icon: Icon,
  title,
  description,
  color,
  onClick,
  selected,
}: {
  icon: any;
  title: string;
  description: string;
  color: string;
  onClick: () => void;
  selected: boolean;
}) => (
  <button
    onClick={onClick}
    className={`p-4 rounded-2xl border-2 text-left transition-all ${
      selected
        ? 'border-white bg-white/20 scale-105'
        : 'border-white/20 bg-white/5 hover:bg-white/10'
    }`}
  >
    <div className={`w-12 h-12 rounded-xl flex items-center justify-center mb-3 ${color}`}>
      <Icon className="w-6 h-6 text-white" />
    </div>
    <h3 className="font-bold text-white">{title}</h3>
    <p className="text-xs text-gray-300 mt-1">{description}</p>
  </button>
);

export default function PortalSOS() {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [emergencyType, setEmergencyType] = useState<string | null>(null);
  const [description, setDescription] = useState('');
  const [location, setLocation] = useState<{ lat: number; lng: number; address: string } | null>(null);
  const [isLocating, setIsLocating] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [referenceNumber, setReferenceNumber] = useState('');
  const [photos, setPhotos] = useState<string[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const emergencyTypes = [
    { id: 'injury', icon: Heart, title: 'Injury', description: 'Someone is hurt', color: 'bg-red-500' },
    { id: 'fire', icon: Zap, title: 'Fire/Hazard', description: 'Fire or dangerous situation', color: 'bg-orange-500' },
    { id: 'security', icon: Shield, title: 'Security', description: 'Threat or suspicious activity', color: 'bg-purple-500' },
    { id: 'equipment', icon: AlertTriangle, title: 'Equipment', description: 'Dangerous equipment failure', color: 'bg-yellow-500' },
  ];

  // Auto-detect location on mount
  useEffect(() => {
    detectLocation();
  }, []);

  const detectLocation = () => {
    setIsLocating(true);
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        async (position) => {
          const { latitude, longitude } = position.coords;
          // In production, would reverse geocode
          setLocation({
            lat: latitude,
            lng: longitude,
            address: `${latitude.toFixed(4)}, ${longitude.toFixed(4)}`,
          });
          setIsLocating(false);
        },
        () => {
          setIsLocating(false);
        }
      );
    } else {
      setIsLocating(false);
    }
  };

  const handlePhotoCapture = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files) {
      Array.from(files).forEach((file) => {
        const reader = new FileReader();
        reader.onloadend = () => {
          setPhotos((prev) => [...prev, reader.result as string]);
        };
        reader.readAsDataURL(file);
      });
    }
  };

  const removePhoto = (index: number) => {
    setPhotos((prev) => prev.filter((_, i) => i !== index));
  };

  const toggleRecording = () => {
    // In production, would use Web Speech API
    setIsRecording(!isRecording);
    if (!isRecording) {
      // Simulate voice recording
      setTimeout(() => {
        setDescription((prev) => prev + ' [Voice note recorded]');
        setIsRecording(false);
      }, 3000);
    }
  };

  const handleSubmit = async () => {
    setIsSubmitting(true);
    // Simulate API call
    setTimeout(() => {
      const ref = `SOS-2026-${Math.floor(Math.random() * 9999).toString().padStart(4, '0')}`;
      setReferenceNumber(ref);
      setSubmitted(true);
      setIsSubmitting(false);
    }, 2000);
  };

  if (submitted) {
    return (
      <div className="min-h-screen relative flex items-center justify-center p-4">
        <EmergencyBackground />
        <div className="bg-white/10 backdrop-blur-xl border border-white/20 rounded-3xl p-8 max-w-md w-full text-center">
          <div className="w-20 h-20 mx-auto mb-6 bg-green-500 rounded-full flex items-center justify-center animate-bounce">
            <CheckCircle className="w-10 h-10 text-white" />
          </div>
          <h1 className="text-3xl font-bold text-white mb-2">Help is Coming!</h1>
          <p className="text-gray-300 mb-6">
            Your emergency has been reported. Emergency response team has been notified.
          </p>
          <div className="bg-white/10 rounded-xl p-4 mb-6">
            <p className="text-sm text-gray-400">Reference Number</p>
            <p className="text-2xl font-mono font-bold text-white">{referenceNumber}</p>
          </div>
          <div className="flex gap-3">
            <a
              href="tel:999"
              className="flex-1 flex items-center justify-center gap-2 px-4 py-3 bg-red-500 text-white font-bold rounded-xl hover:bg-red-600 transition-colors"
            >
              <Phone className="w-5 h-5" />
              Call 999
            </a>
            <button
              onClick={() => navigate('/portal')}
              className="flex-1 px-4 py-3 bg-white/10 text-white font-bold rounded-xl hover:bg-white/20 transition-colors"
            >
              Back to Portal
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen relative">
      <EmergencyBackground />

      {/* Header */}
      <header className="sticky top-0 z-50 bg-red-900/50 backdrop-blur-xl border-b border-red-500/30">
        <div className="max-w-lg mx-auto px-4 py-4 flex items-center justify-between">
          <button
            onClick={() => navigate('/portal')}
            className="w-10 h-10 flex items-center justify-center rounded-xl bg-white/5 hover:bg-white/10 transition-colors"
          >
            <ArrowLeft className="w-5 h-5 text-white" />
          </button>
          <div className="flex items-center gap-2 text-red-400">
            <div className="w-3 h-3 bg-red-500 rounded-full animate-pulse" />
            <span className="text-sm font-medium">EMERGENCY</span>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-lg mx-auto px-4 py-6 pb-12">
        {/* Emergency Icon */}
        <div className="text-center mb-8">
          <div className="inline-flex w-24 h-24 bg-red-500 rounded-full items-center justify-center mb-4 animate-pulse shadow-lg shadow-red-500/50">
            <AlertTriangle className="w-12 h-12 text-white" />
          </div>
          <h1 className="text-4xl font-bold text-white mb-2">Emergency Report</h1>
          <p className="text-red-200">Immediate response will be dispatched</p>
        </div>

        {/* Step 1: Emergency Type */}
        {step === 1 && (
          <div className="space-y-6">
            <h2 className="text-xl font-bold text-white text-center">What type of emergency?</h2>
            <div className="grid grid-cols-2 gap-4">
              {emergencyTypes.map((type) => (
                <EmergencyTypeCard
                  key={type.id}
                  {...type}
                  selected={emergencyType === type.id}
                  onClick={() => setEmergencyType(type.id)}
                />
              ))}
            </div>
            <button
              onClick={() => setStep(2)}
              disabled={!emergencyType}
              className="w-full py-4 bg-red-500 text-white font-bold text-lg rounded-2xl hover:bg-red-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Continue
            </button>
          </div>
        )}

        {/* Step 2: Details */}
        {step === 2 && (
          <div className="space-y-6">
            {/* Location */}
            <div className="bg-white/10 backdrop-blur-sm border border-white/20 rounded-2xl p-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-red-500/20 rounded-lg">
                    <MapPin className="w-5 h-5 text-red-400" />
                  </div>
                  <div>
                    <p className="text-sm text-gray-400">Your Location</p>
                    <p className="text-white font-medium">
                      {isLocating ? 'Detecting...' : location?.address || 'Location not available'}
                    </p>
                  </div>
                </div>
                <button
                  onClick={detectLocation}
                  className="px-3 py-1 bg-white/10 rounded-lg text-sm text-white hover:bg-white/20"
                >
                  {isLocating ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Refresh'}
                </button>
              </div>
            </div>

            {/* Description */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                What's happening? (optional)
              </label>
              <div className="relative">
                <textarea
                  rows={3}
                  placeholder="Describe the emergency..."
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-red-500 resize-none"
                />
                <button
                  onClick={toggleRecording}
                  className={`absolute bottom-3 right-3 p-2 rounded-lg transition-colors ${
                    isRecording ? 'bg-red-500 text-white animate-pulse' : 'bg-white/10 text-gray-400 hover:bg-white/20'
                  }`}
                >
                  {isRecording ? <MicOff className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
                </button>
              </div>
              {isRecording && (
                <p className="text-sm text-red-400 mt-2 animate-pulse">🎙️ Recording... Tap to stop</p>
              )}
            </div>

            {/* Photo Capture */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Add Photos (optional)
              </label>
              <div className="flex flex-wrap gap-3">
                {photos.map((photo, index) => (
                  <div key={index} className="relative w-20 h-20">
                    <img src={photo} alt="" className="w-full h-full object-cover rounded-xl" />
                    <button
                      onClick={() => removePhoto(index)}
                      className="absolute -top-2 -right-2 w-6 h-6 bg-red-500 rounded-full flex items-center justify-center"
                    >
                      <X className="w-4 h-4 text-white" />
                    </button>
                  </div>
                ))}
                <button
                  onClick={() => fileInputRef.current?.click()}
                  className="w-20 h-20 bg-white/5 border-2 border-dashed border-white/20 rounded-xl flex flex-col items-center justify-center gap-1 hover:bg-white/10 transition-colors"
                >
                  <Camera className="w-6 h-6 text-gray-400" />
                  <span className="text-xs text-gray-400">Add</span>
                </button>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  capture="environment"
                  multiple
                  onChange={handlePhotoCapture}
                  className="hidden"
                />
              </div>
            </div>

            {/* Submit */}
            <button
              onClick={handleSubmit}
              disabled={isSubmitting}
              className="w-full py-4 bg-red-500 text-white font-bold text-lg rounded-2xl hover:bg-red-600 transition-colors flex items-center justify-center gap-3 disabled:opacity-70"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="w-6 h-6 animate-spin" />
                  Sending Emergency Alert...
                </>
              ) : (
                <>
                  <Send className="w-6 h-6" />
                  Send Emergency Alert
                </>
              )}
            </button>

            {/* Emergency Services */}
            <div className="flex gap-3">
              <a
                href="tel:999"
                className="flex-1 flex items-center justify-center gap-2 px-4 py-3 bg-white/10 border border-white/20 text-white font-medium rounded-xl hover:bg-white/20 transition-colors"
              >
                <Phone className="w-5 h-5" />
                Call 999
              </a>
              <button
                onClick={() => setStep(1)}
                className="px-4 py-3 bg-white/10 border border-white/20 text-white font-medium rounded-xl hover:bg-white/20 transition-colors"
              >
                Back
              </button>
            </div>
          </div>
        )}

        {/* Quick Stats */}
        <div className="mt-8 grid grid-cols-3 gap-4 text-center">
          <div className="bg-white/5 rounded-xl p-3">
            <Clock className="w-5 h-5 text-red-400 mx-auto mb-1" />
            <p className="text-lg font-bold text-white">{'<2min'}</p>
            <p className="text-xs text-gray-400">Avg Response</p>
          </div>
          <div className="bg-white/5 rounded-xl p-3">
            <Users className="w-5 h-5 text-green-400 mx-auto mb-1" />
            <p className="text-lg font-bold text-white">24/7</p>
            <p className="text-xs text-gray-400">Team Available</p>
          </div>
          <div className="bg-white/5 rounded-xl p-3">
            <Shield className="w-5 h-5 text-blue-400 mx-auto mb-1" />
            <p className="text-lg font-bold text-white">100%</p>
            <p className="text-xs text-gray-400">Secure</p>
          </div>
        </div>
      </main>
    </div>
  );
}
