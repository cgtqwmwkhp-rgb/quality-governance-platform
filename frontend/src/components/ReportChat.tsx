/**
 * ReportChat - Two-way messaging between reporter and investigating officer
 *
 * Features:
 * - Real-time messaging interface
 * - File attachments (images, documents, videos)
 * - Message notifications
 * - Read receipts
 * - Conversation closure option
 */

import { useState, useRef, useEffect } from "react";
import {
  Send,
  Paperclip,
  Image,
  FileText,
  Video,
  X,
  Download,
  CheckCheck,
  Clock,
  MessageCircle,
  User,
  Shield,
  Loader2,
  ChevronDown,
  AlertCircle,
} from "lucide-react";
import { Card } from "./ui/Card";
import { Button } from "./ui/Button";
import { Textarea } from "./ui/Textarea";
import { cn } from "../helpers/utils";

// Types
interface Attachment {
  id: string;
  name: string;
  type: "image" | "document" | "video" | "other";
  url: string;
  size: number;
  mimeType: string;
}

interface Message {
  id: string;
  content: string;
  sender: "reporter" | "officer";
  senderName: string;
  timestamp: string;
  attachments: Attachment[];
  isRead: boolean;
  isDelivered: boolean;
}

interface ReportChatProps {
  referenceNumber: string;
  reporterName: string;
  officerName?: string;
  isReporter: boolean; // true if current user is the reporter, false if officer
  isClosed?: boolean;
  onClose?: () => void;
}

// File type detection
const getFileType = (mimeType: string): Attachment["type"] => {
  if (mimeType.startsWith("image/")) return "image";
  if (mimeType.startsWith("video/")) return "video";
  if (
    mimeType.includes("pdf") ||
    mimeType.includes("word") ||
    mimeType.includes("document") ||
    mimeType.includes("text/")
  )
    return "document";
  return "other";
};

