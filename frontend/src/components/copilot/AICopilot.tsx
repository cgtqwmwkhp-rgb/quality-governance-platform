/**
 * AI Copilot Component
 *
 * Demo-only conversational shell. Default-off via isAICopilotDemoEnabled().
 * Honesty rules (Run021 residual):
 * - Never invent tenant compliance / risk figures or named records (PX-248)
 * - Never claim a write completed when nothing was written (PX-250)
 * - Render markdown in replies instead of raw markers (PX-249)
 */

import React, { useState, useRef, useEffect } from 'react'
import {
  Bot,
  Send,
  X,
  Minimize2,
  Mic,
  MicOff,
  ThumbsUp,
  ThumbsDown,
  Sparkles,
  ChevronRight,
  History,
} from 'lucide-react'
import { Button } from '../ui/Button'
import { cn } from '../../helpers/utils'
import { isAICopilotDemoEnabled } from '../../config/aiCopilotDemo'
import { CopilotMarkdown } from './CopilotMarkdown'

interface Message {
  id: number
  role: 'user' | 'assistant' | 'system'
  content: string
  contentType: 'text' | 'action' | 'error'
  actionType?: string
  actionData?: Record<string, unknown>
  actionResult?: Record<string, unknown>
  /** completed only when a real client-side navigation happened; never for writes */
  actionStatus?: 'pending' | 'completed' | 'not_performed' | 'failed'
  createdAt: Date
  feedbackRating?: number
}

interface SuggestedAction {
  action: string
  displayName: string
  description: string
  parameters?: Record<string, unknown>
}

interface AICopilotProps {
  isOpen: boolean
  onClose: () => void
  currentPage?: string
  contextType?: string
  contextId?: string
  contextData?: Record<string, unknown>
}

const LIVE_DATA_REFUSAL =
  'I cannot answer from live organisation data. This demo is not connected to your registers, so I will not invent counts, percentages, named risks, or reference numbers. Open the relevant module for real figures.'

const WRITE_REFUSAL =
  'I cannot create or update records from this demo. Nothing was written. Use the Incidents register (New) to log a real safety event.'

