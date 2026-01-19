import { useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  AlertTriangle,
  AlertCircle,
  MessageSquare,
  Car,
  Shield,
  ChevronRight,
  Sparkles,
  Clock,
  CheckCircle2,
} from 'lucide-react';

// Report type options
const REPORT_TYPES = [
  {
    id: 'incident',
    path: '/portal/incident',
    icon: AlertTriangle,
    title: 'Injury / Accident',
    description: 'Report a workplace injury or accident that occurred',
    color: 'red',
    gradient: 'from-red-500 to-orange-500',
    features: ['Auto-detect location', 'Body part selector', 'Photo capture'],
    time: '3-5 mins',
  },
  {
    id: 'near-miss',
    path: '/portal/incident',
    icon: AlertCircle,
    title: 'Near Miss',
    description: 'Report a close call where no injury occurred',
    color: 'yellow',
    gradient: 'from-yellow-500 to-amber-500',
    features: ['Quick submission', 'Voice input', 'Anonymous option'],
    time: '2-3 mins',
  },
  {
    id: 'complaint',
    path: '/portal/incident',
    icon: MessageSquare,
    title: 'Customer Complaint',
    description: 'Log a customer concern or complaint',
    color: 'blue',
    gradient: 'from-blue-500 to-cyan-500',
    features: ['Complainant details', 'Contract lookup', 'Asset tracking'],
    time: '3-4 mins',
  },
  {
    id: 'rta',
    path: '/portal/rta',
    icon: Car,
    title: 'Road Traffic Accident',
    description: 'Report an RTA involving a company vehicle',
    color: 'orange',
    gradient: 'from-orange-500 to-red-500',
    features: ['Third-party details', 'Damage diagram', 'Insurance info'],
    time: '5-8 mins',
  },
];

export default function PortalReport() {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900/20 to-slate-900">
      {/* Header */}
      <header className="sticky top-0 z-50 bg-black/30 backdrop-blur-xl border-b border-white/10">
        <div className="max-w-2xl mx-auto px-4 py-4 flex items-center justify-between">
          <button
            onClick={() => navigate('/portal')}
            className="flex items-center gap-2 text-white hover:text-gray-300 transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
            <span className="hidden sm:inline">Back</span>
          </button>
          
          <div className="flex items-center gap-2">
            <Shield className="w-6 h-6 text-purple-400" />
            <span className="font-semibold text-white">Submit Report</span>
          </div>

          <div className="w-16" /> {/* Spacer for centering */}
        </div>
      </header>

      <main className="max-w-2xl mx-auto px-4 py-8">
        {/* Title */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-2 px-4 py-2 bg-purple-500/20 border border-purple-500/30 rounded-full text-purple-300 text-sm mb-4">
            <Sparkles className="w-4 h-4" />
            Mobile-Optimized Forms
          </div>
          <h1 className="text-3xl font-bold text-white mb-2">What would you like to report?</h1>
          <p className="text-gray-400">Choose the type of report that best matches your situation</p>
        </div>

        {/* Report Type Cards */}
        <div className="space-y-4">
          {REPORT_TYPES.map((type) => (
            <button
              key={type.id}
              onClick={() => navigate(type.path)}
              className="w-full bg-white/5 hover:bg-white/10 backdrop-blur-sm border border-white/10 hover:border-white/20 rounded-2xl p-5 text-left transition-all group"
            >
              <div className="flex items-start gap-4">
                {/* Icon */}
                <div className={`p-3 rounded-xl bg-gradient-to-br ${type.gradient} shadow-lg`}>
                  <type.icon className="w-6 h-6 text-white" />
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between mb-1">
                    <h3 className="text-lg font-semibold text-white group-hover:text-purple-300 transition-colors">
                      {type.title}
                    </h3>
                    <ChevronRight className="w-5 h-5 text-gray-500 group-hover:text-purple-400 group-hover:translate-x-1 transition-all" />
                  </div>
                  
                  <p className="text-gray-400 text-sm mb-3">{type.description}</p>
                  
                  {/* Features */}
                  <div className="flex flex-wrap gap-2 mb-2">
                    {type.features.map((feature) => (
                      <span
                        key={feature}
                        className="inline-flex items-center gap-1 px-2 py-0.5 bg-white/5 rounded-full text-xs text-gray-400"
                      >
                        <CheckCircle2 className="w-3 h-3 text-green-400" />
                        {feature}
                      </span>
                    ))}
                  </div>
                  
                  {/* Time estimate */}
                  <div className="flex items-center gap-1 text-xs text-gray-500">
                    <Clock className="w-3 h-3" />
                    Estimated: {type.time}
                  </div>
                </div>
              </div>
            </button>
          ))}
        </div>

        {/* Features Highlight */}
        <div className="mt-10 bg-gradient-to-r from-purple-500/10 to-cyan-500/10 border border-white/10 rounded-2xl p-6">
          <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-purple-400" />
            Optimized for Mobile Engineers
          </h3>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div className="flex items-start gap-2">
              <CheckCircle2 className="w-4 h-4 text-green-400 mt-0.5 flex-shrink-0" />
              <span className="text-gray-300">Fuzzy search dropdowns - find options fast</span>
            </div>
            <div className="flex items-start gap-2">
              <CheckCircle2 className="w-4 h-4 text-green-400 mt-0.5 flex-shrink-0" />
              <span className="text-gray-300">GPS auto-detection for location</span>
            </div>
            <div className="flex items-start gap-2">
              <CheckCircle2 className="w-4 h-4 text-green-400 mt-0.5 flex-shrink-0" />
              <span className="text-gray-300">Voice-to-text for descriptions</span>
            </div>
            <div className="flex items-start gap-2">
              <CheckCircle2 className="w-4 h-4 text-green-400 mt-0.5 flex-shrink-0" />
              <span className="text-gray-300">Direct camera capture for photos</span>
            </div>
            <div className="flex items-start gap-2">
              <CheckCircle2 className="w-4 h-4 text-green-400 mt-0.5 flex-shrink-0" />
              <span className="text-gray-300">Smart conditional fields</span>
            </div>
            <div className="flex items-start gap-2">
              <CheckCircle2 className="w-4 h-4 text-green-400 mt-0.5 flex-shrink-0" />
              <span className="text-gray-300">Large touch-friendly buttons</span>
            </div>
          </div>
        </div>

        {/* Help Text */}
        <p className="text-center text-gray-500 text-sm mt-8">
          Not sure which to choose? Start with the one that seems closest - you can always adjust during the form.
        </p>
      </main>
    </div>
  );
}
