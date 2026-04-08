import { CheckCircle2, Clock, AlertTriangle, BarChart3 } from 'lucide-react'

interface ActionsSummaryData {
  total: number
  completed: number
  in_progress: number
  overdue: number
  not_started: number
  completion_rate_percent: number
  avg_progress_percent: number
}

interface ActionSummaryKPIsProps {
  summary: ActionsSummaryData
}

export function ActionSummaryKPIs({ summary }: ActionSummaryKPIsProps) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
      <KPICard
        icon={<CheckCircle2 className="w-5 h-5 text-green-600" />}
        label="Completed"
        value={summary.completed}
        total={summary.total}
        colour="green"
      />
      <KPICard
        icon={<Clock className="w-5 h-5 text-blue-600" />}
        label="In Progress"
        value={summary.in_progress}
        total={summary.total}
        colour="blue"
      />
      <KPICard
        icon={<AlertTriangle className="w-5 h-5 text-red-500" />}
        label="Overdue"
        value={summary.overdue}
        total={summary.total}
        colour="red"
      />
      <KPICard
        icon={<BarChart3 className="w-5 h-5 text-purple-600" />}
        label="Completion Rate"
        value={`${Math.round(summary.completion_rate_percent)}%`}
        colour="purple"
        isPercent
      />
    </div>
  )
}

function KPICard({
  icon,
  label,
  value,
  total,
  colour,
  isPercent = false,
}: {
  icon: React.ReactNode
  label: string
  value: number | string
  total?: number
  colour: 'green' | 'blue' | 'red' | 'purple'
  isPercent?: boolean
}) {
  const bg = {
    green: 'bg-green-50',
    blue: 'bg-blue-50',
    red: value !== 0 ? 'bg-red-50' : 'bg-gray-50',
    purple: 'bg-purple-50',
  }[colour]

  return (
    <div className={`${bg} rounded-lg p-3 flex flex-col gap-1`}>
      <div className="flex items-center gap-1.5">
        {icon}
        <span className="text-xs font-medium text-gray-600">{label}</span>
      </div>
      <div className="flex items-baseline gap-1">
        <span className="text-2xl font-bold text-gray-900">{value}</span>
        {total !== undefined && !isPercent && (
          <span className="text-xs text-gray-400">/ {total}</span>
        )}
      </div>
    </div>
  )
}
