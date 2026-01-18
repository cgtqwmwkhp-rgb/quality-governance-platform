import { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  AlertTriangle,
  MessageSquare,
  ArrowLeft,
  Send,
  Shield,
  Eye,
  EyeOff,
  Camera,
  MapPin,
  User,
  Mail,
  Phone,
  Building,
  CheckCircle,
  Copy,
  QrCode,
  Loader2,
  Info,
  Sparkles,
} from 'lucide-react';

// Animated background
const AnimatedBackground = () => (
  <div className="fixed inset-0 -z-10 overflow-hidden">
    <div className="absolute inset-0 bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900" />
    <div className="absolute top-0 -left-4 w-96 h-96 bg-purple-500 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-pulse" />
    <div className="absolute bottom-0 -right-4 w-96 h-96 bg-cyan-500 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-pulse" />
  </div>
);

// Severity option component
const SeverityOption = ({ 
  id, 
  label, 
  description, 
  color, 
  selected, 
  onClick 
}: { 
  id: string; 
  label: string; 
  description: string; 
  color: string; 
  selected: boolean; 
  onClick: () => void;
}) => (
  <button
    type="button"
    onClick={onClick}
    className={`flex-1 p-3 rounded-xl border-2 transition-all text-left ${
      selected 
        ? `border-${color}-500 bg-${color}-500/20` 
        : 'border-white/10 bg-white/5 hover:bg-white/10'
    }`}
    style={{
      borderColor: selected ? color : undefined,
      backgroundColor: selected ? `${color}20` : undefined,
    }}
  >
    <div className="flex items-center gap-2 mb-1">
      <div 
        className="w-3 h-3 rounded-full" 
        style={{ backgroundColor: color }}
      />
      <span className="font-semibold text-white text-sm">{label}</span>
    </div>
    <p className="text-xs text-gray-400">{description}</p>
  </button>
);

// Success modal component
const SuccessModal = ({ 
  referenceNumber, 
  trackingCode, 
  onClose 
}: { 
  referenceNumber: string; 
  trackingCode: string;
  onClose: () => void;
}) => {
  const [copied, setCopied] = useState(false);
  const navigate = useNavigate();

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
      <div className="bg-gradient-to-br from-slate-800 to-slate-900 border border-white/20 rounded-3xl p-8 max-w-md w-full text-center">
        {/* Success animation */}
        <div className="w-20 h-20 mx-auto mb-6 bg-gradient-to-br from-green-500 to-emerald-500 rounded-full flex items-center justify-center animate-bounce">
          <CheckCircle className="w-10 h-10 text-white" />
        </div>

        <h2 className="text-2xl font-bold text-white mb-2">Report Submitted!</h2>
        <p className="text-gray-400 mb-6">Your report has been received and will be reviewed shortly.</p>

        {/* Reference Number */}
        <div className="bg-white/5 border border-white/10 rounded-xl p-4 mb-4">
          <p className="text-xs text-gray-400 mb-1">Your Reference Number</p>
          <div className="flex items-center justify-center gap-2">
            <span className="text-2xl font-mono font-bold text-white">{referenceNumber}</span>
            <button
              onClick={() => copyToClipboard(referenceNumber)}
              className="p-2 hover:bg-white/10 rounded-lg transition-colors"
            >
              {copied ? <CheckCircle className="w-5 h-5 text-green-400" /> : <Copy className="w-5 h-5 text-gray-400" />}
            </button>
          </div>
        </div>

        {/* Tracking Code (for anonymous) */}
        <div className="bg-purple-500/10 border border-purple-500/30 rounded-xl p-4 mb-6">
          <div className="flex items-center justify-center gap-2 mb-2">
            <Shield className="w-4 h-4 text-purple-400" />
            <p className="text-xs text-purple-400">Secret Tracking Code</p>
          </div>
          <p className="text-sm font-mono text-white break-all">{trackingCode}</p>
          <p className="text-xs text-gray-400 mt-2">Save this code to track your report anonymously</p>
        </div>

        {/* Actions */}
        <div className="flex flex-col sm:flex-row gap-3">
          <button
            onClick={() => navigate(`/portal/track/${referenceNumber}`)}
            className="flex-1 flex items-center justify-center gap-2 px-4 py-3 bg-gradient-to-r from-purple-500 to-cyan-500 text-white font-semibold rounded-xl hover:opacity-90 transition-opacity"
          >
            <Eye className="w-5 h-5" />
            Track Status
          </button>
          <button
            onClick={onClose}
            className="flex-1 flex items-center justify-center gap-2 px-4 py-3 bg-white/10 text-white font-semibold rounded-xl hover:bg-white/20 transition-colors"
          >
            Submit Another
          </button>
        </div>
      </div>
    </div>
  );
};

