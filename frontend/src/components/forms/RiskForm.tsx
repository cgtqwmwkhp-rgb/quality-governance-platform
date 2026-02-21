const CATEGORIES = [
  { id: 'strategic', label: 'Strategic' },
  { id: 'operational', label: 'Operational' },
  { id: 'financial', label: 'Financial' },
  { id: 'compliance', label: 'Compliance' },
  { id: 'reputational', label: 'Reputational' },
  { id: 'health_safety', label: 'Health & Safety' },
  { id: 'environmental', label: 'Environmental' },
  { id: 'technological', label: 'Technological' },
  { id: 'legal', label: 'Legal' },
  { id: 'project', label: 'Project' },
]

const TREATMENT_STRATEGIES = [
  { id: 'treat', label: 'Treat' },
  { id: 'tolerate', label: 'Tolerate' },
  { id: 'transfer', label: 'Transfer' },
  { id: 'terminate', label: 'Terminate' },
]

export interface RiskFormData {
  title: string
  description: string
  category: string
  department: string
  inherent_likelihood: number
  inherent_impact: number
  residual_likelihood: number
  residual_impact: number
  treatment_strategy: string
  treatment_plan: string
  risk_owner_name: string
  review_frequency_days: number
}

export const EMPTY_RISK_FORM: RiskFormData = {
  title: '',
  description: '',
  category: 'operational',
  department: '',
  inherent_likelihood: 3,
  inherent_impact: 3,
  residual_likelihood: 2,
  residual_impact: 2,
  treatment_strategy: 'treat',
  treatment_plan: '',
  risk_owner_name: '',
  review_frequency_days: 90,
}

function scoreToLevel(score: number) {
  if (score > 16) return 'critical'
  if (score > 9) return 'high'
  if (score > 4) return 'medium'
  return 'low'
}

function levelToColor(level: string) {
  const map: Record<string, string> = {
    critical: 'hsl(var(--destructive))',
    high: 'hsl(var(--warning))',
    medium: 'hsl(var(--info))',
    low: 'hsl(var(--success))',
  }
  return map[level] || map['low']
}

interface RiskFormFieldsProps {
  form: RiskFormData
  onChange: (form: RiskFormData) => void
}