// Format file size
const formatFileSize = (bytes: number): string => {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

// File icon component
const FileIcon = ({ type }: { type: Attachment["type"] }) => {
  switch (type) {
    case "image":
      return <Image className="w-4 h-4" />;
    case "video":
      return <Video className="w-4 h-4" />;
    case "document":
      return <FileText className="w-4 h-4" />;
    default:
      return <Paperclip className="w-4 h-4" />;
  }
};

// Attachment preview component
const AttachmentPreview = ({
  attachment,
  onRemove,
  isUploading = false,
}: {
  attachment: Attachment | File;
  onRemove?: () => void;
  isUploading?: boolean;
}) => {
  const isFile = attachment instanceof File;
  const name = isFile ? attachment.name : attachment.name;
  const size = isFile ? attachment.size : attachment.size;
  const type = isFile ? getFileType(attachment.type) : attachment.type;
  const url = isFile ? URL.createObjectURL(attachment) : attachment.url;

  return (
    <div className="relative group flex items-center gap-2 p-2 bg-muted rounded-lg">
      {type === "image" ? (
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
      {isUploading ? (
        <Loader2 className="w-4 h-4 animate-spin text-primary" />
      ) : onRemove ? (
        <button
          onClick={onRemove}
          className="p-1 hover:bg-destructive/10 rounded opacity-0 group-hover:opacity-100 transition-opacity"
        >
          <X className="w-4 h-4 text-destructive" />
        </button>
      ) : (
        <a
          href={url}
          download={name}
          className="p-1 hover:bg-primary/10 rounded"
        >
          <Download className="w-4 h-4 text-primary" />
        </a>
      )}
    </div>
  );
};

// Message bubble component
const MessageBubble = ({
  message,
  isOwn,
}: {
  message: Message;
  isOwn: boolean;
}) => {
  const isOfficer = message.sender === "officer";

  return (
    <div className={cn("flex gap-3 mb-4", isOwn ? "flex-row-reverse" : "")}>
      {/* Avatar */}
      <div
        className={cn(
          "w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0",
          isOfficer ? "bg-primary/10" : "bg-info/10",
        )}
      >
        {isOfficer ? (
          <Shield
            className={cn("w-4 h-4", isOfficer ? "text-primary" : "text-info")}
          />
        ) : (
          <User className="w-4 h-4 text-info" />
        )}
      </div>

      {/* Message content */}
      <div
        className={cn(
          "max-w-[75%] space-y-1",
          isOwn ? "items-end" : "items-start",
        )}
      >
        {/* Sender name */}
        <div
          className={cn(
            "flex items-center gap-2",
            isOwn ? "flex-row-reverse" : "",
          )}
        >
          <span className="text-xs font-medium text-muted-foreground">
            {message.senderName}
          </span>
          {isOfficer && (
            <span className="text-xs px-1.5 py-0.5 bg-primary/10 text-primary rounded">
              Investigator
            </span>
          )}
        </div>

        {/* Bubble */}
        <div
          className={cn(
            "p-3 rounded-2xl",
            isOwn
              ? "bg-primary text-primary-foreground rounded-tr-md"
              : "bg-muted text-foreground rounded-tl-md",
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
            "flex items-center gap-1 text-xs text-muted-foreground",
            isOwn ? "flex-row-reverse" : "",
          )}
        >
          <span>
            {new Date(message.timestamp).toLocaleTimeString("en-GB", {
              hour: "2-digit",
              minute: "2-digit",
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
  );
};

// Main component
export default function ReportChat({
  referenceNumber,
  reporterName,
  officerName = "Safety Team",
  isReporter,
  isClosed = false,
  onClose,
}: ReportChatProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [newMessage, setNewMessage] = useState("");
  const [attachments, setAttachments] = useState<File[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSending, setIsSending] = useState(false);
  const [isExpanded, setIsExpanded] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Load messages
  useEffect(() => {
    loadMessages();
  }, [referenceNumber]);

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const loadMessages = async () => {
    setIsLoading(true);
    try {
      // In production, this would call the API
      // const response = await fetch(`/api/v1/portal/reports/${referenceNumber}/messages`);

      // Demo data
      await new Promise((resolve) => setTimeout(resolve, 500));

      const demoMessages: Message[] = [
        {
          id: "1",
          content:
            "Thank you for submitting this report. I've been assigned to investigate. Could you please provide more details about the exact location where this occurred?",
          sender: "officer",
          senderName: officerName,
          timestamp: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(),
          attachments: [],
          isRead: true,
          isDelivered: true,
        },
        {
          id: "2",
          content:
            "It happened near the main warehouse entrance, by the loading bay 3. I can send you a photo of the exact spot.",
          sender: "reporter",
          senderName: reporterName,
          timestamp: new Date(Date.now() - 23 * 60 * 60 * 1000).toISOString(),
          attachments: [],
          isRead: true,
          isDelivered: true,
        },
        {
          id: "3",
          content: "Here's a photo of the area.",
          sender: "reporter",
          senderName: reporterName,
          timestamp: new Date(Date.now() - 22.5 * 60 * 60 * 1000).toISOString(),
          attachments: [
            {
              id: "att1",
              name: "location-photo.jpg",
              type: "image",
              url: "https://placehold.co/400x300/e2e8f0/64748b?text=Location+Photo",
              size: 245000,
              mimeType: "image/jpeg",
            },
          ],
          isRead: true,
          isDelivered: true,
        },
        {
          id: "4",
          content:
            "Thank you, that's very helpful. I'll be conducting a site visit tomorrow morning. Were there any witnesses present at the time?",
          sender: "officer",
          senderName: officerName,
          timestamp: new Date(Date.now() - 6 * 60 * 60 * 1000).toISOString(),
          attachments: [],
          isRead: true,
          isDelivered: true,
        },
      ];

      setMessages(demoMessages);
    } catch (err) {
      console.error("Failed to load messages:", err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSend = async () => {
    if (!newMessage.trim() && attachments.length === 0) return;

    setIsSending(true);
    try {
      // In production, this would upload files and send to API
      // const formData = new FormData();
      // formData.append('content', newMessage);
      // attachments.forEach(file => formData.append('attachments', file));
      // await fetch(`/api/v1/portal/reports/${referenceNumber}/messages`, {
      //   method: 'POST',
      //   body: formData,
      // });

      await new Promise((resolve) => setTimeout(resolve, 500));

      const newMsg: Message = {
        id: Date.now().toString(),
        content: newMessage,
        sender: isReporter ? "reporter" : "officer",
        senderName: isReporter ? reporterName : officerName,
        timestamp: new Date().toISOString(),
        attachments: attachments.map((file, index) => ({
          id: `new-${index}`,
          name: file.name,
          type: getFileType(file.type),
          url: URL.createObjectURL(file),
          size: file.size,
          mimeType: file.type,
        })),
        isRead: false,
        isDelivered: true,
      };

      setMessages((prev) => [...prev, newMsg]);
      setNewMessage("");
      setAttachments([]);
    } catch (err) {
      console.error("Failed to send message:", err);
    } finally {
      setIsSending(false);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const newFiles = Array.from(e.target.files);
      setAttachments((prev) => [...prev, ...newFiles]);
    }
    // Reset input
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const removeAttachment = (index: number) => {
    setAttachments((prev) => prev.filter((_, i) => i !== index));
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

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
              {messages.length} messages • Chat with{" "}
              {isReporter ? officerName : reporterName}
            </p>
          </div>
        </div>
        <ChevronDown
          className={cn(
            "w-5 h-5 text-muted-foreground transition-transform",
            isExpanded && "rotate-180",
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
                  Start a conversation with{" "}
                  {isReporter ? "the investigating officer" : "the reporter"}
                </p>
              </div>
            ) : (
              <>
                {messages.map((message) => (
                  <MessageBubble
                    key={message.id}
                    message={message}
                    isOwn={
                      (isReporter && message.sender === "reporter") ||
                      (!isReporter && message.sender === "officer")
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
                <button
                  onClick={onClose}
                  className="ml-auto text-primary hover:underline"
                >
                  Reopen
                </button>
              )}
            </div>
          )}

          {/* Attachments preview */}
          {attachments.length > 0 && (
            <div className="px-4 py-2 border-t border-border bg-card space-y-2">
              {attachments.map((file, index) => (
                <AttachmentPreview
                  key={index}
                  attachment={file}
                  onRemove={() => removeAttachment(index)}
                />
              ))}
            </div>
          )}

          {/* Input area */}
          {!isClosed && (
            <div className="p-4 border-t border-border bg-card">
              <div className="flex gap-2">
                {/* File upload button */}
                <input
                  ref={fileInputRef}
                  type="file"
                  multiple
                  accept="image/*,video/*,.pdf,.doc,.docx,.txt"
                  onChange={handleFileSelect}
                  className="hidden"
                />
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => fileInputRef.current?.click()}
                  className="flex-shrink-0"
                >
                  <Paperclip className="w-4 h-4" />
                </Button>

                {/* Message input */}
                <Textarea
                  value={newMessage}
                  onChange={(e) => setNewMessage(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Type a message..."
                  rows={1}
                  className="min-h-[40px] max-h-32 resize-none"
                />

                {/* Send button */}
                <Button
                  onClick={handleSend}
                  disabled={
                    isSending ||
                    (!newMessage.trim() && attachments.length === 0)
                  }
                  className="flex-shrink-0"
                >
                  {isSending ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Send className="w-4 h-4" />
                  )}
                </Button>
              </div>
              <p className="text-xs text-muted-foreground mt-2">
                Press Enter to send • Shift+Enter for new line • Attach images,
                videos, or documents
              </p>
            </div>
          )}
        </>
      )}
    </Card>
  );
}
