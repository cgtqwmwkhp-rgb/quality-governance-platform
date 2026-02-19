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
import { Card } from '../components/ui/Card';
import { cn } from '../helpers/utils';

// Report type options
const REPORT_TYPES = [
  {
    id: 'incident',
    path: '/portal/report/incident',
    icon: AlertTriangle,
    iconBg: 'bg-destructive/10',
    iconColor: 'text-destructive',
    title: 'Incident',
    subtitle: 'Injury or Accident',
    description: 'Report a workplace injury or accident',
  },
  {
    id: 'near-miss',
    path: '/portal/report/near-miss',
    icon: AlertCircle,
    iconBg: 'bg-warning/10',
    iconColor: 'text-warning',
    title: 'Near Miss',
    subtitle: 'Close call',
    description: 'Report a close call where no injury occurred',
  },
  {
    id: 'complaint',
    path: '/portal/report/complaint',
    icon: MessageSquare,
    iconBg: 'bg-info/10',
    iconColor: 'text-info',
    title: 'Customer Complaint',
    subtitle: 'Customer concern',
    description: 'Log a complaint or concern from a customer',
  },
  {
    id: 'rta',
    path: '/portal/report/rta',
    icon: Car,
    iconBg: 'bg-orange-100 dark:bg-orange-900/20',
    iconColor: 'text-orange-600 dark:text-orange-400',
    title: 'Road Traffic Collision',
    subtitle: 'Vehicle incident',
    description: 'Report an RTC involving a company vehicle',
  },
];

export default function PortalReport() {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-surface">
      {/* Header */}
      <header className="bg-card/95 backdrop-blur-lg border-b border-border sticky top-0 z-40">
        <div className="max-w-lg mx-auto px-4 sm:px-6 py-4 flex items-center gap-4">
          <button
            onClick={() => navigate('/portal')}
            className="w-10 h-10 flex items-center justify-center rounded-xl bg-surface hover:bg-muted transition-colors"
          >
            <ArrowLeft className="w-5 h-5 text-foreground" />
          </button>
          <div className="flex items-center gap-3">
            <Shield className="w-5 h-5 text-primary" />
            <span className="font-semibold text-foreground">Submit Report</span>
          </div>
        </div>
      </header>

      <main className="max-w-lg mx-auto px-4 sm:px-6 py-8">
        {/* Page Title */}
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-foreground mb-2">What are you reporting?</h1>
          <p className="text-muted-foreground">Select the type that best describes your report</p>
        </div>

        {/* Report Type Options */}
        <div className="space-y-3">
          {REPORT_TYPES.map((type) => (
            <Card
              key={type.id}
              hoverable
              className="p-4 cursor-pointer group"
              onClick={() => navigate(type.path)}
              data-testid={`report-${type.id}-card`}
            >
              <div className="flex items-center gap-4">
                {/* Icon */}
                <div className={cn('w-14 h-14 rounded-xl flex items-center justify-center flex-shrink-0', type.iconBg)}>
                  <type.icon className={cn('w-7 h-7', type.iconColor)} />
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-baseline gap-2">
                    <h3 className="font-semibold text-foreground group-hover:text-primary transition-colors">
                      {type.title}
                    </h3>
                    <span className="text-xs text-muted-foreground">{type.subtitle}</span>
                  </div>
                  <p className="text-sm text-muted-foreground mt-0.5">{type.description}</p>
                </div>

                {/* Arrow */}
                <ChevronRight className="w-5 h-5 text-muted-foreground group-hover:text-primary group-hover:translate-x-1 transition-all flex-shrink-0" />
              </div>
            </Card>
          ))}
        </div>

        {/* Help text */}
        <p className="mt-8 text-center text-sm text-muted-foreground">
          Not sure which to choose? Pick the closest match —<br />
          you can provide more details in the form.
        </p>
      </main>
    </div>
  );
}
