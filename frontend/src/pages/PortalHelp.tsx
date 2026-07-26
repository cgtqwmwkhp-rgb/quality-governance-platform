import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
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
  ArrowLeft,
  ExternalLink,
  BookOpen,
  Users,
  Lightbulb,
  ThumbsUp,
  ThumbsDown,
} from 'lucide-react'
import { Card } from '../components/ui/Card'
import { Input } from '../components/ui/Input'
import { Button } from '../components/ui/Button'
import { cn } from '../helpers/utils'
import { getPortalHelpContacts } from '../config/portalHelpContacts'

// FAQ Item component
const FAQItem = ({
  question,
  answer,
  isOpen,
  onClick,
}: {
  question: string
  answer: string
  isOpen: boolean
  onClick: () => void
}) => (
  <Card className="overflow-hidden">
    <button
      onClick={onClick}
      className="w-full flex items-center justify-between p-4 hover:bg-surface transition-colors text-left"
    >
      <span className="font-medium text-foreground">{question}</span>
      {isOpen ? (
        <ChevronDown className="w-5 h-5 text-primary" />
      ) : (
        <ChevronRight className="w-5 h-5 text-muted-foreground" />
      )}
    </button>
    {isOpen && (
      <div className="p-4 bg-surface border-t border-border">
        <p className="text-muted-foreground text-sm leading-relaxed">{answer}</p>
      </div>
    )}
  </Card>
)

// Category card
const CategoryCard = ({
  icon: Icon,
  title,
  description,
  count,
  colorClass,
  onClick,
}: {
  icon: any
  title: string
  description: string
  count: number
  colorClass: string
  onClick: () => void
}) => (
  <Card hoverable className="p-4 cursor-pointer group" onClick={onClick}>
    <div className={cn('w-12 h-12 rounded-xl flex items-center justify-center mb-3', colorClass)}>
      <Icon className="w-6 h-6 text-current" />
    </div>
    <h3 className="font-semibold text-foreground group-hover:text-primary transition-colors">
      {title}
    </h3>
    <p className="text-xs text-muted-foreground mt-1">{description}</p>
    <p className="text-xs text-primary mt-2 font-medium">{count} articles</p>
  </Card>
)

// Quick link
const QuickLink = ({ icon: Icon, title, href }: { icon: any; title: string; href: string }) => (
  <a
    href={href}
    className="flex items-center gap-3 p-3 bg-surface border border-border rounded-xl hover:border-primary/30 transition-colors"
  >
    <Icon className="w-5 h-5 text-primary" />
    <span className="text-foreground text-sm">{title}</span>
    <ExternalLink className="w-4 h-4 text-muted-foreground ml-auto" />
  </a>
)

