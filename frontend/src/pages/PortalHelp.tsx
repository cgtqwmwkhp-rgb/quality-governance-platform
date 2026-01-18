import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  HelpCircle,
  Search,
  ChevronDown,
  ChevronRight,
  MessageCircle,
  Phone,
  Mail,
  FileText,
  Shield,
  Clock,
  AlertTriangle,
  CheckCircle,
  ArrowLeft,
  ExternalLink,
  BookOpen,
  Users,
  Lightbulb,
  ThumbsUp,
  ThumbsDown,
} from 'lucide-react';

// Animated background
const AnimatedBackground = () => (
  <div className="fixed inset-0 -z-10 overflow-hidden">
    <div className="absolute inset-0 bg-gradient-to-br from-slate-900 via-indigo-900 to-slate-900" />
    <div className="absolute top-0 -left-4 w-96 h-96 bg-indigo-500 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-pulse" />
    <div className="absolute bottom-0 -right-4 w-96 h-96 bg-purple-500 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-pulse" />
  </div>
);

// FAQ Item component
const FAQItem = ({
  question,
  answer,
  isOpen,
  onClick,
}: {
  question: string;
  answer: string;
  isOpen: boolean;
  onClick: () => void;
}) => (
  <div className="border border-white/10 rounded-xl overflow-hidden">
    <button
      onClick={onClick}
      className="w-full flex items-center justify-between p-4 bg-white/5 hover:bg-white/10 transition-colors text-left"
    >
      <span className="font-medium text-white">{question}</span>
      {isOpen ? (
        <ChevronDown className="w-5 h-5 text-indigo-400" />
      ) : (
        <ChevronRight className="w-5 h-5 text-gray-400" />
      )}
    </button>
    {isOpen && (
      <div className="p-4 bg-white/5 border-t border-white/10">
        <p className="text-gray-300 text-sm leading-relaxed">{answer}</p>
      </div>
    )}
  </div>
);

// Category card
const CategoryCard = ({
  icon: Icon,
  title,
  description,
  count,
  color,
  onClick,
}: {
  icon: any;
  title: string;
  description: string;
  count: number;
  color: string;
  onClick: () => void;
}) => (
  <button
    onClick={onClick}
    className="p-5 bg-white/5 border border-white/10 rounded-2xl text-left hover:bg-white/10 transition-all group"
  >
    <div className={`w-12 h-12 rounded-xl flex items-center justify-center mb-3 ${color}`}>
      <Icon className="w-6 h-6 text-white" />
    </div>
    <h3 className="font-bold text-white group-hover:text-indigo-400 transition-colors">{title}</h3>
    <p className="text-xs text-gray-400 mt-1">{description}</p>
    <p className="text-xs text-indigo-400 mt-2">{count} articles</p>
  </button>
);

// Quick link
const QuickLink = ({
  icon: Icon,
  title,
  href,
}: {
  icon: any;
  title: string;
  href: string;
}) => (
  <a
    href={href}
    className="flex items-center gap-3 p-3 bg-white/5 border border-white/10 rounded-xl hover:bg-white/10 transition-colors"
  >
    <Icon className="w-5 h-5 text-indigo-400" />
    <span className="text-white text-sm">{title}</span>
    <ExternalLink className="w-4 h-4 text-gray-500 ml-auto" />
  </a>
);