export default function RiskFormFields({ form, onChange }: RiskFormFieldsProps) {
  return (
    <div className="space-y-4 max-h-[70vh] overflow-y-auto pr-2">
      <div>
        <label className="block text-sm font-medium text-foreground mb-1">Title *</label>
        <input
          className="w-full border border-border rounded-lg px-3 py-2 bg-card text-foreground focus:ring-2 focus:ring-primary focus:border-primary"
          value={form.title}
          onChange={e => onChange({ ...form, title: e.target.value })}
          placeholder="Risk title (min 5 chars)"
        />
      </div>
      <div>
        <label className="block text-sm font-medium text-foreground mb-1">Description *</label>
        <textarea
          rows={3}
          className="w-full border border-border rounded-lg px-3 py-2 bg-card text-foreground focus:ring-2 focus:ring-primary focus:border-primary resize-none"
          value={form.description}
          onChange={e => onChange({ ...form, description: e.target.value })}
          placeholder="Detailed risk description (min 10 chars)"
        />
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-foreground mb-1">Category</label>
          <select
            className="w-full border border-border rounded-lg px-3 py-2 bg-card text-foreground"
            value={form.category}
            onChange={e => onChange({ ...form, category: e.target.value })}
          >
            {CATEGORIES.map(c => (
              <option key={c.id} value={c.id}>{c.label}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-foreground mb-1">Department</label>
          <input
            className="w-full border border-border rounded-lg px-3 py-2 bg-card text-foreground"
            value={form.department}
            onChange={e => onChange({ ...form, department: e.target.value })}
            placeholder="e.g. Operations"
          />
        </div>
      </div>
      <div>
        <label className="block text-sm font-medium text-foreground mb-1">Risk Owner</label>
        <input
          className="w-full border border-border rounded-lg px-3 py-2 bg-card text-foreground"
          value={form.risk_owner_name}
          onChange={e => onChange({ ...form, risk_owner_name: e.target.value })}
          placeholder="Person responsible"
        />
      </div>
      <div className="border-t border-border pt-4">
        <h4 className="text-sm font-semibold text-foreground mb-3">Inherent Risk (before controls)</h4>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-xs text-muted-foreground mb-1">Likelihood (1-5)</label>
            <input
              type="range" min={1} max={5} step={1}
              className="w-full accent-primary"
              value={form.inherent_likelihood}
              onChange={e => onChange({ ...form, inherent_likelihood: Number(e.target.value) })}
            />
            <div className="flex justify-between text-xs text-muted-foreground">
              <span>Rare</span><span className="font-bold text-foreground">{form.inherent_likelihood}</span><span>Certain</span>
            </div>
          </div>
          <div>
            <label className="block text-xs text-muted-foreground mb-1">Impact (1-5)</label>
            <input
              type="range" min={1} max={5} step={1}
              className="w-full accent-primary"
              value={form.inherent_impact}
              onChange={e => onChange({ ...form, inherent_impact: Number(e.target.value) })}
            />
            <div className="flex justify-between text-xs text-muted-foreground">
              <span>Minor</span><span className="font-bold text-foreground">{form.inherent_impact}</span><span>Critical</span>
            </div>
          </div>
        </div>
        <div className="mt-2 text-center">
          <span className="text-sm text-muted-foreground">Inherent Score: </span>
          <span className="font-bold text-lg" style={{ color: levelToColor(scoreToLevel(form.inherent_likelihood * form.inherent_impact)) }}>
            {form.inherent_likelihood * form.inherent_impact}
          </span>
        </div>
      </div>
      <div className="border-t border-border pt-4">
        <h4 className="text-sm font-semibold text-foreground mb-3">Residual Risk (after controls)</h4>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-xs text-muted-foreground mb-1">Likelihood (1-5)</label>
            <input
              type="range" min={1} max={5} step={1}
              className="w-full accent-primary"
              value={form.residual_likelihood}
              onChange={e => onChange({ ...form, residual_likelihood: Number(e.target.value) })}
            />
            <div className="flex justify-between text-xs text-muted-foreground">
              <span>Rare</span><span className="font-bold text-foreground">{form.residual_likelihood}</span><span>Certain</span>
            </div>
          </div>
          <div>
            <label className="block text-xs text-muted-foreground mb-1">Impact (1-5)</label>
            <input
              type="range" min={1} max={5} step={1}
              className="w-full accent-primary"
              value={form.residual_impact}
              onChange={e => onChange({ ...form, residual_impact: Number(e.target.value) })}
            />
            <div className="flex justify-between text-xs text-muted-foreground">
              <span>Minor</span><span className="font-bold text-foreground">{form.residual_impact}</span><span>Critical</span>
            </div>
          </div>
        </div>
        <div className="mt-2 text-center">
          <span className="text-sm text-muted-foreground">Residual Score: </span>
          <span className="font-bold text-lg" style={{ color: levelToColor(scoreToLevel(form.residual_likelihood * form.residual_impact)) }}>
            {form.residual_likelihood * form.residual_impact}
          </span>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-4 border-t border-border pt-4">
        <div>
          <label className="block text-sm font-medium text-foreground mb-1">Treatment Strategy</label>
          <select
            className="w-full border border-border rounded-lg px-3 py-2 bg-card text-foreground"
            value={form.treatment_strategy}
            onChange={e => onChange({ ...form, treatment_strategy: e.target.value })}
          >
            {TREATMENT_STRATEGIES.map(s => (
              <option key={s.id} value={s.id}>{s.label}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-foreground mb-1">Review Frequency (days)</label>
          <input
            type="number" min={7} max={365}
            className="w-full border border-border rounded-lg px-3 py-2 bg-card text-foreground"
            value={form.review_frequency_days}
            onChange={e => onChange({ ...form, review_frequency_days: Number(e.target.value) })}
          />
        </div>
      </div>
      <div>
        <label className="block text-sm font-medium text-foreground mb-1">Treatment Plan</label>
        <textarea
          rows={2}
          className="w-full border border-border rounded-lg px-3 py-2 bg-card text-foreground resize-none"
          value={form.treatment_plan}
          onChange={e => onChange({ ...form, treatment_plan: e.target.value })}
          placeholder="Actions to treat this risk"
        />
      </div>
    </div>
  )
}

export { CATEGORIES, TREATMENT_STRATEGIES, scoreToLevel, levelToColor }