export default function PortalHelp() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [searchQuery, setSearchQuery] = useState('')
  const [openFAQ, setOpenFAQ] = useState<number | null>(null)
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null)
  const [feedbackGiven, setFeedbackGiven] = useState<{ [key: number]: 'up' | 'down' | null }>({})
  const contacts = getPortalHelpContacts()

  const faqs = [
    {
      category: 'reporting',
      question: 'How do I submit a report?',
      answer:
        'From the Portal home page, select "Submit a Report" and choose the type. Each type opens a short guided form that asks for the customer, who was involved, the location, the date and time, and a description of what happened. Required fields must be completed before you can move to the next step. Your reference number is shown as soon as the report is submitted.',
    },
    {
      category: 'reporting',
      question: 'What types of incidents should I report?',
      answer:
        'The portal covers four types: Incident (an injury or accident), Near Miss (a close call where nobody was hurt), Customer Complaint, and Road Traffic Collision involving a company vehicle. If you have seen a hazard that does not fit one of those, report it as a near miss and explain it in the description. When in doubt, report it!',
    },
    {
      category: 'privacy',
      question: 'Can I submit a report anonymously?',
      answer:
        'No. Reports submitted through the portal are attributable: your name and contact details are recorded with the report and are visible to the team who review it. If you do not feel able to put your name to a concern, use the contact options at the bottom of this page to speak to the safety team before you submit.',
    },
    {
      category: 'privacy',
      question: 'What information is recorded when I submit a report?',
      answer:
        'The details you enter on the form are stored with your report, along with your name, the contact details you provide, and the date and time of submission. Your report can be traced back to you, so please treat anything you submit as attributable.',
    },
    {
      category: 'tracking',
      question: 'What do the different status labels mean?',
      answer:
        'Reported (or Open) = we have received your report. Under Investigation = someone is reviewing it. In Progress = actions are being taken. Pending Review = the actions taken are waiting to be signed off. Resolved and Closed = the issue has been dealt with and the case is complete.',
    },
    {
      category: 'tracking',
      question: 'How do I check the status of my report?',
      answer:
        'Select "Track my report" and enter the reference number you were given when you submitted. If you are signed in to the portal, your recent reports are also listed there, so you can open one without typing a reference number.',
    },
    {
      category: 'tracking',
      question: 'How long does it take to resolve a report?',
      answer:
        'Timescales depend on the type and severity of what you report, and critical safety issues are prioritised. The portal does not set a fixed response time, so use "Track my report" to see the current status and the latest updates on your case.',
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
        'For life-threatening emergencies, ALWAYS call 999 first. Use the portal to document the incident after the immediate danger has been addressed.',
    },
  ]

  const countFor = (categoryId: string) => faqs.filter((faq) => faq.category === categoryId).length

  const categories = [
    {
      id: 'reporting',
      icon: FileText,
      title: 'Reporting Issues',
      description: 'How to submit reports',
      count: countFor('reporting'),
      colorClass: 'bg-info/10 text-info',
    },
    {
      id: 'privacy',
      icon: Shield,
      title: 'Privacy',
      description: 'What we record about you',
      count: countFor('privacy'),
      colorClass: 'bg-purple-100 text-purple-600 dark:bg-purple-900/20 dark:text-purple-400',
    },
    {
      id: 'tracking',
      icon: Clock,
      title: 'Tracking Status',
      description: 'Follow up on reports',
      count: countFor('tracking'),
      colorClass: 'bg-success/10 text-success',
    },
    {
      id: 'emergency',
      icon: AlertTriangle,
      title: 'Emergencies',
      description: 'Urgent situations',
      count: countFor('emergency'),
      colorClass: 'bg-destructive/10 text-destructive',
    },
  ]

  const filteredFAQs = faqs.filter(
    (faq) =>
      (!selectedCategory || faq.category === selectedCategory) &&
      (!searchQuery ||
        faq.question.toLowerCase().includes(searchQuery.toLowerCase()) ||
        faq.answer.toLowerCase().includes(searchQuery.toLowerCase())),
  )

  const giveFeedback = (index: number, type: 'up' | 'down') => {
    setFeedbackGiven((prev) => ({ ...prev, [index]: type }))
  }

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
          <div className="flex items-center gap-2">
            <HelpCircle className="w-5 h-5 text-primary" />
            <span className="font-semibold text-foreground">{t('portal.help_support_title')}</span>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-lg mx-auto px-4 sm:px-6 py-6 pb-12">
        {/* Hero */}
        <div className="text-center mb-8">
          <div className="inline-flex w-16 h-16 rounded-2xl gradient-brand items-center justify-center mb-4 shadow-glow">
            <HelpCircle className="w-8 h-8 text-primary-foreground" />
          </div>
          <h1 className="text-2xl font-bold text-foreground mb-2">{t('portal.how_can_help')}</h1>
          <p className="text-muted-foreground">{t('portal.search_knowledge')}</p>
        </div>

        {/* Search */}
        <div className="relative mb-8">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
          <Input
            type="text"
            placeholder={t('portal.search_answers')}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-10"
          />
        </div>

        {/* Categories */}
        {!searchQuery && !selectedCategory && (
          <div className="mb-8">
            <h2 className="text-base font-semibold text-foreground mb-4">
              {t('portal.browse_category')}
            </h2>
            <div className="grid grid-cols-2 gap-3">
              {categories.map((cat) => (
                <CategoryCard key={cat.id} {...cat} onClick={() => setSelectedCategory(cat.id)} />
              ))}
            </div>
          </div>
        )}

        {/* Category header */}
        {selectedCategory && (
          <div className="flex items-center gap-3 mb-6">
            <button
              onClick={() => setSelectedCategory(null)}
              className="text-primary hover:underline transition-colors text-sm"
            >
              {t('portal.all_categories')}
            </button>
            <ChevronRight className="w-4 h-4 text-muted-foreground" />
            <span className="text-foreground font-medium text-sm">
              {categories.find((c) => c.id === selectedCategory)?.title}
            </span>
          </div>
        )}

        {/* FAQs */}
        <div className="mb-8">
          <h2 className="text-base font-semibold text-foreground mb-4 flex items-center gap-2">
            <Lightbulb className="w-5 h-5 text-warning" />
            {searchQuery ? t('portal.search_results_title') : t('portal.faq_title')}
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
                      <span className="text-xs text-muted-foreground">
                        {t('portal.was_helpful')}
                      </span>
                      <button
                        onClick={() => giveFeedback(index, 'up')}
                        className={cn(
                          'p-1.5 rounded-lg transition-colors',
                          feedbackGiven[index] === 'up'
                            ? 'bg-success/20 text-success'
                            : 'bg-muted text-muted-foreground hover:bg-surface',
                        )}
                      >
                        <ThumbsUp className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => giveFeedback(index, 'down')}
                        className={cn(
                          'p-1.5 rounded-lg transition-colors',
                          feedbackGiven[index] === 'down'
                            ? 'bg-destructive/20 text-destructive'
                            : 'bg-muted text-muted-foreground hover:bg-surface',
                        )}
                      >
                        <ThumbsDown className="w-4 h-4" />
                      </button>
                    </div>
                  )}
                </div>
              ))
            ) : (
              <div className="text-center py-8">
                <BookOpen className="w-12 h-12 text-muted-foreground mx-auto mb-3" />
                <p className="text-muted-foreground">{t('portal.no_articles')}</p>
              </div>
            )}
          </div>
        </div>

        {/* Contact Options */}
        <Card className="p-6 border-primary/20 bg-primary/5">
          <h2 className="text-base font-semibold text-foreground mb-4 flex items-center gap-2">
            <Users className="w-5 h-5 text-primary" />
            {t('portal.still_need_help')}
          </h2>
          <div className="grid gap-3">
            {contacts.chatHref && (
              <QuickLink icon={MessageCircle} title={t('portal.live_chat')} href={contacts.chatHref} />
            )}
            {contacts.emailHref && (
              <QuickLink icon={Mail} title={t('portal.email_support')} href={contacts.emailHref} />
            )}
            {contacts.phoneHref && (
              <QuickLink icon={Phone} title={t('portal.call_helpline')} href={contacts.phoneHref} />
            )}
          </div>
        </Card>

        {/* Quick Actions */}
        <div className="mt-6 flex flex-col sm:flex-row gap-3">
          <Button
            variant="outline"
            onClick={() => navigate('/portal/report')}
            className="flex-1 border-destructive/30 text-destructive hover:bg-destructive/10"
          >
            <AlertTriangle className="w-4 h-4" />
            {t('portal.submit_report_btn')}
          </Button>
          <Button variant="outline" onClick={() => navigate('/portal/track')} className="flex-1">
            <Clock className="w-4 h-4" />
            {t('portal.track_my_report')}
          </Button>
        </div>
      </main>
    </div>
  )
}
