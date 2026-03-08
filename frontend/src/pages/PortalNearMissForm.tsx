import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { usePortalAuth } from '../contexts/PortalAuthContext'
import { API_BASE_URL } from '../config/apiBase'

// Portal report submission - uses public endpoint (no auth required)
interface PortalReportPayload {
  report_type: 'incident' | 'complaint' | 'rta' | 'near_miss'
  title: string
  description: string
  location?: string
  severity: string
  reporter_name?: string
  reporter_email?: string
  reporter_phone?: string
  department?: string
  is_anonymous: boolean
}

interface PortalReportResponse {
  success: boolean
  reference_number: string
  tracking_code: string
  message: string
  estimated_response: string
}

async function submitPortalReport(payload: PortalReportPayload): Promise<PortalReportResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/portal/reports/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(errorData.message || `Submission failed: ${response.status}`)
  }

  return response.json()
}
import {
  ArrowLeft,
  AlertTriangle,
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
  X,
  Shield,
  Wrench,
  Zap,
  Navigation,
  HardHat,
  Truck,
  CircleAlert,
  Construction,
} from 'lucide-react'
import FuzzySearchDropdown from '../components/FuzzySearchDropdown'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Textarea } from '../components/ui/Textarea'
import { cn } from '../helpers/utils'
import { useGeolocation } from '../hooks/useGeolocation'
import { useVoiceToText } from '../hooks/useVoiceToText'

// Contract options
const CONTRACT_OPTIONS = [
  { value: 'TfL-Central', label: 'TfL Central Line', sublabel: 'London Underground' },
  { value: 'TfL-Jubilee', label: 'TfL Jubilee Line', sublabel: 'London Underground' },
  { value: 'NR-Southern', label: 'Network Rail Southern', sublabel: 'Maintenance' },
  { value: 'NR-Western', label: 'Network Rail Western', sublabel: 'Maintenance' },
  { value: 'HS2-Midlands', label: 'HS2 Midlands', sublabel: 'Construction' },
  { value: 'Crossrail', label: 'Elizabeth Line', sublabel: 'Operations' },
  { value: 'other', label: 'Other', sublabel: 'Enter manually' },
]

// Role options
const ROLE_OPTIONS = [
  { value: 'driver', label: 'Driver', icon: Truck },
  { value: 'technician', label: 'Technician', icon: Wrench },
  { value: 'engineer', label: 'Engineer', icon: Construction },
  { value: 'supervisor', label: 'Supervisor', icon: HardHat },
  { value: 'office', label: 'Office Staff', icon: User },
  { value: 'visitor', label: 'Visitor', icon: User },
]

// Risk categories
const RISK_CATEGORIES = [
  { value: 'slip-trip-fall', label: 'Slip/Trip/Fall', icon: CircleAlert, color: 'orange' },
  { value: 'equipment', label: 'Equipment', icon: Wrench, color: 'blue' },
  { value: 'electrical', label: 'Electrical', icon: Zap, color: 'yellow' },
  { value: 'manual-handling', label: 'Manual Handling', icon: HardHat, color: 'purple' },
  { value: 'vehicle', label: 'Vehicle/Traffic', icon: Truck, color: 'red' },
  { value: 'environmental', label: 'Environmental', icon: Shield, color: 'green' },
]

// Severity levels
const SEVERITY_LEVELS = [
  { value: 'low', label: 'Low', description: 'Minor inconvenience', color: 'bg-success' },
  { value: 'medium', label: 'Medium', description: 'Could cause injury', color: 'bg-warning' },
  { value: 'high', label: 'High', description: 'Serious injury risk', color: 'bg-orange-500' },
  {
    value: 'critical',
    label: 'Critical',
    description: 'Life-threatening',
    color: 'bg-destructive',
  },
]

interface FormData {
  reporterName: string
  reporterEmail: string
  reporterPhone: string
  reporterRole: string
  wasInvolved: boolean | null
  contract: string
  contractOther: string
  location: string
  locationCoordinates: string
  eventDate: string
  eventTime: string
  description: string
  potentialConsequences: string
  preventiveActionSuggested: string
  personsInvolved: string
  witnessesPresent: boolean | null
  witnessNames: string
  assetNumber: string
  assetType: string
  riskCategory: string
  potentialSeverity: string
  photos: File[]
}

type Step = 1 | 2 | 3 | 4

