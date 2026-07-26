/**
 * Shared form primitive.
 *
 * One place that owns required-field marking (visual *and* programmatic),
 * field-adjacent error messages, focus/scroll to the first invalid control,
 * in-flight submit state, persistent failure messages, and the unsaved-work
 * guard. Adopted by the non-portal forms; designed so the portal intake forms
 * can adopt it without changing this API.
 */

export { FormField } from './FormField'
export type { FormFieldProps, FormControlProps } from './FormField'
export { FormNotice } from './FormNotice'
export type { FormNoticeProps, FormNoticeTone } from './FormNotice'
export { SubmitButton } from './SubmitButton'
export type { SubmitButtonProps } from './SubmitButton'
export { useFormController } from './useFormController'
export type {
  FormController,
  FormFieldBinding,
  UseFormControllerOptions,
} from './useFormController'
export { useUnsavedChangesGuard } from './useUnsavedChangesGuard'
export type { UnsavedChangesGuard, UseUnsavedChangesGuardOptions } from './useUnsavedChangesGuard'
export { UnsavedChangesDialog } from './UnsavedChangesDialog'
export type { UnsavedChangesDialogProps } from './UnsavedChangesDialog'
export {
  defaultRequiredMessage,
  fieldErrorId,
  fieldHintId,
  focusInvalidControl,
  isBlankValue,
  validateFields,
} from './formValidation'
export type { FieldSpec, FieldSpecs, ValidationOutcome } from './formValidation'
