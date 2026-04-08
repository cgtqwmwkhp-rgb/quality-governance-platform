import { useState } from 'react'
import { Award, ChevronDown, Loader2, CheckCircle2, AlertTriangle, Clock } from 'lucide-react'
import { planetMarkApi } from '../../api/client'

interface CertificationInfo {
  status: string
  certificate_number: string | null
  certification_date: string | null
  expiry_date: string | null
  certifying_body: string | null
  assessor_name: string | null
  readiness_percent: number
  data_quality_met: boolean
  actions_completed: number
  actions_total: number
}

interface CertificationStatusPanelProps {
  yearId: number
  certification: CertificationInfo
  onUpdated: () => void
}

const STATUS_LABELS: Record<string, { label: string; colour: string }> = {
  draft: { label: 'Draft', colour: 'bg-gray-100 text-gray-700' },
  submitted: { label: 'Submitted for Assessment', colour: 'bg-blue-100 text-blue-800' },
  certified: { label: 'Certified', colour: 'bg-green-100 text-green-800' },
  expired: { label: 'Expired', colour: 'bg-red-100 text-red-700' },
}

const TRANSITIONS: Record<string, { label: string; to: string }[]> = {
  draft: [{ label: 'Submit for Assessment', to: 'submitted' }],
  submitted: [
    { label: 'Mark as Certified', to: 'certified' },
    { label: 'Revert to Draft', to: 'draft' },
  ],
  certified: [{ label: 'Mark as Expired', to: 'expired' }],
  expired: [],
}

