/**
 * PlantEx Assist panel (technical module path: copilot/)
 *
 * Conversational shell. Default-off via isAICopilotDemoEnabled().
 * Honesty rules (Run021 residual) live on the backend `/api/v1/copilot` routes:
 * - Never invent tenant compliance / risk figures or named records (PX-248)
 * - Never claim a write completed when nothing was written (PX-250)
 * - Render markdown in replies instead of raw markers (PX-249)
 *
 * This UI calls the API; it must not fall back to client-side canned answers.
 *
 * What the panel *says about itself* is not hardcoded either: the title, subtitle,
 * banner and opening message come from the runtime feature flags in
 * ./copilotDisclosure, because the same bundle is served to a deployment running the
 * keyword simulator and to one running grounded inference over live registers.
 */

import React, { useState, useRef, useEffect, useMemo } from 'react'
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
import { useFeatureFlag } from '../../hooks/useFeatureFlag'
import { CopilotMarkdown } from './CopilotMarkdown'
import { copilotDisclosure, resolveCopilotDisclosureMode } from './copilotDisclosure'
import {
  copilotApi,
  isCopilotUnavailableError,
  type CopilotMessage as ApiCopilotMessage,
} from '../../api/copilot'
import { getApiErrorMessage } from '../../api/client'

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

const UNAVAILABLE_MESSAGE =
  'PlantEx Assist is not enabled in this environment. No simulated answers are available.'

/** Local id of the opening message, which is rewritten if the runtime flags change. */
const WELCOME_MESSAGE_ID = 0

function mapApiMessage(msg: ApiCopilotMessage): Message {
  const contentType =
    msg.content_type === 'action' || msg.content_type === 'error'
      ? msg.content_type
      : 'text'
  const actionStatus =
    msg.action_status === 'pending' ||
    msg.action_status === 'completed' ||
    msg.action_status === 'not_performed' ||
    msg.action_status === 'failed'
      ? msg.action_status
      : undefined
  const role =
    msg.role === 'user' || msg.role === 'system' ? msg.role : 'assistant'

  return {
    id: msg.id,
    role,
    content: msg.content,
    contentType,
    actionType: msg.action_type ?? undefined,
    actionData: msg.action_data ?? undefined,
    actionResult: msg.action_result ?? undefined,
    actionStatus,
    createdAt: new Date(msg.created_at),
  }
}

