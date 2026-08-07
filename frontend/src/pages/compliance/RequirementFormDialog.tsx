import { useCallback, useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../../components/ui/Dialog'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Textarea } from '../../components/ui/Textarea'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../../components/ui/Select'
import { Checkbox } from '../../components/ui/Checkbox'
import { Label } from '../../components/ui/Label'
import {
  FormField,
  FormNotice,
  SubmitButton,
  UnsavedChangesDialog,
  useFormController,
  useUnsavedChangesGuard,
  type FieldSpecs,
} from '../../components/ui/form'
import { UserEmailSearch } from '../../components/UserEmailSearch'
import { complianceScheduleApi, getApiErrorMessage, type UserSearchResult } from '../../api/client'
import type {
  ComplianceRequirement,
  RequirementCreatePayload,
  RequirementUpdatePayload,
} from '../../api/complianceScheduleClient'
import { getCurrentUserId } from '../../utils/auth'
import { ownershipOf } from '../complianceScheduleHelpers'
import { useOwnershipLabel } from './useOwnershipLabel'
import { useTaxonomyOptions } from './useTaxonomyOptions'
import { RegulatoryBasisAssist } from './RegulatoryBasisAssist'
import { regulatoryBasisAssistCopy } from './regulatoryBasisAssistI18n'
import type { RegulatoryBasisCandidate } from './regulatoryBasisAssistMachine'

type FieldName =
  | 'title'
  | 'taxonomy_id'
  | 'next_due_date'
  | 'owner'
  | 'frequency_months'
  | 'frequency_days'

interface FormState {
  title: string
  taxonomy_id: string
  next_due_date: string
  description: string
  regulatory_basis: string
  regulatory_standard_id: number | null
  regulatory_clause_id: number | null
  frequency_months: string
  frequency_days: string
  anchor: 'completion' | 'schedule'
  statutory: boolean
}

const CONTROL_IDS: Record<FieldName, string> = {
  title: 'requirement-form-title',
  taxonomy_id: 'requirement-form-taxonomy',
  next_due_date: 'requirement-form-next-due',
  owner: 'requirement-form-owner',
  frequency_months: 'requirement-form-frequency-months',
  frequency_days: 'requirement-form-frequency-days',
}

function emptyState(): FormState {
  return {
    title: '',
    taxonomy_id: '',
    next_due_date: '',
    description: '',
    regulatory_basis: '',
    regulatory_standard_id: null,
    regulatory_clause_id: null,
    frequency_months: '',
    frequency_days: '',
    anchor: 'schedule',
    statutory: false,
  }
}

function stateFrom(requirement: ComplianceRequirement): FormState {
  return {
    title: requirement.title ?? '',
    taxonomy_id: requirement.taxonomy_id ?? '',
    next_due_date: requirement.next_due_date ?? '',
    description: requirement.description ?? '',
    regulatory_basis: requirement.regulatory_basis ?? '',
    regulatory_standard_id: requirement.regulatory_standard_id ?? null,
    regulatory_clause_id: requirement.regulatory_clause_id ?? null,
    frequency_months:
      requirement.frequency_months != null ? String(requirement.frequency_months) : '',
    frequency_days: requirement.frequency_days != null ? String(requirement.frequency_days) : '',
    anchor: requirement.anchor ?? 'schedule',
    statutory: Boolean(requirement.statutory),
  }
}

/**
 * A whole-number interval, or null when the box is empty.
 *
 * Returns `undefined` for anything that is neither, so the caller can tell
 * "nothing entered" from "entered something unusable" and reject the latter
 * rather than silently dropping it.
 */
export function parseInterval(raw: string): number | null | undefined {
  const trimmed = raw.trim()
  if (trimmed === '') return null
  if (!/^\d+$/.test(trimmed)) return undefined
  const n = Number(trimmed)
  return n >= 1 ? n : undefined
}

export interface RequirementFormDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  /** Omitted for a new obligation; supplied to edit an existing one. */
  requirement?: ComplianceRequirement | null
  onSaved: () => void
}

/**
 * Create or amend an obligation.
 *
 * One component covers both because the fields, their validation and their
 * payload shape are identical — the only differences are which endpoint runs and
 * whether untouched fields are sent at all. Splitting it would have meant two
 * copies of the same eleven-field form drifting apart.
 */