export default function PortalNearMissForm() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { user } = usePortalAuth()
  const [step, setStep] = useState<Step>(1)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [submittedRef, setSubmittedRef] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const {
    latitude,
    longitude,
    isLoading: geoLoading,
    error: geoError,
    getLocation,
  } = useGeolocation()
  const {
    isListening,
    transcript,
    isSupported: voiceSupported,
    startListening,
    stopListening,
  } = useVoiceToText()

  const [formData, setFormData] = useState<FormData>({
    reporterName: '',
    reporterEmail: '',
    reporterPhone: '',
    reporterRole: '',
    wasInvolved: null,
    contract: '',
    contractOther: '',
    location: '',
    locationCoordinates: '',
    eventDate: new Date().toISOString().split('T')[0],
    eventTime: new Date().toTimeString().slice(0, 5),
    description: '',
    potentialConsequences: '',
    preventiveActionSuggested: '',
    personsInvolved: '',
    witnessesPresent: null,
    witnessNames: '',
    assetNumber: '',
    assetType: '',
    riskCategory: '',
    potentialSeverity: '',
    photos: [],
  })

  const totalSteps = 4

  // Pre-fill user details from SSO
  useEffect(() => {
    if (user) {
      setFormData((prev) => ({
        ...prev,
        reporterName: user.name || '',
        reporterEmail: user.email || '',
      }))
    }
  }, [user])

  // Update location from GPS
  useEffect(() => {
    if (latitude !== null && longitude !== null) {
      setFormData((prev) => ({
        ...prev,
        locationCoordinates: `${latitude.toFixed(6)}, ${longitude.toFixed(6)}`,
        location: prev.location || `GPS: ${latitude.toFixed(6)}, ${longitude.toFixed(6)}`,
      }))
    }
  }, [latitude, longitude])

  // Track previous transcript to avoid duplicates
  const [lastTranscript, setLastTranscript] = useState('')

  // Append voice transcript to description
  useEffect(() => {
    if (transcript && transcript !== lastTranscript) {
      setFormData((prev) => ({
        ...prev,
        description: prev.description + (prev.description ? ' ' : '') + transcript,
      }))
      setLastTranscript(transcript)
    }
  }, [transcript, lastTranscript])

  // GPS detection
  const detectLocation = () => {
    getLocation()
  }

  // Voice recording toggle
  const toggleVoiceRecording = () => {
    if (isListening) {
      stopListening()
    } else {
      startListening()
    }
  }

  // Photo handling
  const handlePhotoCapture = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      setFormData((prev) => ({ ...prev, photos: [...prev.photos, ...Array.from(e.target.files!)] }))
    }
  }

  const removePhoto = (index: number) => {
    setFormData((prev) => ({ ...prev, photos: prev.photos.filter((_, i) => i !== index) }))
  }

  // Submit - uses public portal endpoint (no auth required)
  const handleSubmit = async () => {
    setIsSubmitting(true)
    setError(null)

    try {
      // Build portal report payload - Near miss goes to Near Miss/Incidents dashboard
      const payload: PortalReportPayload = {
        report_type: 'near_miss', // Routes to Near Miss records, not general Incidents
        title: `Near Miss - ${formData.contract === 'other' ? formData.contractOther : formData.contract} - ${formData.location}`,
        description: `${formData.description}${formData.potentialConsequences ? `\n\nPotential consequences: ${formData.potentialConsequences}` : ''}${formData.preventiveActionSuggested ? `\n\nPreventive action suggested: ${formData.preventiveActionSuggested}` : ''}`,
        location: formData.location,
        severity:
          formData.potentialSeverity === 'severe'
            ? 'high'
            : formData.potentialSeverity === 'moderate'
              ? 'medium'
              : 'low',
        reporter_name: formData.reporterName,
        // CRITICAL: reporter_email MUST match authenticated user's email for My Reports linkage
        reporter_email: user?.email || formData.reporterEmail || undefined,
        reporter_phone: formData.reporterPhone || undefined,
        department: formData.contract === 'other' ? formData.contractOther : formData.contract,
        is_anonymous: false,
      }

      const response = await submitPortalReport(payload)
      setSubmittedRef(response.reference_number)
      // Store tracking code for anonymous access if needed
      if (response.tracking_code) {
        sessionStorage.setItem(`tracking_${response.reference_number}`, response.tracking_code)
      }
    } catch (error) {
      console.error('Submission error:', error)
      // Show real error - do NOT generate fake reference numbers
      setError(
        error instanceof Error ? error.message : 'Failed to submit report. Please try again.',
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  // Validation
  const canProceed = (): boolean => {
    switch (step) {
      case 1:
        return !!formData.reporterName && !!formData.contract && !!formData.reporterRole
      case 2:
        return !!formData.location && !!formData.description
      case 3:
        return !!formData.riskCategory && !!formData.potentialSeverity
      case 4:
        return true
      default:
        return false
    }
  }

  // Success screen
  if (submittedRef) {
    return (
      <div className="min-h-screen bg-surface flex items-center justify-center p-4">
        <Card className="p-8 max-w-md w-full text-center">
          <div className="w-20 h-20 bg-success/10 rounded-full flex items-center justify-center mx-auto mb-6">
            <Check className="w-10 h-10 text-success" />
          </div>
          <h1 className="text-2xl font-bold text-foreground mb-2">Near Miss Reported</h1>
          <p className="text-muted-foreground mb-6">Your reference number is:</p>
          <div className="bg-surface border border-border rounded-xl px-6 py-4 mb-6">
            <span className="text-2xl font-mono font-bold text-primary">{submittedRef}</span>
          </div>
          <p className="text-sm text-muted-foreground mb-6">{t('portal.thank_you_near_miss')}</p>
          <div className="flex gap-3">
            <Button
              onClick={() => navigate('/portal/track/' + submittedRef)}
              className="flex-1 bg-primary hover:bg-primary/90"
            >
              Track Status
            </Button>
            <Button variant="outline" onClick={() => navigate('/portal')} className="flex-1">
              Done
            </Button>
          </div>
        </Card>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-surface">
      {/* Header */}
      <header className="bg-card/95 backdrop-blur-lg border-b border-border sticky top-0 z-40">
        <div className="max-w-lg mx-auto px-4 sm:px-6 py-4 flex items-center gap-4">
          <button
            onClick={() =>
              step === 1 ? navigate('/portal/report') : setStep((s) => (s - 1) as Step)
            }
            className="w-10 h-10 flex items-center justify-center rounded-xl bg-surface hover:bg-muted transition-colors"
          >
            <ArrowLeft className="w-5 h-5 text-foreground" />
          </button>
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-warning" />
              <span className="font-semibold text-foreground">{t('portal.near_miss_report')}</span>
            </div>
            <div className="text-xs text-muted-foreground">
              {t('portal.step_of', { step, total: totalSteps })}
            </div>
          </div>
        </div>

        <div className="h-1 bg-border">
          <div
            className="h-full bg-gradient-to-r from-warning to-primary transition-all duration-300"
            style={{ width: `${(step / totalSteps) * 100}%` }}
          />
        </div>
      </header>

      <main className="max-w-lg mx-auto px-4 sm:px-6 py-6 pb-28">
        {/* Step 1: Your Details */}
        {step === 1 && (
          <div className="space-y-5">
            <div>
              <h1 className="text-xl font-bold text-foreground mb-1">{t('portal.your_details')}</h1>
              <p className="text-muted-foreground text-sm">{t('portal.who_reporting')}</p>
            </div>

            <div>
              <label
                htmlFor="portalnearmissform-field-0"
                className="block text-sm font-medium text-foreground mb-2"
              >
                {t('portal.your_name_label')} *
              </label>
              <div className="relative">
                <User className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                <Input
                  id="portalnearmissform-field-0"
                  value={formData.reporterName}
                  onChange={(e) =>
                    setFormData((prev) => ({ ...prev, reporterName: e.target.value }))
                  }
                  placeholder={t('portal.full_name_placeholder')}
                  className="pl-10"
                />
              </div>
            </div>

            <div>
              <span className="block text-sm font-medium text-foreground mb-2">
                {t('portal.your_role')} *
              </span>
              <div className="grid grid-cols-3 gap-2">
                {ROLE_OPTIONS.map((role) => (
                  <button
                    key={role.value}
                    type="button"
                    onClick={() => setFormData((prev) => ({ ...prev, reporterRole: role.value }))}
                    className={cn(
                      'flex flex-col items-center gap-1 p-3 rounded-xl border-2 transition-all',
                      formData.reporterRole === role.value
                        ? 'bg-primary/10 border-primary'
                        : 'bg-card border-border hover:border-border-strong',
                    )}
                  >
                    <role.icon
                      className={cn(
                        'w-5 h-5',
                        formData.reporterRole === role.value
                          ? 'text-primary'
                          : 'text-muted-foreground',
                      )}
                    />
                    <span className="text-xs text-foreground">{role.label}</span>
                  </button>
                ))}
              </div>
            </div>

            <FuzzySearchDropdown
              label={`${t('portal.contract_site')} *`}
              options={CONTRACT_OPTIONS}
              value={formData.contract}
              onChange={(val) => setFormData((prev) => ({ ...prev, contract: val }))}
              placeholder={t('portal.search_contract_nm')}
              required
            />

            {formData.contract === 'other' && (
              <Input
                value={formData.contractOther}
                onChange={(e) =>
                  setFormData((prev) => ({ ...prev, contractOther: e.target.value }))
                }
                placeholder={t('portal.enter_contract')}
              />
            )}

            <div>
              <span className="block text-sm font-medium text-foreground mb-2">
                {t('portal.were_you_involved_nm')}
              </span>
              <div className="grid grid-cols-2 gap-3">
                {[true, false].map((val) => (
                  <button
                    key={String(val)}
                    type="button"
                    onClick={() => setFormData((prev) => ({ ...prev, wasInvolved: val }))}
                    className={cn(
                      'px-4 py-3 rounded-xl border-2 font-medium transition-all',
                      formData.wasInvolved === val
                        ? 'bg-primary/10 border-primary text-primary'
                        : 'bg-card border-border text-foreground hover:border-border-strong',
                    )}
                  >
                    {val ? t('portal.yes_involved') : t('portal.no_witnessed')}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Step 2: What Happened */}
        {step === 2 && (
          <div className="space-y-5">
            <div>
              <h1 className="text-xl font-bold text-foreground mb-1">
                {t('portal.what_happened')}
              </h1>
              <p className="text-muted-foreground text-sm">{t('portal.describe_near_miss')}</p>
            </div>

            <div>
              <label
                htmlFor="portalnearmissform-field-1"
                className="block text-sm font-medium text-foreground mb-2"
              >
                {t('portal.location_label')} *
              </label>
              <div className="relative">
                <MapPin className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                <Input
                  id="portalnearmissform-field-1"
                  value={formData.location}
                  onChange={(e) => setFormData((prev) => ({ ...prev, location: e.target.value }))}
                  placeholder={t('portal.where_did_happen')}
                  className="pl-10 pr-16"
                />
                <button
                  type="button"
                  onClick={detectLocation}
                  disabled={geoLoading}
                  className="absolute right-2 top-1/2 -translate-y-1/2 p-2 bg-primary/10 text-primary rounded-lg"
                >
                  {geoLoading ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Navigation className="w-4 h-4" />
                  )}
                </button>
              </div>
              {geoError && <p className="text-destructive text-xs mt-1">{geoError}</p>}
              {formData.locationCoordinates && (
                <p className="text-muted-foreground text-xs mt-1">
                  GPS: {formData.locationCoordinates}
                </p>
              )}
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label
                  htmlFor="portalnearmissform-field-2"
                  className="block text-sm font-medium text-foreground mb-2"
                >
                  {t('portal.date_label')}
                </label>
                <div className="relative">
                  <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                  <Input
                    id="portalnearmissform-field-2"
                    type="date"
                    value={formData.eventDate}
                    onChange={(e) =>
                      setFormData((prev) => ({ ...prev, eventDate: e.target.value }))
                    }
                    className="pl-10"
                  />
                </div>
              </div>
              <div>
                <label
                  htmlFor="portalnearmissform-field-3"
                  className="block text-sm font-medium text-foreground mb-2"
                >
                  {t('portal.time_label')}
                </label>
                <div className="relative">
                  <Clock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                  <Input
                    id="portalnearmissform-field-3"
                    type="time"
                    value={formData.eventTime}
                    onChange={(e) =>
                      setFormData((prev) => ({ ...prev, eventTime: e.target.value }))
                    }
                    className="pl-10"
                  />
                </div>
              </div>
            </div>

            <div>
              <label
                htmlFor="portalnearmissform-field-4"
                className="block text-sm font-medium text-foreground mb-2"
              >
                {t('portal.description_label')} *
              </label>
              <div className="relative">
                <Textarea
                  id="portalnearmissform-field-4"
                  value={formData.description}
                  onChange={(e) =>
                    setFormData((prev) => ({ ...prev, description: e.target.value }))
                  }
                  placeholder={t('portal.near_miss_placeholder')}
                  rows={5}
                />
                {voiceSupported && (
                  <button
                    type="button"
                    onClick={toggleVoiceRecording}
                    className={cn(
                      'absolute right-3 bottom-3 p-2 rounded-full transition-colors',
                      isListening
                        ? 'bg-destructive text-destructive-foreground animate-pulse'
                        : 'bg-primary/10 text-primary hover:bg-primary/20',
                    )}
                  >
                    {isListening ? <MicOff className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
                  </button>
                )}
              </div>
              {isListening && (
                <p className="text-primary text-xs mt-1 animate-pulse">
                  {t('portal.listening_speak')}
                </p>
              )}
            </div>

            <div>
              <label
                htmlFor="portalnearmissform-field-5"
                className="block text-sm font-medium text-foreground mb-2"
              >
                {t('portal.what_could_happened')}
              </label>
              <Textarea
                id="portalnearmissform-field-5"
                value={formData.potentialConsequences}
                onChange={(e) =>
                  setFormData((prev) => ({ ...prev, potentialConsequences: e.target.value }))
                }
                placeholder={t('portal.potential_consequences_placeholder')}
                rows={3}
              />
            </div>
          </div>
        )}

        {/* Step 3: Risk Assessment */}
        {step === 3 && (
          <div className="space-y-5">
            <div>
              <h1 className="text-xl font-bold text-foreground mb-1">
                {t('portal.risk_assessment')}
              </h1>
              <p className="text-muted-foreground text-sm">{t('portal.categorize_near_miss')}</p>
            </div>

            <div>
              <span className="block text-sm font-medium text-foreground mb-2">
                {t('portal.risk_category')} *
              </span>
              <div className="grid grid-cols-3 gap-2">
                {RISK_CATEGORIES.map((cat) => (
                  <button
                    key={cat.value}
                    type="button"
                    onClick={() => setFormData((prev) => ({ ...prev, riskCategory: cat.value }))}
                    className={cn(
                      'flex flex-col items-center gap-1 p-3 rounded-xl border-2 transition-all',
                      formData.riskCategory === cat.value
                        ? 'bg-primary/10 border-primary'
                        : 'bg-card border-border hover:border-border-strong',
                    )}
                  >
                    <cat.icon
                      className={cn(
                        'w-5 h-5',
                        formData.riskCategory === cat.value
                          ? 'text-primary'
                          : 'text-muted-foreground',
                      )}
                    />
                    <span className="text-xs text-foreground text-center">{cat.label}</span>
                  </button>
                ))}
              </div>
            </div>

            <div>
              <span className="block text-sm font-medium text-foreground mb-2">
                {t('portal.potential_severity')} *
              </span>
              <div className="space-y-2">
                {SEVERITY_LEVELS.map((level) => (
                  <button
                    key={level.value}
                    type="button"
                    onClick={() =>
                      setFormData((prev) => ({ ...prev, potentialSeverity: level.value }))
                    }
                    className={cn(
                      'w-full flex items-center gap-3 p-3 rounded-xl border-2 transition-all text-left',
                      formData.potentialSeverity === level.value
                        ? 'bg-primary/10 border-primary'
                        : 'bg-card border-border hover:border-border-strong',
                    )}
                  >
                    <div className={cn('w-4 h-4 rounded-full', level.color)} />
                    <div className="flex-1">
                      <div className="font-medium text-foreground">{level.label}</div>
                      <div className="text-xs text-muted-foreground">{level.description}</div>
                    </div>
                  </button>
                ))}
              </div>
            </div>

            <div>
              <span className="block text-sm font-medium text-foreground mb-2">
                {t('portal.any_witnesses')}
              </span>
              <div className="grid grid-cols-2 gap-3">
                {[true, false].map((val) => (
                  <button
                    key={String(val)}
                    type="button"
                    onClick={() => setFormData((prev) => ({ ...prev, witnessesPresent: val }))}
                    className={cn(
                      'px-4 py-3 rounded-xl border-2 font-medium transition-all',
                      formData.witnessesPresent === val
                        ? 'bg-primary/10 border-primary text-primary'
                        : 'bg-card border-border text-foreground hover:border-border-strong',
                    )}
                  >
                    {val ? 'Yes' : 'No'}
                  </button>
                ))}
              </div>
            </div>

            {formData.witnessesPresent && (
              <Input
                value={formData.witnessNames}
                onChange={(e) => setFormData((prev) => ({ ...prev, witnessNames: e.target.value }))}
                placeholder={t('portal.witness_contact_placeholder')}
              />
            )}
          </div>
        )}

        {/* Step 4: Prevention & Evidence */}
        {step === 4 && (
          <div className="space-y-5">
            <div>
              <h1 className="text-xl font-bold text-foreground mb-1">
                {t('portal.prevention_evidence')}
              </h1>
              <p className="text-muted-foreground text-sm">{t('portal.suggest_actions')}</p>
            </div>

            <div>
              <label
                htmlFor="portalnearmissform-field-6"
                className="block text-sm font-medium text-foreground mb-2"
              >
                {t('portal.suggested_preventive')}
              </label>
              <Textarea
                id="portalnearmissform-field-6"
                value={formData.preventiveActionSuggested}
                onChange={(e) =>
                  setFormData((prev) => ({ ...prev, preventiveActionSuggested: e.target.value }))
                }
                placeholder={t('portal.preventive_placeholder')}
                rows={4}
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label
                  htmlFor="portalnearmissform-field-7"
                  className="block text-sm font-medium text-foreground mb-2"
                >
                  {t('portal.asset_number')}
                </label>
                <Input
                  id="portalnearmissform-field-7"
                  value={formData.assetNumber}
                  onChange={(e) =>
                    setFormData((prev) => ({ ...prev, assetNumber: e.target.value }))
                  }
                  placeholder={t('portal.if_applicable')}
                />
              </div>
              <div>
                <label
                  htmlFor="portalnearmissform-field-8"
                  className="block text-sm font-medium text-foreground mb-2"
                >
                  {t('portal.asset_type')}
                </label>
                <Input
                  id="portalnearmissform-field-8"
                  value={formData.assetType}
                  onChange={(e) => setFormData((prev) => ({ ...prev, assetType: e.target.value }))}
                  placeholder={t('portal.asset_type_placeholder')}
                />
              </div>
            </div>

            <div>
              <label
                htmlFor="portalnearmissform-field-9"
                className="block text-sm font-medium text-foreground mb-2"
              >
                {t('portal.others_involved')}
              </label>
              <Input
                id="portalnearmissform-field-9"
                value={formData.personsInvolved}
                onChange={(e) =>
                  setFormData((prev) => ({ ...prev, personsInvolved: e.target.value }))
                }
                placeholder={t('portal.others_placeholder')}
              />
            </div>

            {/* Photos */}
            <div>
              <span className="block text-sm font-medium text-foreground mb-2">
                {t('portal.photos_optional')}
              </span>
              <div className="grid grid-cols-4 gap-2">
                {formData.photos.map((photo, index) => (
                  <div key={index} className="relative aspect-square">
                    <img
                      src={URL.createObjectURL(photo)}
                      alt=""
                      className="w-full h-full object-cover rounded-xl"
                    />
                    <button
                      type="button"
                      onClick={() => removePhoto(index)}
                      className="absolute -top-1 -right-1 w-5 h-5 bg-destructive text-destructive-foreground rounded-full flex items-center justify-center"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </div>
                ))}
                <span className="aspect-square flex flex-col items-center justify-center bg-surface border-2 border-dashed border-border rounded-xl cursor-pointer hover:border-primary/30 transition-colors">
                  <Camera className="w-6 h-6 text-muted-foreground" />
                  <span className="text-xs text-muted-foreground mt-1">Add</span>
                  <input
                    type="file"
                    accept="image/*"
                    capture="environment"
                    onChange={handlePhotoCapture}
                    className="hidden"
                    multiple
                  />
                </span>
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
              <CircleAlert className="w-5 h-5 text-destructive flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-medium text-destructive">
                  {t('portal.submission_failed')}
                </p>
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
            <Button variant="outline" onClick={() => setStep((s) => (s - 1) as Step)}>
              <ChevronLeft className="w-5 h-5" />
              {t('back')}
            </Button>
          )}

          {step < totalSteps ? (
            <Button
              onClick={() => setStep((s) => (s + 1) as Step)}
              disabled={!canProceed()}
              className="flex-1 bg-primary hover:bg-primary/90"
            >
              {t('portal.continue_btn')}
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
                  {t('portal.submitting')}
                </>
              ) : (
                <>
                  <Check className="w-5 h-5" />
                  {t('portal.submit_near_miss')}
                </>
              )}
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}