const AICopilot: React.FC<AICopilotProps> = ({
  isOpen,
  onClose,
  currentPage,
  contextType,
  contextId,
  contextData,
}) => {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [isMinimized, setIsMinimized] = useState(false)
  const [isListening, setIsListening] = useState(false)
  const [showHistory, setShowHistory] = useState(false)
  const [sessionId, setSessionId] = useState<number | null>(null)
  const [sessionReady, setSessionReady] = useState(false)
  const [unavailable, setUnavailable] = useState(false)
  const [sessionError, setSessionError] = useState<string | null>(null)

  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  // Both published by GET /api/v1/meta/features, folding the same configuration and
  // kill switch require_copilot_enabled reads on the server side.
  const copilotOpen = useFeatureFlag('ai_copilot')
  const inferenceOpen = useFeatureFlag('ai_copilot_inference')

  const disclosure = copilotDisclosure(
    resolveCopilotDisclosureMode({ unavailable, copilotOpen, inferenceOpen }),
  )
  const grounded = disclosure.mode === 'grounded'

  const suggestions = useMemo<SuggestedAction[]>(() => {
    const items: SuggestedAction[] = []

    if (contextType === 'incident') {
      items.push({
        action: 'explain_capa',
        displayName: 'What is CAPA?',
        description: 'what is CAPA',
      })
    } else if (currentPage?.includes('audit')) {
      items.push({
        action: 'explain_iso',
        displayName: 'Explain ISO 45001',
        description: 'explain ISO 45001',
      })
    }

    // Register questions are offered only where the server can ground them. Offered
    // anywhere else they would walk the user straight into the refusal path, which
    // reads as a broken feature rather than as the honesty guarantee it is (PX-248).
    if (grounded) {
      items.push(
        {
          action: 'incident_count',
          displayName: 'How many incidents do we have?',
          description: 'how many incidents do we have',
        },
        {
          action: 'overdue_actions',
          displayName: 'Which actions are overdue?',
          description: 'which actions are overdue',
        },
      )
    }

    // Suggestions must not steer users into fabricated live-data answers (PX-248).
    items.push(
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

    return items
  }, [contextType, currentPage, grounded])

  // Initialize backend session when the demo surface opens (context captured at open).
  useEffect(() => {
    if (!isOpen || !isAICopilotDemoEnabled()) {
      setSessionId(null)
      setSessionReady(false)
      setUnavailable(false)
      setSessionError(null)
      setMessages([])
      setInput('')
      setIsMinimized(false)
      return
    }

    let cancelled = false

    const initSession = async () => {
      setUnavailable(false)
      setSessionError(null)
      setSessionReady(false)

      try {
        const { data: session } = await copilotApi.createSession({
          context_type: contextType ?? null,
          context_id: contextId ?? null,
          context_data: contextData ?? null,
          current_page: currentPage ?? null,
        })

        if (cancelled) return

        setSessionId(session.id)
        setSessionReady(true)
        setMessages([
          {
            id: WELCOME_MESSAGE_ID,
            role: 'assistant',
            content: disclosure.welcome,
            contentType: 'text',
            createdAt: new Date(),
          },
        ])
      } catch (err) {
        if (cancelled) return
        if (isCopilotUnavailableError(err)) {
          setUnavailable(true)
          setMessages([])
          setSessionId(null)
          setSessionReady(false)
          return
        }
        setSessionError(
          getApiErrorMessage(err, 'Could not start PlantEx Assist session. Please try again.'),
        )
        setSessionReady(false)
      }
    }

    void initSession()

    return () => {
      cancelled = true
    }
    // Intentionally only re-init when the panel opens/closes — not on every context prop change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen])

  // The flags are fetched asynchronously and default closed, so a grounded deployment
  // can open its session while the panel still believes it is a simulator. Rewriting
  // the opening message is what stops that first bubble claiming "not connected to any
  // AI model" in an environment where a model is answering.
  useEffect(() => {
    if (!disclosure.welcome) return
    setMessages((prev) => {
      const stale = prev.some(
        (message) =>
          message.id === WELCOME_MESSAGE_ID &&
          message.role === 'assistant' &&
          message.content !== disclosure.welcome,
      )
      if (!stale) return prev
      return prev.map((message) =>
        message.id === WELCOME_MESSAGE_ID && message.role === 'assistant'
          ? { ...message, content: disclosure.welcome }
          : message,
      )
    })
  }, [disclosure.welcome])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
    if (isOpen && !isMinimized && !unavailable) {
      inputRef.current?.focus()
    }
  }, [isOpen, isMinimized, unavailable])

  const sendMessage = async () => {
    if (!input.trim() || isLoading || unavailable || !sessionId) return

    const prompt = input.trim()
    const userMessage: Message = {
      id: Date.now(),
      role: 'user',
      content: prompt,
      contentType: 'text',
      createdAt: new Date(),
    }

    setMessages((prev) => [...prev, userMessage])
    setInput('')
    setIsLoading(true)

    try {
      const { data } = await copilotApi.sendMessage(sessionId, prompt)
      setMessages((prev) => [...prev, mapApiMessage(data)])
    } catch (err) {
      if (isCopilotUnavailableError(err)) {
        setUnavailable(true)
        setMessages((prev) => [
          ...prev,
          {
            id: Date.now() + 1,
            role: 'assistant',
            content: UNAVAILABLE_MESSAGE,
            contentType: 'error',
            createdAt: new Date(),
          },
        ])
        return
      }
      const errorMessage: Message = {
        id: Date.now() + 1,
        role: 'assistant',
        content: getApiErrorMessage(err, 'Sorry, I encountered an error. Please try again.'),
        contentType: 'error',
        createdAt: new Date(),
      }
      setMessages((prev) => [...prev, errorMessage])
    } finally {
      setIsLoading(false)
    }
  }

  const submitFeedback = async (messageId: number, rating: number) => {
    setMessages((prev) =>
      prev.map((m) => (m.id === messageId ? { ...m, feedbackRating: rating } : m)),
    )
    if (messageId <= 0 || unavailable) return
    try {
      await copilotApi.submitFeedback(messageId, {
        rating,
        feedback_type: rating >= 4 ? 'helpful' : 'inaccurate',
      })
    } catch {
      // Feedback is best-effort; local UI state already updated.
    }
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
          <span className="font-medium">{disclosure.title}</span>
          {messages.length > 1 && (
            <span className="bg-primary-foreground/20 px-2 py-0.5 rounded-full text-xs">
              {messages.length - 1}
            </span>
          )}
        </Button>
      </div>
    )
  }

  const inputDisabled = unavailable || !sessionReady || isLoading

  return (
    <div className="fixed bottom-4 right-4 w-[420px] h-[600px] bg-card rounded-2xl shadow-lg border border-border flex flex-col z-50 overflow-hidden">
      <div className="gradient-brand px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-primary-foreground/20 flex items-center justify-center">
            <Bot className="w-6 h-6 text-primary-foreground" />
          </div>
          <div>
            <h3 className="font-semibold text-primary-foreground">{disclosure.title}</h3>
            <p className="text-xs text-primary-foreground/70">{disclosure.subtitle}</p>
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

      {disclosure.banner && (
        <div
          role="alert"
          data-testid={disclosure.banner.testId}
          data-copilot-mode={disclosure.mode}
          className={cn(
            'px-4 py-2 border-b text-xs text-foreground',
            disclosure.banner.tone === 'warning'
              ? 'bg-warning/15 border-warning/40'
              : 'bg-info/10 border-info/30',
          )}
        >
          <strong>{disclosure.banner.lead}</strong> {disclosure.banner.detail}
        </div>
      )}

      {unavailable && (
        <div
          role="alert"
          data-testid="ai-copilot-unavailable"
          className="px-4 py-3 bg-destructive/10 border-b border-destructive/20 text-sm text-destructive"
        >
          {UNAVAILABLE_MESSAGE}
        </div>
      )}

      {sessionError && !unavailable && (
        <div
          role="alert"
          data-testid="ai-copilot-session-error"
          className="px-4 py-3 bg-destructive/10 border-b border-destructive/20 text-sm text-destructive"
        >
          {sessionError}
        </div>
      )}

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {!sessionReady && !unavailable && !sessionError && (
          <div className="flex justify-start">
            <div className="bg-surface rounded-2xl px-4 py-3 border border-border">
              <span className="text-sm text-muted-foreground">Connecting…</span>
            </div>
          </div>
        )}

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
                      {disclosure.actionNotPerformed}
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

      {sessionReady && messages.length <= 2 && !unavailable && (
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
              placeholder={disclosure.inputPlaceholder}
              rows={1}
              disabled={inputDisabled}
              className={cn(
                'w-full bg-surface text-foreground rounded-xl px-4 py-3 pr-10 resize-none',
                'focus:outline-none focus:ring-2 focus:ring-primary/50 border border-border',
                'placeholder:text-muted-foreground',
                inputDisabled && 'opacity-60 cursor-not-allowed',
              )}
              style={{ maxHeight: '100px' }}
            />
            <button
              onClick={toggleVoiceInput}
              disabled={inputDisabled}
              className={cn(
                'absolute right-2 bottom-2.5 p-1.5 rounded-lg transition-colors',
                isListening
                  ? 'bg-destructive text-destructive-foreground'
                  : 'text-muted-foreground hover:text-foreground hover:bg-surface',
                inputDisabled && 'pointer-events-none opacity-50',
              )}
            >
              {isListening ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
            </button>
          </div>
          <Button
            onClick={() => void sendMessage()}
            disabled={!input.trim() || inputDisabled}
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