export function RequirementFormDialog({
  open,
  onOpenChange,
  requirement,
  onSaved,
}: RequirementFormDialogProps) {
  const { t } = useTranslation()
  const isEdit = Boolean(requirement)
  const currentUserId = useMemo(() => getCurrentUserId(), [])
  const ownershipLabel = useOwnershipLabel()
  const taxonomy = useTaxonomyOptions(open)

  const [form, setForm] = useState<FormState>(emptyState)
  const [ownerQuery, setOwnerQuery] = useState('')
  const [ownerUser, setOwnerUser] = useState<UserSearchResult | null>(null)
  const [dirty, setDirty] = useState(false)

  // Reopening must not show the last attempt's typing. RecordCompletionSheet
  // resets only one field on success, so a reopened sheet still carries the
  // previous timestamp; this form resets from the source of truth every time it
  // opens, which also covers edit-then-edit-a-different-row.
  useEffect(() => {
    if (!open) return
    setForm(requirement ? stateFrom(requirement) : emptyState())
    setOwnerQuery('')
    setOwnerUser(null)
    setDirty(false)
  }, [open, requirement])

  const update = useCallback((patch: Partial<FormState>) => {
    setForm((prev) => ({ ...prev, ...patch }))
    setDirty(true)
  }, [])

  /**
   * Ignore the empty value Radix reports when the current code has no matching
   * item mounted.
   *
   * The options arrive from a request that has not finished when the dialog
   * first renders, and Radix answers a controlled value it cannot find by
   * calling back with `""`. Accepting that would wipe the category off every
   * obligation the moment someone opened it to change the title. An empty
   * string is never a real choice either — Radix forbids `SelectItem value=""`
   * — so the only thing this discards is the reset.
   */
  const handleTaxonomyChange = useCallback(
    (value: string) => {
      if (value === '') return
      update({ taxonomy_id: value })
    },
    [update],
  )

  /**
   * Always offer the code the obligation already carries, even when the
   * category list no longer contains it. A category deactivated after the
   * obligation was filed would otherwise render as the placeholder, making a
   * filed obligation look unfiled.
   */
  const selectableTaxonomies = useMemo(() => {
    const current = form.taxonomy_id
    if (!current || taxonomy.options.some((o) => o.taxonomyId === current)) {
      return taxonomy.options
    }
    return [{ taxonomyId: current, name: '', sectionName: '' }, ...taxonomy.options]
  }, [form.taxonomy_id, taxonomy.options])

  const fields: FieldSpecs<FieldName> = useMemo(
    () => ({
      title: {
        label: t('compliance.schedule.form.title', 'Title'),
        required: true,
        validate: (value) =>
          String(value ?? '').trim().length > 255
            ? t('compliance.schedule.form.title_too_long', 'Title must be 255 characters or fewer')
            : null,
      },
      taxonomy_id: {
        label: t('compliance.schedule.form.taxonomy', 'Category'),
        required: true,
      },
      next_due_date: {
        label: t('compliance.schedule.form.next_due', 'Next due date'),
        required: true,
        validate: (value) =>
          Number.isNaN(new Date(String(value)).getTime())
            ? t('compliance.schedule.form.next_due_invalid', 'Enter a valid date')
            : null,
      },
      // Guards the one way this form can look like it worked and quietly not
      // have: typing an address without picking anyone leaves the obligation
      // unowned, and an unowned obligation notifies nobody.
      owner: {
        label: t('compliance.schedule.form.owner', 'Owner'),
        validate: (value) =>
          String(value ?? '').trim() !== '' && !ownerUser
            ? t(
                'compliance.schedule.form.owner_unselected',
                'Choose a person from the list so the reminder has somewhere to go',
              )
            : null,
      },
      frequency_months: {
        label: t('compliance.schedule.form.frequency_months', 'Every (months)'),
        validate: (value) =>
          parseInterval(String(value ?? '')) === undefined
            ? t('compliance.schedule.form.interval_invalid', 'Enter a whole number of 1 or more')
            : null,
      },
      frequency_days: {
        label: t('compliance.schedule.form.frequency_days', 'Every (days)'),
        validate: (value) =>
          parseInterval(String(value ?? '')) === undefined
            ? t('compliance.schedule.form.interval_invalid', 'Enter a whole number of 1 or more')
            : null,
      },
    }),
    [t, ownerUser],
  )

  const values = useMemo(
    () => ({
      title: form.title,
      taxonomy_id: form.taxonomy_id,
      next_due_date: form.next_due_date,
      owner: ownerQuery,
      frequency_months: form.frequency_months,
      frequency_days: form.frequency_days,
    }),
    [form, ownerQuery],
  )

  const close = useCallback(() => {
    setDirty(false)
    onOpenChange(false)
  }, [onOpenChange])

  const submit = useCallback(async () => {
    const months = parseInterval(form.frequency_months)
    const days = parseInterval(form.frequency_days)
    // Validation already rejects these, so reaching here means the guard above
    // it failed. Bailing rather than coercing keeps a malformed interval out of
    // the payload instead of silently sending null.
    if (months === undefined || days === undefined) return

    const shared = {
      title: form.title.trim(),
      taxonomy_id: form.taxonomy_id,
      next_due_date: form.next_due_date,
      description: form.description.trim() || null,
      regulatory_basis: form.regulatory_basis.trim() || null,
      regulatory_standard_id: form.regulatory_standard_id,
      regulatory_clause_id: form.regulatory_clause_id,
      frequency_months: months,
      frequency_days: days,
      anchor: form.anchor,
      statutory: form.statutory,
    }

    if (requirement) {
      const payload: RequirementUpdatePayload = { ...shared }
      // Omitted unless someone was actually picked. The route applies
      // exclude_unset, so sending owner_id only when it changed is what stops an
      // edit of the title from clearing the owner.
      if (ownerUser) payload.owner_id = ownerUser.id
      await complianceScheduleApi.updateRequirement(requirement.id, payload)
    } else {
      const payload: RequirementCreatePayload = {
        ...shared,
        // Same reasoning as activation: an obligation created with no owner
        // falls through to the admin role, and where nobody holds it the
        // reminder reaches no one. Whoever creates it is the safe default, and
        // the register shows who so it can be reassigned.
        owner_id: ownerUser?.id ?? currentUserId ?? null,
      }
      await complianceScheduleApi.createRequirement(payload)
    }

    onSaved()
    close()
  }, [form, ownerUser, currentUserId, requirement, onSaved, close])

  const controller = useFormController<FieldName>({
    fields,
    values,
    controlId: (name) => CONTROL_IDS[name],
    toErrorMessage: getApiErrorMessage,
    onSubmit: submit,
  })

  const guard = useUnsavedChangesGuard({ dirty, onDiscard: close })

  const ownerHint = isEdit
    ? t(
        'compliance.schedule.form.owner_hint_edit',
        'Currently {{owner}}. Leave blank to keep it unchanged.',
        { owner: ownershipLabel(ownershipOf(requirement?.owner_id, currentUserId)).toLowerCase() },
      )
    : t(
        'compliance.schedule.form.owner_hint_create',
        'Leave blank and this is assigned to you, so the reminder always reaches someone.',
      )

  return (
    <>
      <Dialog open={open} onOpenChange={guard.handleOpenChange}>
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>
              {isEdit
                ? t('compliance.schedule.form.edit_title', 'Edit obligation')
                : t('compliance.schedule.form.create_title', 'Add obligation')}
            </DialogTitle>
            <DialogDescription>
              {isEdit
                ? t(
                    'compliance.schedule.form.edit_description',
                    'Changing the next due date re-opens reminders for this obligation.',
                  )
                : t(
                    'compliance.schedule.form.create_description',
                    'For an obligation the catalogue does not cover. Reminders begin from the due date you set.',
                  )}
            </DialogDescription>
          </DialogHeader>

          <form {...controller.formProps} className="space-y-5">
            {controller.submitError ? (
              <FormNotice tone="error" data-testid="requirement-form-error">
                {controller.submitError}
              </FormNotice>
            ) : null}

            <FormField {...controller.fieldProps('title')}>
              {(control) => (
                <Input
                  {...control}
                  type="text"
                  value={form.title}
                  onChange={(e) => update({ title: e.target.value })}
                  error={Boolean(controller.errors.title)}
                  data-testid="requirement-form-title-input"
                />
              )}
            </FormField>

            <FormField
              {...controller.fieldProps('taxonomy_id')}
              nativeControl={false}
              hint={
                taxonomy.failed
                  ? t(
                      'compliance.schedule.form.taxonomy_failed',
                      'The category list could not be loaded, so this obligation cannot be filed yet.',
                    )
                  : undefined
              }
            >
              {(control) => (
                <Select
                  value={form.taxonomy_id}
                  onValueChange={handleTaxonomyChange}
                  disabled={taxonomy.loading || taxonomy.failed}
                >
                  <SelectTrigger {...control} data-testid="requirement-form-taxonomy-trigger">
                    <SelectValue
                      placeholder={
                        taxonomy.loading
                          ? t('common.loading', 'Loading…')
                          : t('compliance.schedule.form.taxonomy_placeholder', 'Choose a category')
                      }
                    />
                  </SelectTrigger>
                  <SelectContent>
                    {selectableTaxonomies.map((option) => (
                      <SelectItem key={option.taxonomyId} value={option.taxonomyId}>
                        {option.taxonomyId}
                        {option.name ? ` — ${option.name}` : ''}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            </FormField>

            <FormField {...controller.fieldProps('next_due_date')}>
              {(control) => (
                <Input
                  {...control}
                  type="date"
                  value={form.next_due_date}
                  onChange={(e) => update({ next_due_date: e.target.value })}
                  error={Boolean(controller.errors.next_due_date)}
                  data-testid="requirement-form-next-due-input"
                />
              )}
            </FormField>

            <div data-testid="requirement-form-owner-block">
              <UserEmailSearch
                label={t('compliance.schedule.form.owner', 'Owner')}
                value={ownerQuery}
                placeholder={t(
                  'compliance.schedule.form.owner_placeholder',
                  'Search by name or email…',
                )}
                onChange={(email, user) => {
                  setOwnerQuery(email)
                  setOwnerUser(user ?? null)
                  setDirty(true)
                }}
              />
              <p className="mt-1 text-xs text-muted-foreground">{ownerHint}</p>
              {controller.errors.owner ? (
                <p
                  role="alert"
                  data-testid="requirement-form-owner-error"
                  className="mt-1 text-sm text-destructive"
                >
                  {controller.errors.owner}
                </p>
              ) : null}
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <FormField
                {...controller.fieldProps('frequency_months')}
                hint={t(
                  'compliance.schedule.form.frequency_hint',
                  'Both may be set; they are added together.',
                )}
              >
                {(control) => (
                  <Input
                    {...control}
                    type="number"
                    min={1}
                    step={1}
                    value={form.frequency_months}
                    onChange={(e) => update({ frequency_months: e.target.value })}
                    error={Boolean(controller.errors.frequency_months)}
                    data-testid="requirement-form-months-input"
                  />
                )}
              </FormField>

              <FormField {...controller.fieldProps('frequency_days')}>
                {(control) => (
                  <Input
                    {...control}
                    type="number"
                    min={1}
                    step={1}
                    value={form.frequency_days}
                    onChange={(e) => update({ frequency_days: e.target.value })}
                    error={Boolean(controller.errors.frequency_days)}
                    data-testid="requirement-form-days-input"
                  />
                )}
              </FormField>
            </div>

            <FormField
              id="requirement-form-anchor"
              label={t('compliance.schedule.anchor', 'Anchor')}
              nativeControl={false}
              hint={
                form.anchor === 'completion'
                  ? t(
                      'compliance.schedule.anchor.completion_hint',
                      'The next date is measured from the day the work is done, so completing late pushes the schedule back.',
                    )
                  : t(
                      'compliance.schedule.anchor.schedule_hint',
                      'The next date is measured from the current due date, so the anniversary holds even if the work is done late.',
                    )
              }
            >
              {(control) => (
                <Select
                  value={form.anchor}
                  onValueChange={(value) =>
                    update({ anchor: value as 'completion' | 'schedule' })
                  }
                >
                  <SelectTrigger {...control} data-testid="requirement-form-anchor-trigger">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="schedule">
                      {t('compliance.schedule.anchor.schedule', 'Fixed schedule')}
                    </SelectItem>
                    <SelectItem value="completion">
                      {t('compliance.schedule.anchor.completion', 'From completion')}
                    </SelectItem>
                  </SelectContent>
                </Select>
              )}
            </FormField>

            <div className="flex items-start gap-2">
              <Checkbox
                id="requirement-form-statutory"
                checked={form.statutory}
                onCheckedChange={(checked) => update({ statutory: checked === true })}
                data-testid="requirement-form-statutory"
              />
              <div>
                <Label htmlFor="requirement-form-statutory" className="text-sm font-medium">
                  {t('compliance.schedule.form.statutory', 'Required by law')}
                </Label>
                <p className="text-xs text-muted-foreground">
                  {t(
                    'compliance.schedule.form.statutory_hint',
                    'Statutory obligations are reminded earlier and escalate further.',
                  )}
                </p>
              </div>
            </div>

            <FormField
              id="requirement-form-regulatory-basis"
              label={t('compliance.schedule.regulatory_basis', 'Regulatory basis')}
            >
              {(control) => (
                <div className="space-y-2">
                  <Input
                    {...control}
                    type="text"
                    value={form.regulatory_basis}
                    onChange={(e) =>
                      update({
                        regulatory_basis: e.target.value,
                        // Hand-editing must clear the structured link or text and FK disagree.
                        regulatory_standard_id: null,
                        regulatory_clause_id: null,
                      })
                    }
                    placeholder={t(
                      'compliance.schedule.form.regulatory_basis_placeholder',
                      'e.g. Regulatory Reform (Fire Safety) Order 2005',
                    )}
                    data-testid="requirement-form-basis-input"
                  />
                  {form.regulatory_standard_id != null ? (
                    <div
                      className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground"
                      data-testid="requirement-form-basis-link-chip"
                    >
                      <span>
                        {t(
                          'compliance.schedule.regulatory_ai.linked',
                          regulatoryBasisAssistCopy.linkedChip,
                        )}{' '}
                        #{form.regulatory_standard_id}
                        {form.regulatory_clause_id != null
                          ? ` / clause #${form.regulatory_clause_id}`
                          : ''}
                      </span>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="h-7 px-2"
                        onClick={() =>
                          update({
                            regulatory_standard_id: null,
                            regulatory_clause_id: null,
                          })
                        }
                        data-testid="requirement-form-basis-unlink"
                      >
                        {t(
                          'compliance.schedule.regulatory_ai.remove_link',
                          regulatoryBasisAssistCopy.removeLink,
                        )}
                      </Button>
                    </div>
                  ) : null}
                  <RegulatoryBasisAssist
                    title={form.title}
                    taxonomyId={form.taxonomy_id}
                    description={form.description}
                    statutory={form.statutory}
                    requirementId={requirement?.id}
                    onAccept={(candidate: RegulatoryBasisCandidate) =>
                      update({
                        regulatory_basis: candidate.label.slice(0, 255),
                        regulatory_standard_id: candidate.standard_id ?? null,
                        regulatory_clause_id: candidate.clause_ids[0] ?? null,
                      })
                    }
                  />
                </div>
              )}
            </FormField>

            <FormField
              id="requirement-form-description"
              label={t('compliance.schedule.form.description', 'Description')}
            >
              {(control) => (
                <Textarea
                  {...control}
                  rows={3}
                  value={form.description}
                  onChange={(e) => update({ description: e.target.value })}
                  data-testid="requirement-form-description-input"
                />
              )}
            </FormField>

            <DialogFooter className="gap-3 pt-2">
              <Button type="button" variant="outline" onClick={guard.requestClose}>
                {t('common.cancel', 'Cancel')}
              </Button>
              <SubmitButton
                submitting={controller.submitting}
                submittingLabel={t('common.saving', 'Saving…')}
                disabled={taxonomy.failed}
                data-testid="requirement-form-submit"
              >
                {isEdit
                  ? t('compliance.schedule.form.save', 'Save changes')
                  : t('compliance.schedule.form.create', 'Add obligation')}
              </SubmitButton>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
      <UnsavedChangesDialog
        guard={guard}
        title={t('form.unsaved.title', 'Discard unsaved changes?')}
        description={t(
          'form.unsaved.description',
          'This form has changes that have not been saved. Closing it now will lose them.',
        )}
        keepEditingLabel={t('form.unsaved.keep_editing', 'Keep editing')}
        discardLabel={t('form.unsaved.discard', 'Discard changes')}
        data-testid="requirement-form-unsaved"
      />
    </>
  )
}
