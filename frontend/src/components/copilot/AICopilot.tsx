/**
 * AI Copilot Component
 * 
 * Interactive conversational AI assistant with:
 * - Natural language chat interface
 * - Context-aware suggestions
 * - Action execution
 * - Voice input support
 * - Feedback mechanism
 */

import React, { useState, useRef, useEffect } from 'react';
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
  Loader2,
  ChevronRight,
  History,
} from 'lucide-react';
import { Button } from '../ui/Button';
import { cn } from '../../lib/utils';

interface Message {
  id: number;
  role: 'user' | 'assistant' | 'system';
  content: string;
  contentType: 'text' | 'action' | 'error';
  actionType?: string;
  actionData?: Record<string, unknown>;
  actionResult?: Record<string, unknown>;
  actionStatus?: 'pending' | 'completed' | 'failed';
  createdAt: Date;
  feedbackRating?: number;
}

interface SuggestedAction {
  action: string;
  displayName: string;
  description: string;
  parameters?: Record<string, unknown>;
}

interface AICopilotProps {
  isOpen: boolean;
  onClose: () => void;
  currentPage?: string;
  contextType?: string;
  contextId?: string;
  contextData?: Record<string, unknown>;
}

const AICopilot: React.FC<AICopilotProps> = ({
  isOpen,
  onClose,
  currentPage,
  contextType,
  contextId: _contextId,
  contextData: _contextData,
}) => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isMinimized, setIsMinimized] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [_sessionId, _setSessionId] = useState<number | null>(null);
  const [suggestions, setSuggestions] = useState<SuggestedAction[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  
  // Initialize session and welcome message
  useEffect(() => {
    if (isOpen && messages.length === 0) {
      const welcomeMessage: Message = {
        id: Date.now(),
        role: 'assistant',
        content: `Hello! I'm your AI assistant for the Quality Governance Platform.\n\nI can help you with:\n• Creating and managing incidents\n• Scheduling audits\n• Risk assessment\n• Compliance queries\n• Generating reports\n\nHow can I assist you today?`,
        contentType: 'text',
        createdAt: new Date(),
      };
      setMessages([welcomeMessage]);
      
      // Get context-aware suggestions
      fetchSuggestions();
    }
  }, [isOpen]);
  
  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);
  
  // Focus input when opened
  useEffect(() => {
    if (isOpen && !isMinimized) {
      inputRef.current?.focus();
    }
  }, [isOpen, isMinimized]);
  
  const fetchSuggestions = async () => {
    // Simulated suggestions based on context
    const contextSuggestions: SuggestedAction[] = [];
    
    if (contextType === 'incident') {
      contextSuggestions.push(
        { action: 'create_action', displayName: 'Create CAPA', description: 'Create corrective action for this incident' },
        { action: 'search_incidents', displayName: 'Find Similar', description: 'Search for related incidents' }
      );
    } else if (currentPage?.includes('audit')) {
      contextSuggestions.push(
        { action: 'schedule_audit', displayName: 'Schedule Audit', description: 'Plan a new audit' }
      );
    }
    
    // Default suggestions
    contextSuggestions.push(
      { action: 'get_compliance_status', displayName: 'Compliance Status', description: 'Check ISO compliance' },
      { action: 'get_risk_summary', displayName: 'Risk Summary', description: 'View current risks' }
    );
    
    setSuggestions(contextSuggestions);
  };
  
  const sendMessage = async () => {
    if (!input.trim() || isLoading) return;
    
    const userMessage: Message = {
      id: Date.now(),
      role: 'user',
      content: input.trim(),
      contentType: 'text',
      createdAt: new Date(),
    };
    
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);
    
    try {
      // Simulate API call
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      // Generate response based on input
      const response = generateResponse(input.trim());
      
      const assistantMessage: Message = {
        id: Date.now() + 1,
        role: 'assistant',
        content: response.content,
        contentType: response.actionType ? 'action' : 'text',
        actionType: response.actionType,
        actionData: response.actionData,
        actionStatus: response.actionType ? 'pending' : undefined,
        createdAt: new Date(),
      };
      
      setMessages(prev => [...prev, assistantMessage]);
      
      // Execute action if present
      if (response.actionType) {
        await executeAction(assistantMessage.id, response.actionType, response.actionData);
      }
      
    } catch (error) {
      const errorMessage: Message = {
        id: Date.now() + 1,
        role: 'assistant',
        content: 'Sorry, I encountered an error. Please try again.',
        contentType: 'error',
        createdAt: new Date(),
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };
  
  const generateResponse = (input: string): { content: string; actionType?: string; actionData?: Record<string, unknown> } => {
    const inputLower = input.toLowerCase();
    
    if (inputLower.includes('create') && inputLower.includes('incident')) {
      return {
        content: `I'll help you create an incident report.\n\n**New Incident**\n• Title: ${input.replace(/create (an? )?incident (for )?/i, '')}\n• Severity: Medium\n\nShall I proceed with creating this incident?`,
        actionType: 'create_incident',
        actionData: { title: input.replace(/create (an? )?incident (for )?/i, ''), severity: 'medium' },
      };
    }
    
    if (inputLower.includes('compliance') || inputLower.includes('iso')) {
      let standard = 'ISO 9001';
      if (inputLower.includes('14001')) standard = 'ISO 14001';
      else if (inputLower.includes('45001')) standard = 'ISO 45001';
      else if (inputLower.includes('27001')) standard = 'ISO 27001';
      
      return {
        content: `**${standard} Compliance Status**\n\nOverall Compliance: **92%**\n\n| Category | Status | Score |\n|----------|--------|-------|\n| Leadership | Compliant | 95% |\n| Planning | Compliant | 90% |\n| Support | Minor Gap | 85% |\n| Operation | Compliant | 94% |\n| Evaluation | Compliant | 93% |\n| Improvement | Minor Gap | 88% |\n\n**3 minor gaps** identified. Would you like me to show details or create actions to address them?`,
        actionType: 'get_compliance_status',
        actionData: { standard },
      };
    }
    
    if (inputLower.includes('risk')) {
      return {
        content: `**Risk Summary**\n\n| Level | Count | Trend |\n|-------|-------|-------|\n| Critical | 2 | Down |\n| High | 8 | Stable |\n| Medium | 15 | Up |\n| Low | 23 | Stable |\n\n**Top Risk:** Supply Chain Disruption (Score: 20)\n**New This Week:** Cybersecurity Threat\n\nWould you like to see the risk heat map or create a treatment plan?`,
      };
    }
    
    if (inputLower.includes('what is') || inputLower.includes('explain')) {
      const topic = input.replace(/what is|explain/gi, '').trim();
      
      const explanations: Record<string, string> = {
        'capa': `**CAPA (Corrective and Preventive Action)**\n\nA systematic approach to:\n1. **Corrective Action** - Fix immediate problems and root causes\n2. **Preventive Action** - Prevent similar issues from occurring\n\nRequired by ISO 9001 (Clause 10.2)\nEssential for continuous improvement\nMust be documented and verified`,
        'riddor': `**RIDDOR**\n\n**Reporting of Injuries, Diseases and Dangerous Occurrences Regulations 2013**\n\nUK employers must report:\n• Deaths and specified injuries\n• Over-7-day incapacitation\n• Occupational diseases\n• Dangerous occurrences\n\nReport within 10-15 days to HSE`,
      };
      
      return {
        content: explanations[topic.toLowerCase()] || `**${topic}**\n\nI'd be happy to explain this. Could you provide more context about what aspect you'd like to understand?`,
      };
    }
    
    return {
      content: `I understand you're asking about: "${input}"\n\nI can help you with:\n• Creating incidents or actions\n• Checking compliance status\n• Viewing risk summaries\n• Explaining QHSE concepts\n• Searching records\n\nCould you be more specific about what you'd like to do?`,
    };
  };
  
  const executeAction = async (messageId: number, _actionType: string, _actionData?: Record<string, unknown>) => {
    // Simulate action execution
    await new Promise(resolve => setTimeout(resolve, 500));
    
    setMessages(prev => prev.map(m => 
      m.id === messageId 
        ? { ...m, actionStatus: 'completed', actionResult: { success: true } }
        : m
    ));
  };
  
  const submitFeedback = async (messageId: number, rating: number) => {
    setMessages(prev => prev.map(m =>
      m.id === messageId
        ? { ...m, feedbackRating: rating }
        : m
    ));
    
    // Would send to API
    console.log('Feedback submitted:', { messageId, rating });
  };
  
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };
  
  const handleSuggestionClick = (suggestion: SuggestedAction) => {
    setInput(suggestion.description);
    inputRef.current?.focus();
  };
  
  const toggleVoiceInput = () => {
    if (isListening) {
      setIsListening(false);
      // Stop speech recognition
    } else {
      setIsListening(true);
      // Start speech recognition
      if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
        const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
        const recognition = new SpeechRecognition();
        recognition.continuous = false;
        recognition.interimResults = false;
        recognition.lang = 'en-GB';
        
        recognition.onresult = (event: any) => {
          const transcript = event.results[0][0].transcript;
          setInput(prev => prev + transcript);
          setIsListening(false);
        };
        
        recognition.onerror = () => {
          setIsListening(false);
        };
        
        recognition.onend = () => {
          setIsListening(false);
        };
        
        recognition.start();
      }
    }
  };
  
  if (!isOpen) return null;
  
  if (isMinimized) {
    return (
      <div className="fixed bottom-4 right-4 z-50">
        <Button
          onClick={() => setIsMinimized(false)}
          className="rounded-full gap-2 shadow-glow"
        >
          <Bot className="w-5 h-5" />
          <span className="font-medium">AI Copilot</span>
          {messages.length > 1 && (
            <span className="bg-primary-foreground/20 px-2 py-0.5 rounded-full text-xs">
              {messages.length - 1}
            </span>
          )}
        </Button>
      </div>
    );
  }
  
  return (
    <div className="fixed bottom-4 right-4 w-[420px] h-[600px] bg-card rounded-2xl shadow-lg border border-border flex flex-col z-50 overflow-hidden">
      {/* Header */}
      <div className="gradient-brand px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-primary-foreground/20 flex items-center justify-center">
            <Bot className="w-6 h-6 text-primary-foreground" />
          </div>
          <div>
            <h3 className="font-semibold text-primary-foreground">AI Copilot</h3>
            <p className="text-xs text-primary-foreground/70">Your QHSE Assistant</p>
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
      
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((message) => (
          <div
            key={message.id}
            className={cn("flex", message.role === 'user' ? 'justify-end' : 'justify-start')}
          >
            <div
              className={cn(
                "max-w-[85%] rounded-2xl px-4 py-3",
                message.role === 'user'
                  ? 'bg-primary text-primary-foreground'
                  : message.contentType === 'error'
                  ? 'bg-destructive/10 text-destructive border border-destructive/20'
                  : 'bg-surface text-foreground border border-border'
              )}
            >
              {/* Message content */}
              <div className="text-sm whitespace-pre-wrap leading-relaxed">
                {message.content}
              </div>
              
              {/* Action indicator */}
              {message.actionType && (
                <div className="mt-2 pt-2 border-t border-border flex items-center gap-2 text-xs">
                  {message.actionStatus === 'pending' && (
                    <>
                      <Loader2 className="w-3 h-3 animate-spin" />
                      <span>Processing...</span>
                    </>
                  )}
                  {message.actionStatus === 'completed' && (
                    <>
                      <Sparkles className="w-3 h-3 text-success" />
                      <span className="text-success">Action completed</span>
                    </>
                  )}
                  {message.actionStatus === 'failed' && (
                    <>
                      <X className="w-3 h-3 text-destructive" />
                      <span className="text-destructive">Action failed</span>
                    </>
                  )}
                </div>
              )}
              
              {/* Feedback buttons for assistant messages */}
              {message.role === 'assistant' && message.contentType !== 'error' && (
                <div className="mt-2 pt-2 border-t border-border flex items-center gap-2">
                  <span className="text-xs text-muted-foreground">Was this helpful?</span>
                  <button
                    onClick={() => submitFeedback(message.id, 5)}
                    className={cn(
                      "p-1 rounded hover:bg-surface transition-colors",
                      message.feedbackRating === 5 ? 'text-success' : 'text-muted-foreground hover:text-success'
                    )}
                  >
                    <ThumbsUp className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => submitFeedback(message.id, 1)}
                    className={cn(
                      "p-1 rounded hover:bg-surface transition-colors",
                      message.feedbackRating === 1 ? 'text-destructive' : 'text-muted-foreground hover:text-destructive'
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
                  <div className="w-2 h-2 bg-primary rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                  <div className="w-2 h-2 bg-primary rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                  <div className="w-2 h-2 bg-primary rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                </div>
                <span className="text-sm text-muted-foreground">Thinking...</span>
              </div>
            </div>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>
      
      {/* Suggestions */}
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
      
      {/* Input */}
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
                "w-full bg-surface text-foreground rounded-xl px-4 py-3 pr-10 resize-none",
                "focus:outline-none focus:ring-2 focus:ring-primary/50 border border-border",
                "placeholder:text-muted-foreground"
              )}
              style={{ maxHeight: '100px' }}
            />
            <button
              onClick={toggleVoiceInput}
              className={cn(
                "absolute right-2 bottom-2.5 p-1.5 rounded-lg transition-colors",
                isListening 
                  ? 'bg-destructive text-destructive-foreground' 
                  : 'text-muted-foreground hover:text-foreground hover:bg-surface'
              )}
            >
              {isListening ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
            </button>
          </div>
          <Button
            onClick={sendMessage}
            disabled={!input.trim() || isLoading}
            size="icon"
          >
            <Send className="w-5 h-5" />
          </Button>
        </div>
        <p className="text-xs text-muted-foreground mt-2 text-center">
          Press Enter to send | Shift+Enter for new line
        </p>
      </div>
    </div>
  );
};

export default AICopilot;