export default function PortalHelp() {
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState('');
  const [openFAQ, setOpenFAQ] = useState<number | null>(null);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [feedbackGiven, setFeedbackGiven] = useState<{ [key: number]: 'up' | 'down' | null }>({});

  const categories = [
    {
      id: 'reporting',
      icon: FileText,
      title: 'Reporting Issues',
      description: 'How to submit reports',
      count: 8,
      color: 'bg-blue-500',
    },
    {
      id: 'anonymous',
      icon: Shield,
      title: 'Anonymous Reports',
      description: 'Privacy & confidentiality',
      count: 5,
      color: 'bg-purple-500',
    },
    {
      id: 'tracking',
      icon: Clock,
      title: 'Tracking Status',
      description: 'Follow up on reports',
      count: 6,
      color: 'bg-green-500',
    },
    {
      id: 'emergency',
      icon: AlertTriangle,
      title: 'Emergencies',
      description: 'Urgent situations',
      count: 4,
      color: 'bg-red-500',
    },
  ];

  const faqs = [
    {
      category: 'reporting',
      question: 'How do I submit a report?',
      answer:
        'From the Portal home page, select either "Safety Incident" or "Complaint". Fill in the required fields (title and description), optionally add your location and contact details, then click Submit. You\'ll receive a reference number immediately.',
    },
    {
      category: 'reporting',
      question: 'What types of incidents should I report?',
      answer:
        'You should report any safety hazards, accidents, near-misses, equipment failures, workplace injuries, environmental concerns, or any situation that could harm employees or visitors. When in doubt, report it!',
    },
    {
      category: 'anonymous',
      question: 'Is my identity really protected when I report anonymously?',
      answer:
        'Yes, 100%. When you enable the anonymous toggle, no personal information is recorded. We don\'t track IP addresses or device information for anonymous reports. Only the report content is stored.',
    },
    {
      category: 'anonymous',
      question: 'Can I still track my anonymous report?',
      answer:
        'Yes! When you submit an anonymous report, you\'ll receive a secret tracking code along with your reference number. Save this code - it\'s the only way to check your report\'s status.',
    },
    {
      category: 'tracking',
      question: 'What do the different status labels mean?',
      answer:
        'Submitted = We received your report. Under Investigation = A team member is reviewing it. In Progress = Actions are being taken. Resolved = The issue has been addressed. Closed = Case is complete.',
    },
    {
      category: 'tracking',
      question: 'How long does it take to resolve a report?',
      answer:
        'Most reports are acknowledged within 24 hours and resolved within 3-5 business days. Critical safety issues are addressed immediately. You can always check your status using your reference number.',
    },
    {
      category: 'emergency',
      question: 'What counts as an emergency?',
      answer:
        'Emergencies include: active injuries, fire or smoke, security threats, hazardous material spills, structural damage, or any situation requiring immediate response. For life-threatening emergencies, always call 999 first.',
    },
    {
      category: 'emergency',
      question: 'Should I call 999 or use the portal for emergencies?',
      answer:
        'For life-threatening emergencies, ALWAYS call 999 first. Use the portal\'s SOS feature to alert internal response teams simultaneously, but never delay calling emergency services.',
    },
  ];

  const filteredFAQs = faqs.filter(
    (faq) =>
      (!selectedCategory || faq.category === selectedCategory) &&
      (!searchQuery ||
        faq.question.toLowerCase().includes(searchQuery.toLowerCase()) ||
        faq.answer.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  const giveFeedback = (index: number, type: 'up' | 'down') => {
    setFeedbackGiven((prev) => ({ ...prev, [index]: type }));
  };

  return (
    <div className="min-h-screen relative">
      <AnimatedBackground />

      {/* Header */}
      <header className="fixed top-0 left-0 right-0 z-40 bg-black/20 backdrop-blur-xl border-b border-white/10">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center h-16">
            <button
              onClick={() => navigate('/portal')}
              className="flex items-center gap-2 text-gray-400 hover:text-white transition-colors"
            >
              <ArrowLeft className="w-5 h-5" />
              <span>Back to Portal</span>
            </button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="pt-24 pb-12 px-4 sm:px-6 lg:px-8 max-w-4xl mx-auto">
        {/* Hero */}
        <div className="text-center mb-10">
          <div className="inline-flex w-16 h-16 bg-gradient-to-br from-indigo-500 to-purple-500 rounded-2xl items-center justify-center mb-4">
            <HelpCircle className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-4xl font-bold text-white mb-2">How can we help?</h1>
          <p className="text-gray-400">Search our knowledge base or browse by category</p>
        </div>

        {/* Search */}
        <div className="relative mb-8">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
          <input
            type="text"
            placeholder="Search for answers..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-12 pr-4 py-4 bg-white/5 border border-white/10 rounded-2xl text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 text-lg"
          />
        </div>

        {/* Categories */}
        {!searchQuery && !selectedCategory && (
          <div className="mb-10">
            <h2 className="text-lg font-semibold text-white mb-4">Browse by Category</h2>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              {categories.map((cat) => (
                <CategoryCard
                  key={cat.id}
                  {...cat}
                  onClick={() => setSelectedCategory(cat.id)}
                />
              ))}
            </div>
          </div>
        )}

        {/* Category header */}
        {selectedCategory && (
          <div className="flex items-center gap-3 mb-6">
            <button
              onClick={() => setSelectedCategory(null)}
              className="text-indigo-400 hover:text-indigo-300 transition-colors"
            >
              All Categories
            </button>
            <ChevronRight className="w-4 h-4 text-gray-500" />
            <span className="text-white font-medium">
              {categories.find((c) => c.id === selectedCategory)?.title}
            </span>
          </div>
        )}

        {/* FAQs */}
        <div className="mb-10">
          <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <Lightbulb className="w-5 h-5 text-yellow-400" />
            {searchQuery ? 'Search Results' : 'Frequently Asked Questions'}
          </h2>
          <div className="space-y-3">
            {filteredFAQs.length > 0 ? (
              filteredFAQs.map((faq, index) => (
                <div key={index}>
                  <FAQItem
                    question={faq.question}
                    answer={faq.answer}
                    isOpen={openFAQ === index}
                    onClick={() => setOpenFAQ(openFAQ === index ? null : index)}
                  />
                  {openFAQ === index && (
                    <div className="flex items-center justify-end gap-2 mt-2 px-4">
                      <span className="text-xs text-gray-500">Was this helpful?</span>
                      <button
                        onClick={() => giveFeedback(index, 'up')}
                        className={`p-1.5 rounded-lg transition-colors ${
                          feedbackGiven[index] === 'up'
                            ? 'bg-green-500/20 text-green-400'
                            : 'bg-white/5 text-gray-400 hover:bg-white/10'
                        }`}
                      >
                        <ThumbsUp className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => giveFeedback(index, 'down')}
                        className={`p-1.5 rounded-lg transition-colors ${
                          feedbackGiven[index] === 'down'
                            ? 'bg-red-500/20 text-red-400'
                            : 'bg-white/5 text-gray-400 hover:bg-white/10'
                        }`}
                      >
                        <ThumbsDown className="w-4 h-4" />
                      </button>
                    </div>
                  )}
                </div>
              ))
            ) : (
              <div className="text-center py-8">
                <BookOpen className="w-12 h-12 text-gray-600 mx-auto mb-3" />
                <p className="text-gray-400">No articles found. Try a different search term.</p>
              </div>
            )}
          </div>
        </div>

        {/* Contact Options */}
        <div className="bg-gradient-to-r from-indigo-500/20 to-purple-500/20 border border-indigo-500/30 rounded-2xl p-6">
          <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <Users className="w-5 h-5 text-indigo-400" />
            Still need help?
          </h2>
          <div className="grid sm:grid-cols-3 gap-4">
            <QuickLink icon={MessageCircle} title="Live Chat" href="#chat" />
            <QuickLink icon={Mail} title="Email Support" href="mailto:safety@company.com" />
            <QuickLink icon={Phone} title="Call Helpline" href="tel:08001234567" />
          </div>
        </div>

        {/* Quick Actions */}
        <div className="mt-8 flex flex-col sm:flex-row gap-4">
          <button
            onClick={() => navigate('/portal/report?type=incident')}
            className="flex-1 flex items-center justify-center gap-2 px-4 py-3 bg-red-500/20 border border-red-500/30 text-red-400 font-medium rounded-xl hover:bg-red-500/30 transition-colors"
          >
            <AlertTriangle className="w-5 h-5" />
            Report an Incident
          </button>
          <button
            onClick={() => navigate('/portal/track')}
            className="flex-1 flex items-center justify-center gap-2 px-4 py-3 bg-indigo-500/20 border border-indigo-500/30 text-indigo-400 font-medium rounded-xl hover:bg-indigo-500/30 transition-colors"
          >
            <Clock className="w-5 h-5" />
            Track My Report
          </button>
        </div>
      </main>
    </div>
  );
}
