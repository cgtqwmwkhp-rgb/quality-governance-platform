import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '../AlertDialog'
import { Button } from '../Button'
import type { UnsavedChangesGuard } from './useUnsavedChangesGuard'

export interface UnsavedChangesDialogProps {
  guard: UnsavedChangesGuard
  title?: string
  description?: string
  keepEditingLabel?: string
  discardLabel?: string
  'data-testid'?: string
}

/** Confirmation shown by {@link useUnsavedChangesGuard} before typed work is dropped. */
export function UnsavedChangesDialog({
  guard,
  title = 'Discard unsaved changes?',
  description = 'This form has changes that have not been saved. Closing it now will lose them.',
  keepEditingLabel = 'Keep editing',
  discardLabel = 'Discard changes',
  'data-testid': testId = 'unsaved-changes-dialog',
}: UnsavedChangesDialogProps) {
  return (
    <AlertDialog open={guard.confirmOpen} onOpenChange={(open) => !open && guard.keepEditing()}>
      <AlertDialogContent className="max-w-md" data-testid={testId}>
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          <AlertDialogDescription>{description}</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter className="gap-2 sm:gap-0">
          <Button
            type="button"
            variant="outline"
            onClick={guard.keepEditing}
            data-testid={`${testId}-keep`}
          >
            {keepEditingLabel}
          </Button>
          <Button
            type="button"
            variant="destructive"
            onClick={guard.confirmDiscard}
            data-testid={`${testId}-discard`}
          >
            {discardLabel}
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
