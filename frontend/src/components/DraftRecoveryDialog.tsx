/**
 * DraftRecoveryDialog - Prompt to recover a saved form draft
 * 
 * Part of EXP-001: Autosave + Draft Recovery for Portal Forms
 */

import { Clock, FileText, RotateCcw, Trash2 } from 'lucide-react';
import { Button } from './ui/Button';
import { cn } from '../helpers/utils';

interface DraftRecoveryDialogProps {
  isOpen: boolean;
  formType: string;
  savedAt: string;
  stepNumber: number;
  totalSteps: number;
  onRecover: () => void;
  onDiscard: () => void;
}

/**
 * Format relative time (e.g., "5 minutes ago", "2 hours ago")
 */
function formatRelativeTime(dateString: string): string {
  try {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    
    if (diffMins < 1) return 'just now';
    if (diffMins === 1) return '1 minute ago';
    if (diffMins < 60) return `${diffMins} minutes ago`;
    if (diffHours === 1) return '1 hour ago';
    if (diffHours < 24) return `${diffHours} hours ago`;
    return 'yesterday';
  } catch {
    return 'recently';
  }
}

/**
 * Format form type for display
 */
function formatFormType(formType: string): string {
  const typeMap: Record<string, string> = {
    'incident': 'Incident Report',
    'near-miss': 'Near Miss Report',
    'complaint': 'Customer Complaint',
    'rta': 'RTA Report',
  };
  return typeMap[formType] || 'Form';
}

export function DraftRecoveryDialog({
  isOpen,
  formType,
  savedAt,
  stepNumber,
  totalSteps,
  onRecover,
  onDiscard,
}: DraftRecoveryDialogProps) {
  if (!isOpen) return null;
  
  const relativeTime = formatRelativeTime(savedAt);
  const formName = formatFormType(formType);
  
  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-4">
      {/* Backdrop */}
      <div 
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onDiscard}
      />
      
      {/* Dialog */}
      <div className={cn(
        'relative w-full max-w-md bg-card rounded-2xl shadow-2xl',
        'animate-in slide-in-from-bottom-4 duration-300'
      )}>
        {/* Header */}
        <div className="p-6 pb-4">
          <div className="flex items-start gap-4">
            <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center flex-shrink-0">
              <FileText className="w-6 h-6 text-primary" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-foreground">
                Resume your {formName}?
              </h2>
              <p className="text-sm text-muted-foreground mt-1">
                You have an unsaved draft from {relativeTime}
              </p>
            </div>
          </div>
        </div>
        
        {/* Progress info */}
        <div className="px-6 pb-4">
          <div className="flex items-center gap-3 p-3 bg-surface rounded-xl">
            <Clock className="w-5 h-5 text-muted-foreground" />
            <div className="flex-1">
              <div className="text-sm font-medium text-foreground">
                Step {stepNumber} of {totalSteps}
              </div>
              <div className="text-xs text-muted-foreground">
                Your progress was automatically saved
              </div>
            </div>
            <div className="text-right">
              <div className="text-lg font-semibold text-primary">
                {Math.round((stepNumber / totalSteps) * 100)}%
              </div>
            </div>
          </div>
        </div>
        
        {/* Actions */}
        <div className="p-6 pt-2 space-y-3">
          <Button
            onClick={onRecover}
            className="w-full"
            data-testid="draft-recover-btn"
          >
            <RotateCcw className="w-4 h-4 mr-2" />
            Resume Draft
          </Button>
          
          <Button
            variant="outline"
            onClick={onDiscard}
            className="w-full"
            data-testid="draft-discard-btn"
          >
            <Trash2 className="w-4 h-4 mr-2" />
            Start Fresh
          </Button>
        </div>
        
        {/* Footer note */}
        <div className="px-6 pb-6">
          <p className="text-xs text-center text-muted-foreground">
            Drafts are automatically saved and expire after 24 hours
          </p>
        </div>
      </div>
    </div>
  );
}

export default DraftRecoveryDialog;