const AICopilot: React.FC<AICopilotProps> = ({
  isOpen,
  onClose,
  currentPage,
  contextType,
  contextId: _contextId,
  contextData: _contextData,
}) => {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [isMinimized, setIsMinimized] = useState(false)
  const [isListening, setIsListening] = useState(false)
  const [suggestions, setSuggestions] = useState<SuggestedAction[]>([])
  const [showHistory, setShowHistory] = useState(false)

  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  // Initialize session and welcome message
  useEffect(() => {
    if (isOpen && messages.length === 0) {
      const welcomeMessage: Message = {
        id: Date.now(),
        role: 'assistant',
        content: `This is a demonstration of a planned AI assistant. It is not connected to any AI model or to your organisation's records.\n\nI will **refuse** live-data questions (compliance status, risk summaries) and will **not** claim to create incidents or actions. Concept explanations (for example CAPA or RIDDOR) are general guidance only.\n\nTry "what is CAPA" for a concept preview, or open Compliance / Risk Register for real figures.`,
        contentType: 'text',
        createdAt: new Date(),
      }
      setMessages([welcomeMessage])

      fetchSuggestions()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
    if (isOpen && !isMinimized) {
      inputRef.current?.focus()
    }
  }, [isOpen, isMinimized])

  const fetchSuggestions = async () => {
    const contextSuggestions: SuggestedAction[] = []

    if (contextType === 'incident') {
      contextSuggestions.push({
        action: 'explain_capa',
        displayName: 'What is CAPA?',
        description: 'what is CAPA',
      })
    } else if (currentPage?.includes('audit')) {
      contextSuggestions.push({
        action: 'explain_iso',
        displayName: 'Explain ISO 45001',
        description: 'explain ISO 45001',
      })
    }

    // Suggestions must not steer users into fabricated live-data answers (PX-248).
    contextSuggestions.push(
      {
        action: 'explain_capa',
        displayName: 'What is CAPA?',
        description: 'what is CAPA',
      },
      {
        action: 'explain_riddor',
        displayName: 'What is RIDDOR?',
        description: 'what is RIDDOR',
      },
    )

    setSuggestions(contextSuggestions)
  }

  const sendMessage = async () => {
    if (!input.trim() || isLoading) return

    const userMessage: Message = {
      id: Date.now(),
      role: 'user',
      content: input.trim(),
      contentType: 'text',
      createdAt: new Date(),
    }

    setMessages((prev) => [...prev, userMessage])
    const prompt = input.trim()
    setInput('')
    setIsLoading(true)

    try {
      await new Promise((resolve) => setTimeout(resolve, 300))

      const response = generateResponse(prompt)

      const assistantMessage: Message = {
        id: Date.now() + 1,
        role: 'assistant',
        content: response.content,
        contentType: response.actionType ? 'action' : 'text',
        actionType: response.actionType,
        actionData: response.actionData,
        actionStatus: response.actionStatus,
        actionResult: response.actionResult,
        createdAt: new Date(),
      }

      setMessages((prev) => [...prev, assistantMessage])
    } catch {
      const errorMessage: Message = {
        id: Date.now() + 1,
        role: 'assistant',
        content: 'Sorry, I encountered an error. Please try again.',
        contentType: 'error',
        createdAt: new Date(),
      }
      setMessages((prev) => [...prev, errorMessage])
    } finally {
      setIsLoading(false)
    }
  }

  const generateResponse = (
    rawInput: string,
  ): {
    content: string
    actionType?: string
    actionData?: Record<string, unknown>
    actionStatus?: Message['actionStatus']
    actionResult?: Record<string, unknown>
  } => {
    const inputLower = rawInput.toLowerCase()

    // PX-250: never ask "Shall I proceed?" and then claim completion. Refuse writes.
    if (inputLower.includes('create') && inputLower.includes('incident')) {
      return {
        content: WRITE_REFUSAL,
        actionType: 'create_incident',
        actionData: { title: rawInput },
        actionStatus: 'not_performed',
        actionResult: { performed: false, reason: 'demo_cannot_write' },
      }
    }

    // PX-248: refuse fabricated compliance / risk tenant data.
    if (inputLower.includes('compliance') || inputLower.includes('iso')) {
      const mentionsIsoStandard =
        /iso\s*(9001|14001|45001|27001)/i.test(rawInput) ||
        inputLower.includes('compliance')
      if (mentionsIsoStandard && !inputLower.startsWith('what is') && !inputLower.startsWith('explain')) {
        return {
          content: `${LIVE_DATA_REFUSAL}\n\nFor ISO clause scores, open **Compliance** in the main navigation.`,
          actionType: 'get_compliance_status',
          actionStatus: 'not_performed',
          actionResult: { performed: false, reason: 'no_live_data' },
        }
      }
    }

    if (
      inputLower.includes('risk summary') ||
      inputLower.includes('risk register') ||
      (inputLower.includes('risk') &&
        (inputLower.includes('summary') ||
          inputLower.includes('status') ||
          inputLower.includes('how many') ||
          inputLower.includes('critical')))
    ) {
      return {
        content: `${LIVE_DATA_REFUSAL}\n\nOpen the **Risk Register** for the live register.`,
        actionType: 'get_risk_summary',
        actionStatus: 'not_performed',
        actionResult: { performed: false, reason: 'no_live_data' },
      }
    }

    // Generic "risk" still refused — any invented named risk is the PX-248 failure mode.
    if (/\brisks?\b/.test(inputLower) && !inputLower.startsWith('what is') && !inputLower.startsWith('explain')) {
      return {
        content: `${LIVE_DATA_REFUSAL}\n\nOpen the **Risk Register** for the live register.`,
        actionType: 'get_risk_summary',
        actionStatus: 'not_performed',
        actionResult: { performed: false, reason: 'no_live_data' },
      }
    }

    if (inputLower.includes('what is') || inputLower.includes('explain')) {
      const topic = rawInput.replace(/what is|explain/gi, '').trim()

      const explanations: Record<string, string> = {
        capa: `**CAPA (Corrective and Preventive Action)**\n\nA systematic approach to:\n1. **Corrective Action** - Fix immediate problems and root causes\n2. **Preventive Action** - Prevent similar issues from occurring\n\nRequired by ISO 9001 (Clause 10.2)\nEssential for continuous improvement\nMust be documented and verified\n\n_General guidance only — not your organisation's CAPA register._`,
        riddor: `**RIDDOR**\n\n**Reporting of Injuries, Diseases and Dangerous Occurrences Regulations 2013**\n\nUK employers must report:\n• Deaths and specified injuries\n• Over-7-day incapacitation\n• Occupational diseases\n• Dangerous occurrences\n\nReport within 10-15 days to HSE\n\n_General guidance only — not a filing status for your cases._`,
        'iso 45001': `**ISO 45001** is the international standard for Occupational Health & Safety Management Systems.\n\nKey elements:\n• Leadership commitment\n• Worker participation\n• Hazard identification\n• Legal compliance\n• Continual improvement\n\n_General guidance only — not your compliance score._`,
      }

      const key = topic.toLowerCase()
      return {
        content:
          explanations[key] ||
          `**${topic}**\n\nI can only offer general QHSE definitions in this demo. I cannot look up your organisation's records.`,
      }
    }

    return {
      content: `I understand you're asking about: "${rawInput}"\n\nIn this demo I can:\n• Explain QHSE concepts (try "what is CAPA")\n• Honestly refuse live-data questions (compliance / risk figures)\n• Honestly refuse writes (creating incidents)\n\nI will not invent register data. Open the relevant module for real figures.`,
    }
  }

  const submitFeedback = async (messageId: number, rating: number) => {
    setMessages((prev) =>
      prev.map((m) => (m.id === messageId ? { ...m, feedbackRating: rating } : m)),
    )
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      void sendMessage()
    }
  }

  const handleSuggestionClick = (suggestion: SuggestedAction) => {
    setInput(suggestion.description)
    inputRef.current?.focus()
  }

  const toggleVoiceInput = () => {
    if (isListening) {
      setIsListening(false)
    } else {
      setIsListening(true)
      if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
        const SpeechRecognition =
          (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
        const recognition = new SpeechRecognition()
        recognition.continuous = false
        recognition.interimResults = false
        recognition.lang = 'en-GB'

        recognition.onresult = (event: any) => {
          const transcript = event.results[0][0].transcript
          setInput((prev) => prev + transcript)
          setIsListening(false)
        }

        recognition.onerror = () => {
          setIsListening(false)
        }

        recognition.onend = () => {
          setIsListening(false)
        }

        recognition.start()
      }
    }
  }

  // Second line of defence behind Layout's gate: never render simulated answers
  // when the demo flag is off, however this component gets mounted (PX-248).
  if (!isAICopilotDemoEnabled()) return null

  if (!isOpen) return null

  if (isMinimized) {
    return (
      <div className="fixed bottom-4 right-4 z-50">
        <Button onClick={() => setIsMinimized(false)} className="rounded-full gap-2 shadow-glow">
          <Bot className="w-5 h-5" />
          <span className="font-medium">AI Copilot (Demo)</span>
          {messages.length > 1 && (
            <span className="bg-primary-foreground/20 px-2 py-0.5 rounded-full text-xs">
              {messages.length - 1}
            </span>
          )}
        </Button>
      </div>
    )
  }

  return (
    <div className="fixed bottom-4 right-4 w-[420px] h-[600px] bg-card rounded-2xl shadow-lg border border-border flex flex-col z-50 overflow-hidden">
      <div className="gradient-brand px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-primary-foreground/20 flex items-center justify-center">
            <Bot className="w-6 h-6 text-primary-foreground" />
          </div>
          <div>
            <h3 className="font-semibold text-primary-foreground">AI Copilot (Demo)</h3>
            <p className="text-xs text-primary-foreground/70">Simulated — not live data</p>
          </div>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={() => setShowHistory(!showHistory)}
            className="p-2 hover:bg-primary-foreground/10 rounded-lg transition-colors text-primary-foreground/80 hover:text-primary-foreground"
            title="History"
          >
            <History className="w-4 h-4" />
          </button>
          <button
            onClick={() => setIsMinimized(true)}
            className="p-2 hover:bg-primary-foreground/10 rounded-lg transition-colors text-primary-foreground/80 hover:text-primary-foreground"
            title="Minimize"
          >
            <Minimize2 className="w-4 h-4" />
          </button>
          <button
            onClick={onClose}
            className="p-2 hover:bg-primary-foreground/10 rounded-lg transition-colors text-primary-foreground/80 hover:text-primary-foreground"
            title="Close"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      <div
        role="alert"
        data-testid="ai-copilot-demo-banner"
        className="px-4 py-2 bg-warning/15 border-b border-warning/40 text-xs text-foreground"
      >
        <strong>Demonstration only.</strong> Live-data questions are refused. Writes are never
        performed. Do not quote this surface as organisational truth.
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((message) => (
          <div
            key={message.id}
            className={cn('flex', message.role === 'user' ? 'justify-end' : 'justify-start')}
          >
            <div
              className={cn(
                'max-w-[85%] rounded-2xl px-4 py-3',
                message.role === 'user'
                  ? 'bg-primary text-primary-foreground'
                  : message.contentType === 'error'
                    ? 'bg-destructive/10 text-destructive border border-destructive/20'
                    : 'bg-surface text-foreground border border-border',
              )}
            >
              {message.role === 'assistant' ? (
                <CopilotMarkdown
                  content={message.content}
                  className="text-sm leading-relaxed"
                />
              ) : (
                <div className="text-sm whitespace-pre-wrap leading-relaxed">{message.content}</div>
              )}

              {message.actionType && (
                <div className="mt-2 pt-2 border-t border-border flex items-center gap-2 text-xs">
                  {message.actionStatus === 'completed' && (
                    <>
                      <Sparkles className="w-3 h-3 text-success" />
                      <span className="text-success">Action completed</span>
                    </>
                  )}
                  {message.actionStatus === 'not_performed' && (
                    <span className="text-muted-foreground" data-testid="copilot-action-not-performed">
                      Not performed — demo cannot write or read live registers
                    </span>
                  )}
                  {message.actionStatus === 'failed' && (
                    <>
                      <X className="w-3 h-3 text-destructive" />
                      <span className="text-destructive">Action failed</span>
                    </>
                  )}
                </div>
              )}

              {message.role === 'assistant' && message.contentType !== 'error' && (
                <div className="mt-2 pt-2 border-t border-border flex items-center gap-2">
                  <span className="text-xs text-muted-foreground">Was this helpful?</span>
                  <button
                    onClick={() => void submitFeedback(message.id, 5)}
                    className={cn(
                      'p-1 rounded hover:bg-surface transition-colors',
                      message.feedbackRating === 5
                        ? 'text-success'
                        : 'text-muted-foreground hover:text-success',
                    )}
                  >
                    <ThumbsUp className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => void submitFeedback(message.id, 1)}
                    className={cn(
                      'p-1 rounded hover:bg-surface transition-colors',
                      message.feedbackRating === 1
                        ? 'text-destructive'
                        : 'text-muted-foreground hover:text-destructive',
                    )}
                  >
                    <ThumbsDown className="w-4 h-4" />
                  </button>
                </div>
              )}
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="flex justify-start">
            <div className="bg-surface rounded-2xl px-4 py-3 border border-border">
              <div className="flex items-center gap-2">
                <div className="flex space-x-1">
                  <div
                    className="w-2 h-2 bg-primary rounded-full animate-bounce"
                    style={{ animationDelay: '0ms' }}
                  />
                  <div
                    className="w-2 h-2 bg-primary rounded-full animate-bounce"
                    style={{ animationDelay: '150ms' }}
                  />
                  <div
                    className="w-2 h-2 bg-primary rounded-full animate-bounce"
                    style={{ animationDelay: '300ms' }}
                  />
                </div>
                <span className="text-sm text-muted-foreground">Thinking...</span>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {suggestions.length > 0 && messages.length <= 2 && (
        <div className="px-4 pb-2">
          <div className="flex items-center gap-2 text-xs text-muted-foreground mb-2">
            <Sparkles className="w-3 h-3" />
            <span>Suggested</span>
          </div>
          <div className="flex flex-wrap gap-2">
            {suggestions.slice(0, 3).map((suggestion, i) => (
              <button
                key={i}
                onClick={() => handleSuggestionClick(suggestion)}
                className="flex items-center gap-1 px-3 py-1.5 bg-surface hover:bg-surface/80 rounded-full text-xs text-foreground border border-border transition-colors"
              >
                {suggestion.displayName}
                <ChevronRight className="w-3 h-3" />
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="p-4 border-t border-border">
        <div className="flex items-end gap-2">
          <div className="flex-1 relative">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask me anything..."
              rows={1}
              className={cn(
                'w-full bg-surface text-foreground rounded-xl px-4 py-3 pr-10 resize-none',
                'focus:outline-none focus:ring-2 focus:ring-primary/50 border border-border',
                'placeholder:text-muted-foreground',
              )}
              style={{ maxHeight: '100px' }}
            />
            <button
              onClick={toggleVoiceInput}
              className={cn(
                'absolute right-2 bottom-2.5 p-1.5 rounded-lg transition-colors',
                isListening
                  ? 'bg-destructive text-destructive-foreground'
                  : 'text-muted-foreground hover:text-foreground hover:bg-surface',
              )}
            >
              {isListening ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
            </button>
          </div>
          <Button
            onClick={() => void sendMessage()}
            disabled={!input.trim() || isLoading}
            size="icon"
            aria-label="Send"
          >
            <Send className="w-5 h-5" />
          </Button>
        </div>
        <p className="text-xs text-muted-foreground mt-2 text-center">
          Press Enter to send | Shift+Enter for new line
        </p>
      </div>
    </div>
  )
}

export default AICopilot
