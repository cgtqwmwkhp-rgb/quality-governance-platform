import { useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  AlertTriangle,
  AlertCircle,
  MessageSquare,
  Car,
  ChevronRight,
  Shield,
} from 'lucide-react';

// Report type options - Level 2 of the flow
const REPORT_TYPES = [
  {
    id: 'incident',
    path: '/portal/report/incident',
    icon: AlertTriangle,
    iconBg: 'bg-red-500/20',
    iconColor: 'text-red-400',
    title: 'Incident',
    subtitle: 'Injury or Accident',
    description: 'Report a workplace injury or accident',
  },
  {
    id: 'near-miss',
    path: '/portal/report/near-miss',
    icon: AlertCircle,
    iconBg: 'bg-yellow-500/20',
    iconColor: 'text-yellow-400',
    title: 'Near Miss',
    subtitle: 'Close call',
    description: 'Report a close call where no injury occurred',
  },
  {
    id: 'complaint',
    path: '/portal/report/complaint',
    icon: MessageSquare,
    iconBg: 'bg-blue-500/20',
    iconColor: 'text-blue-400',
    title: 'Customer Complaint',
    subtitle: 'Customer concern',
    description: 'Log a complaint or concern from a customer',
  },
  {
    id: 'rta',
    path: '/portal/report/rta',
    icon: Car,
    iconBg: 'bg-orange-500/20',
    iconColor: 'text-orange-400',
    title: 'Road Traffic Accident',
    subtitle: 'Vehicle incident',
    description: 'Report an RTA involving a company vehicle',
  },
];

export default function PortalReport() {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900/20 to-slate-900">
      {/* Header with back button */}
      <header className="bg-black/20 backdrop-blur-xl border-b border-white/10">
        <div className="max-w-lg mx-auto px-4 py-4 flex items-center gap-4">
          <button
            onClick={() => navigate('/portal')}
            className="w-10 h-10 flex items-center justify-center rounded-xl bg-white/5 hover:bg-white/10 transition-colors"
          >
            <ArrowLeft className="w-5 h-5 text-white" />
          </button>
          <div className="flex items-center gap-3">
            <Shield className="w-6 h-6 text-purple-400" />
            <span className="font-semibold text-white">Submit Report</span>
          </div>
        </div>
      </header>

      <main className="max-w-lg mx-auto px-4 py-8">
        {/* Page Title */}
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-white mb-2">What are you reporting?</h1>
          <p className="text-gray-400">Select the type that best describes your report</p>
        </div>

        {/* Report Type Options */}
        <div className="space-y-3">
          {REPORT_TYPES.map((type) => (
            <button
              key={type.id}
              onClick={() => navigate(type.path)}
              className="w-full flex items-center gap-4 p-4 bg-white/5 hover:bg-white/10 border border-white/10 hover:border-white/20 rounded-2xl transition-all group text-left"
            >
              {/* Icon */}
              <div className={`w-14 h-14 ${type.iconBg} rounded-xl flex items-center justify-center flex-shrink-0`}>
                <type.icon className={`w-7 h-7 ${type.iconColor}`} />
              </div>

              {/* Content */}
              <div className="flex-1 min-w-0">
                <div className="flex items-baseline gap-2">
                  <h3 className="font-semibold text-white group-hover:text-purple-300 transition-colors">
                    {type.title}
                  </h3>
                  <span className="text-xs text-gray-500">{type.subtitle}</span>
                </div>
                <p className="text-sm text-gray-500 mt-0.5">{type.description}</p>
              </div>

              {/* Arrow */}
              <ChevronRight className="w-5 h-5 text-gray-500 group-hover:text-purple-400 group-hover:translate-x-1 transition-all flex-shrink-0" />
            </button>
          ))}
        </div>

        {/* Help text */}
        <p className="mt-8 text-center text-sm text-gray-600">
          Not sure which to choose? Pick the closest match —<br />
          you can provide more details in the form.
        </p>
      </main>
    </div>
  );
}