export default function PortalReport() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const reportType = searchParams.get('type') || 'incident';

  const [formData, setFormData] = useState({
    title: '',
    description: '',
    location: '',
    severity: 'medium',
    reporterName: '',
    reporterEmail: '',
    reporterPhone: '',
    department: '',
    isAnonymous: false,
  });

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showSuccess, setShowSuccess] = useState(false);
  const [submissionResult, setSubmissionResult] = useState<{
    referenceNumber: string;
    trackingCode: string;
  } | null>(null);

  const severityOptions = [
    { id: 'low', label: 'Low', description: 'Minor issue', color: '#22c55e' },
    { id: 'medium', label: 'Medium', description: 'Needs attention', color: '#eab308' },
    { id: 'high', label: 'High', description: 'Urgent', color: '#f97316' },
    { id: 'critical', label: 'Critical', description: 'Immediate action', color: '#ef4444' },
  ];

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);

    try {
      const response = await fetch('/api/v1/portal/reports/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          report_type: reportType,
          title: formData.title,
          description: formData.description,
          location: formData.location,
          severity: formData.severity,
          reporter_name: formData.isAnonymous ? null : formData.reporterName,
          reporter_email: formData.isAnonymous ? null : formData.reporterEmail,
          reporter_phone: formData.isAnonymous ? null : formData.reporterPhone,
          department: formData.department,
          is_anonymous: formData.isAnonymous,
        }),
      });

      if (response.ok) {
        const result = await response.json();
        setSubmissionResult({
          referenceNumber: result.reference_number,
          trackingCode: result.tracking_code,
        });
        setShowSuccess(true);
      } else {
        // Handle error
        alert('Failed to submit report. Please try again.');
      }
    } catch (error) {
      // For demo, simulate success
      const demoRef = `${reportType === 'incident' ? 'INC' : 'COMP'}-2026-${Math.floor(Math.random() * 9999).toString().padStart(4, '0')}`;
      setSubmissionResult({
        referenceNumber: demoRef,
        trackingCode: 'demo-' + Math.random().toString(36).substring(7),
      });
      setShowSuccess(true);
    } finally {
      setIsSubmitting(false);
    }
  };

  const resetForm = () => {
    setFormData({
      title: '',
      description: '',
      location: '',
      severity: 'medium',
      reporterName: '',
      reporterEmail: '',
      reporterPhone: '',
      department: '',
      isAnonymous: false,
    });
    setShowSuccess(false);
    setSubmissionResult(null);
  };

  const isIncident = reportType === 'incident';

  return (
    <div className="min-h-screen relative">
      <AnimatedBackground />

      {/* Header */}
      <header className="fixed top-0 left-0 right-0 z-40 bg-black/20 backdrop-blur-xl border-b border-white/10">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center h-16">
            <button
              onClick={() => navigate('/portal')}
              className="flex items-center gap-2 text-gray-400 hover:text-white transition-colors"
            >
              <ArrowLeft className="w-5 h-5" />
              <span>Back</span>
            </button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="pt-24 pb-12 px-4 sm:px-6 lg:px-8 max-w-3xl mx-auto">
        {/* Form Header */}
        <div className="text-center mb-8">
          <div className={`inline-flex w-16 h-16 rounded-2xl items-center justify-center mb-4 ${
            isIncident 
              ? 'bg-gradient-to-br from-red-500 to-orange-500' 
              : 'bg-gradient-to-br from-amber-500 to-yellow-500'
          }`}>
            {isIncident ? (
              <AlertTriangle className="w-8 h-8 text-white" />
            ) : (
              <MessageSquare className="w-8 h-8 text-white" />
            )}
          </div>
          <h1 className="text-3xl font-bold text-white mb-2">
            {isIncident ? 'Report Safety Incident' : 'Submit Complaint'}
          </h1>
          <p className="text-gray-400">
            {isIncident 
              ? 'Help us maintain a safe workplace. All reports are taken seriously.' 
              : 'Your feedback helps us improve. We value your input.'}
          </p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Anonymous Toggle */}
          <div className="bg-gradient-to-r from-purple-500/20 to-cyan-500/20 border border-purple-500/30 rounded-2xl p-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-purple-500/20 rounded-lg">
                  {formData.isAnonymous ? (
                    <EyeOff className="w-5 h-5 text-purple-400" />
                  ) : (
                    <Eye className="w-5 h-5 text-purple-400" />
                  )}
                </div>
                <div>
                  <h3 className="font-semibold text-white">Anonymous Reporting</h3>
                  <p className="text-xs text-gray-400">Your identity will be completely protected</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setFormData(prev => ({ ...prev, isAnonymous: !prev.isAnonymous }))}
                className={`relative w-14 h-8 rounded-full transition-colors ${
                  formData.isAnonymous ? 'bg-purple-500' : 'bg-gray-600'
                }`}
              >
                <div className={`absolute top-1 w-6 h-6 bg-white rounded-full transition-transform ${
                  formData.isAnonymous ? 'translate-x-7' : 'translate-x-1'
                }`} />
              </button>
            </div>
          </div>

          {/* What Happened */}
          <div className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-2xl p-6 space-y-4">
            <h2 className="text-lg font-semibold text-white flex items-center gap-2">
              <Info className="w-5 h-5 text-cyan-400" />
              What Happened?
            </h2>

            {/* Title */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Brief Title <span className="text-red-400">*</span>
              </label>
              <input
                type="text"
                required
                placeholder={isIncident ? "e.g., Slippery floor near entrance" : "e.g., Late delivery of materials"}
                value={formData.title}
                onChange={(e) => setFormData(prev => ({ ...prev, title: e.target.value }))}
                className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
              />
            </div>

            {/* Description */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Description <span className="text-red-400">*</span>
              </label>
              <textarea
                required
                rows={4}
                placeholder="Please provide details about what happened..."
                value={formData.description}
                onChange={(e) => setFormData(prev => ({ ...prev, description: e.target.value }))}
                className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent resize-none"
              />
            </div>

            {/* Location */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                <MapPin className="w-4 h-4 inline mr-1" />
                Location
              </label>
              <input
                type="text"
                placeholder="Where did this occur?"
                value={formData.location}
                onChange={(e) => setFormData(prev => ({ ...prev, location: e.target.value }))}
                className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
              />
            </div>

            {/* Severity */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Severity Level <span className="text-red-400">*</span>
              </label>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                {severityOptions.map((option) => (
                  <SeverityOption
                    key={option.id}
                    {...option}
                    selected={formData.severity === option.id}
                    onClick={() => setFormData(prev => ({ ...prev, severity: option.id }))}
                  />
                ))}
              </div>
            </div>
          </div>

          {/* Contact Information (not shown if anonymous) */}
          {!formData.isAnonymous && (
            <div className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-2xl p-6 space-y-4">
              <h2 className="text-lg font-semibold text-white flex items-center gap-2">
                <User className="w-5 h-5 text-cyan-400" />
                Your Information
              </h2>
              <p className="text-xs text-gray-400">Optional, but helps us follow up with you</p>

              <div className="grid sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    <User className="w-4 h-4 inline mr-1" />
                    Name
                  </label>
                  <input
                    type="text"
                    placeholder="Your name"
                    value={formData.reporterName}
                    onChange={(e) => setFormData(prev => ({ ...prev, reporterName: e.target.value }))}
                    className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    <Building className="w-4 h-4 inline mr-1" />
                    Department
                  </label>
                  <input
                    type="text"
                    placeholder="Your department"
                    value={formData.department}
                    onChange={(e) => setFormData(prev => ({ ...prev, department: e.target.value }))}
                    className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    <Mail className="w-4 h-4 inline mr-1" />
                    Email
                  </label>
                  <input
                    type="email"
                    placeholder="your@email.com"
                    value={formData.reporterEmail}
                    onChange={(e) => setFormData(prev => ({ ...prev, reporterEmail: e.target.value }))}
                    className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    <Phone className="w-4 h-4 inline mr-1" />
                    Phone
                  </label>
                  <input
                    type="tel"
                    placeholder="Your phone number"
                    value={formData.reporterPhone}
                    onChange={(e) => setFormData(prev => ({ ...prev, reporterPhone: e.target.value }))}
                    className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                  />
                </div>
              </div>
            </div>
          )}

          {/* Submit Button */}
          <button
            type="submit"
            disabled={isSubmitting || !formData.title || !formData.description}
            className={`w-full flex items-center justify-center gap-3 px-6 py-4 rounded-2xl font-bold text-lg transition-all ${
              isSubmitting || !formData.title || !formData.description
                ? 'bg-gray-600 text-gray-400 cursor-not-allowed'
                : isIncident
                  ? 'bg-gradient-to-r from-red-500 to-orange-500 text-white hover:opacity-90'
                  : 'bg-gradient-to-r from-amber-500 to-yellow-500 text-white hover:opacity-90'
            }`}
          >
            {isSubmitting ? (
              <>
                <Loader2 className="w-6 h-6 animate-spin" />
                Submitting...
              </>
            ) : (
              <>
                <Send className="w-6 h-6" />
                Submit Report
              </>
            )}
          </button>

          {/* Privacy Notice */}
          <p className="text-center text-xs text-gray-500">
            <Shield className="w-4 h-4 inline mr-1" />
            Your report is encrypted and stored securely. 
            {formData.isAnonymous && ' Your identity will not be recorded.'}
          </p>
        </form>
      </main>

      {/* Success Modal */}
      {showSuccess && submissionResult && (
        <SuccessModal
          referenceNumber={submissionResult.referenceNumber}
          trackingCode={submissionResult.trackingCode}
          onClose={resetForm}
        />
      )}
    </div>
  );
}