export function CertificationStatusPanel({
  yearId,
  certification,
  onUpdated,
}: CertificationStatusPanelProps) {
  const [isExpanded, setIsExpanded] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [form, setForm] = useState({
    certificate_number: certification.certificate_number || '',
    certification_date: certification.certification_date?.slice(0, 10) || '',
    expiry_date: certification.expiry_date?.slice(0, 10) || '',
    certifying_body: certification.certifying_body || 'Planet Mark',
    assessor_name: certification.assessor_name || '',
    assessment_notes: '',
  })

  const statusInfo = STATUS_LABELS[certification.status] ?? STATUS_LABELS.draft
  const available = TRANSITIONS[certification.status] ?? []

  const canProgress =
    certification.readiness_percent >= 80 &&
    certification.data_quality_met &&
    certification.actions_completed > 0

  const handleTransition = async (toStatus: string) => {
    setLoading(true)
    setError(null)
    try {
      await planetMarkApi.patchCertification(yearId, {
        status: toStatus,
        ...(toStatus === 'certified' ? form : {}),
      })
      onUpdated()
    } catch (err: unknown) {
      const msg =
        err instanceof Error
          ? err.message
          : 'Failed to update certification status'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="border rounded-lg bg-white overflow-hidden">
      <button
        className="w-full flex items-center justify-between px-5 py-4 hover:bg-gray-50 transition-colors"
        onClick={() => setIsExpanded(!isExpanded)}
        aria-expanded={isExpanded}
      >
        <div className="flex items-center gap-3">
          <Award className="w-5 h-5 text-green-600" />
          <div className="text-left">
            <p className="font-semibold text-gray-900 text-sm">Certification Status</p>
            <p className="text-xs text-gray-500 mt-0.5">
              {certification.certifying_body || 'Planet Mark'}
              {certification.certificate_number
                ? ` · Cert #${certification.certificate_number}`
                : ''}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className={`text-xs font-medium px-2.5 py-1 rounded-full ${statusInfo.colour}`}>
            {statusInfo.label}
          </span>
          <ChevronDown
            className={`w-4 h-4 text-gray-400 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
          />
        </div>
      </button>

      {isExpanded && (
        <div className="px-5 pb-5 border-t bg-gray-50">
          {/* Readiness indicators */}
          <div className="mt-4 grid grid-cols-3 gap-3">
            <ReadinessItem
              icon={<CheckCircle2 className="w-4 h-4" />}
              label="Evidence readiness"
              value={`${Math.round(certification.readiness_percent)}%`}
              met={certification.readiness_percent >= 80}
            />
            <ReadinessItem
              icon={<Award className="w-4 h-4" />}
              label="Data quality"
              value={certification.data_quality_met ? 'Met (≥12/16)' : 'Not yet met'}
              met={certification.data_quality_met}
            />
            <ReadinessItem
              icon={<Clock className="w-4 h-4" />}
              label="Actions completed"
              value={`${certification.actions_completed}/${certification.actions_total}`}
              met={certification.actions_completed > 0}
            />
          </div>

          {/* Certification form (shown when marking as certified) */}
          {certification.status === 'submitted' && (
            <div className="mt-4 space-y-3">
              <h4 className="text-xs font-semibold text-gray-700 uppercase tracking-wide">
                Certification Details
              </h4>
              <div className="grid grid-cols-2 gap-3">
                <FormField
                  label="Certificate Number"
                  value={form.certificate_number}
                  onChange={(v) => setForm({ ...form, certificate_number: v })}
                />
                <FormField
                  label="Certifying Body"
                  value={form.certifying_body}
                  onChange={(v) => setForm({ ...form, certifying_body: v })}
                />
                <FormField
                  label="Certification Date"
                  type="date"
                  value={form.certification_date}
                  onChange={(v) => setForm({ ...form, certification_date: v })}
                />
                <FormField
                  label="Expiry Date"
                  type="date"
                  value={form.expiry_date}
                  onChange={(v) => setForm({ ...form, expiry_date: v })}
                />
                <FormField
                  label="Assessor Name"
                  value={form.assessor_name}
                  onChange={(v) => setForm({ ...form, assessor_name: v })}
                  className="col-span-2"
                />
              </div>
            </div>
          )}

          {error && (
            <div className="mt-3 flex items-center gap-2 text-sm text-red-600 bg-red-50 p-3 rounded-md" role="alert">
              <AlertTriangle className="w-4 h-4 flex-shrink-0" />
              {error}
            </div>
          )}

          {/* Transition buttons */}
          {available.length > 0 && (
            <div className="mt-4 flex flex-wrap gap-2">
              {available.map(({ label, to }) => {
                const blockedForward = to === 'submitted' && !canProgress
                return (
                  <button
                    key={to}
                    onClick={() => !blockedForward && handleTransition(to)}
                    disabled={loading || blockedForward}
                    title={
                      blockedForward
                        ? 'Complete evidence uploads, data quality and actions first'
                        : undefined
                    }
                    className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors
                      ${to === 'certified'
                        ? 'bg-green-600 text-white hover:bg-green-700'
                        : to === 'draft'
                        ? 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                        : 'bg-blue-600 text-white hover:bg-blue-700'}
                      disabled:opacity-40 disabled:cursor-not-allowed`}
                  >
                    {loading ? (
                      <Loader2 className="w-4 h-4 animate-spin inline mr-1" />
                    ) : null}
                    {label}
                  </button>
                )
              })}
            </div>
          )}

          {available.length === 0 && (
            <p className="mt-3 text-xs text-gray-500 italic">
              No further status transitions available.
            </p>
          )}
        </div>
      )}
    </div>
  )
}

function ReadinessItem({
  icon,
  label,
  value,
  met,
}: {
  icon: React.ReactNode
  label: string
  value: string
  met: boolean
}) {
  return (
    <div className={`rounded-lg p-3 ${met ? 'bg-green-50' : 'bg-amber-50'}`}>
      <div className={`flex items-center gap-1.5 mb-1 ${met ? 'text-green-700' : 'text-amber-700'}`}>
        {icon}
        <span className="text-xs font-medium">{label}</span>
      </div>
      <p className={`text-sm font-semibold ${met ? 'text-green-900' : 'text-amber-900'}`}>{value}</p>
    </div>
  )
}

function FormField({
  label,
  value,
  onChange,
  type = 'text',
  className = '',
}: {
  label: string
  value: string
  onChange: (v: string) => void
  type?: string
  className?: string
}) {
  return (
    <div className={className}>
      <label className="block text-xs font-medium text-gray-600 mb-1">{label}</label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full text-sm border border-gray-300 rounded-md px-3 py-1.5 focus:ring-1 focus:ring-green-500 focus:border-green-500 outline-none"
      />
    </div>
  )
}
