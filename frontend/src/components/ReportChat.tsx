/**
 * ReportChat - Two-way messaging between reporter and investigating officer
 *
 * Features:
 * - Read-only display of persisted messages
 * - Honest messaging availability status
 */

import { useState, useRef, useEffect, useCallback } from 'react'
import { trackError } from '../utils/errorTracker'
import {
  Paperclip,
  Image,
  FileText,
  Video,
  Download,
  CheckCheck,
  Clock,
  MessageCircle,
  User,
  Shield,
  Loader2,
  ChevronDown,
  AlertCircle,
} from 'lucide-react'
import { Card } from './ui/Card'
import { cn } from '../helpers/utils'

// Types
interface Attachment {
  id: string
  name: string
  type: 'image' | 'document' | 'video' | 'other'
  url: string
  size: number
  mimeType: string
}

interface Message {
  id: string
  content: string
  sender: 'reporter' | 'officer'
  senderName: string
  timestamp: string
  attachments: Attachment[]
  isRead: boolean
  isDelivered: boolean
}

interface ReportChatProps {
  referenceNumber: string
  reporterName: string
  officerName?: string
  isReporter: boolean // true if current user is the reporter, false if officer
  isClosed?: boolean
  onClose?: () => void
}

// Format file size
const formatFileSize = (bytes: number): string => {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

// File icon component
const FileIcon = ({ type }: { type: Attachment['type'] }) => {
  switch (type) {
    case 'image':
      return <Image className="w-4 h-4" />
    case 'video':
      return <Video className="w-4 h-4" />
    case 'document':
      return <FileText className="w-4 h-4" />
    default:
      return <Paperclip className="w-4 h-4" />
  }
}

// Attachment preview component
const AttachmentPreview = ({
  attachment,
}: {
  attachment: Attachment
}) => {
  const { name, size, type, url } = attachment

  return (
    <div className="relative group flex items-center gap-2 p-2 bg-muted rounded-lg">
      {type === 'image' ? (
        <img src={url} alt={name} className="w-10 h-10 object-cover rounded" />
      ) : (
        <div className="w-10 h-10 bg-primary/10 rounded flex items-center justify-center">
          <FileIcon type={type} />
        </div>
      )}
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-foreground truncate">{name}</p>
        <p className="text-xs text-muted-foreground">{formatFileSize(size)}</p>
      </div>
      <a href={url} download={name} className="p-1 hover:bg-primary/10 rounded">
        <Download className="w-4 h-4 text-primary" />
      </a>
    </div>
  )
}

// Message bubble component
const MessageBubble = ({ message, isOwn }: { message: Message; isOwn: boolean }) => {
  const isOfficer = message.sender === 'officer'

  return (
    <div className={cn('flex gap-3 mb-4', isOwn ? 'flex-row-reverse' : '')}>
      {/* Avatar */}
      <div
        className={cn(
          'w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0',
          isOfficer ? 'bg-primary/10' : 'bg-info/10',
        )}
      >
        {isOfficer ? (
          <Shield className={cn('w-4 h-4', isOfficer ? 'text-primary' : 'text-info')} />
        ) : (
          <User className="w-4 h-4 text-info" />
        )}
      </div>

      {/* Message content */}
      <div className={cn('max-w-[75%] space-y-1', isOwn ? 'items-end' : 'items-start')}>
        {/* Sender name */}
        <div className={cn('flex items-center gap-2', isOwn ? 'flex-row-reverse' : '')}>
          <span className="text-xs font-medium text-muted-foreground">{message.senderName}</span>
          {isOfficer && (
            <span className="text-xs px-1.5 py-0.5 bg-primary/10 text-primary rounded">
              Investigator
            </span>
          )}
        </div>

        {/* Bubble */}
        <div
          className={cn(
            'p-3 rounded-2xl',
            isOwn
              ? 'bg-primary text-primary-foreground rounded-tr-md'
              : 'bg-muted text-foreground rounded-tl-md',
          )}
        >
          <p className="text-sm whitespace-pre-wrap">{message.content}</p>
        </div>

        {/* Attachments */}
        {message.attachments.length > 0 && (
          <div className="space-y-2 mt-2">
            {message.attachments.map((attachment) => (
              <AttachmentPreview key={attachment.id} attachment={attachment} />
            ))}
          </div>
        )}

        {/* Timestamp and status */}
        <div
          className={cn(
            'flex items-center gap-1 text-xs text-muted-foreground',
            isOwn ? 'flex-row-reverse' : '',
          )}
        >
          <span>
            {new Date(message.timestamp).toLocaleTimeString('en-GB', {
              hour: '2-digit',
              minute: '2-digit',
            })}
          </span>
          {isOwn &&
            (message.isRead ? (
              <CheckCheck className="w-3 h-3 text-primary" />
            ) : message.isDelivered ? (
              <CheckCheck className="w-3 h-3" />
            ) : (
              <Clock className="w-3 h-3" />
            ))}
        </div>
      </div>
    </div>
  )
}

// Main component
export default function ReportChat({
  referenceNumber,
  reporterName,
  officerName = 'Safety Team',
  isReporter,
  isClosed = false,
  onClose,
}: ReportChatProps) {
  const [messages, setMessages] = useState<Message[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isExpanded, setIsExpanded] = useState(true)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const loadMessages = useCallback(async () => {
    setIsLoading(true)
    try {
      const response = await fetch(`/api/v1/portal/reports/${referenceNumber}/messages`)
      if (response.ok) {
        const data: Message[] = await response.json()
        setMessages(data)
      } else {
        setMessages([])
      }
    } catch (err) {
      trackError(err, { component: 'ReportChat', action: 'loadMessages' })
      setMessages([])
    } finally {
      setIsLoading(false)
    }
  }, [referenceNumber])

  // Load messages
  useEffect(() => {
    loadMessages()
  }, [referenceNumber, loadMessages])

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  return (
    <Card className="overflow-hidden">
      {/* Header */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full p-4 flex items-center justify-between bg-card hover:bg-muted/50 transition-colors border-b border-border"
      >
        <div className="flex items-center gap-3">
          <div className="p-2 bg-primary/10 rounded-lg">
            <MessageCircle className="w-5 h-5 text-primary" />
          </div>
          <div className="text-left">
            <h3 className="font-semibold text-foreground">Messages</h3>
            <p className="text-xs text-muted-foreground">
              {messages.length} messages • Chat with {isReporter ? officerName : reporterName}
            </p>
          </div>
        </div>
        <ChevronDown
          className={cn(
            'w-5 h-5 text-muted-foreground transition-transform',
            isExpanded && 'rotate-180',
          )}
        />
      </button>

      {/* Chat content */}
      {isExpanded && (
        <>
          {/* Messages area */}
          <div className="h-80 overflow-y-auto p-4 bg-surface/50">
            {isLoading ? (
              <div className="flex items-center justify-center h-full">
                <Loader2 className="w-6 h-6 animate-spin text-primary" />
              </div>
            ) : messages.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-center">
                <MessageCircle className="w-12 h-12 text-muted-foreground/30 mb-3" />
                <p className="text-muted-foreground">No messages yet</p>
                <p className="text-sm text-muted-foreground">
                  Start a conversation with{' '}
                  {isReporter ? 'the investigating officer' : 'the reporter'}
                </p>
              </div>
            ) : (
              <>
                {messages.map((message) => (
                  <MessageBubble
                    key={message.id}
                    message={message}
                    isOwn={
                      (isReporter && message.sender === 'reporter') ||
                      (!isReporter && message.sender === 'officer')
                    }
                  />
                ))}
                <div ref={messagesEndRef} />
              </>
            )}
          </div>

          {/* Closed notice */}
          {isClosed && (
            <div className="px-4 py-3 bg-muted/50 border-t border-border flex items-center gap-2 text-sm text-muted-foreground">
              <AlertCircle className="w-4 h-4" />
              This conversation has been closed.
              {onClose && (
                <button onClick={onClose} className="ml-auto text-primary hover:underline">
                  Reopen
                </button>
              )}
            </div>
          )}

          {/* Composer intentionally unavailable until a durable send API exists. */}
          {!isClosed && (
            <div className="p-4 border-t border-border bg-muted/50 flex items-start gap-2 text-sm text-muted-foreground">
              <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
              <p>
                Messaging is not available yet. Existing messages are shown here, but replies and attachments
                cannot be sent until a durable delivery service is enabled.
              </p>
            </div>
          )}
        </>
      )}
    </Card>
  )
}
