/**
 * Add a certificate to the compliance expiry register.
 *
 * One component serves both places the register is read — the Monitoring
 * Certificates tab and the assurance certificate shelf — because both need the
 * same eight fields writing to the same endpoint. Two copies would have drifted,
 * and the register only has one writer to drift away from.
 *
 * `entity_id` is deliberately absent from the form. It is a scoping key inside
 * the tenant, and for an organisation-level accreditation there is no row to
 * point at; the server supplies the tenant's own id. Asking an operator to type
 * a machine key to file an ISO certificate would be the wrong question.
 */

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
  useFormController,
  type FieldSpecs,
} from '../../components/ui/form'
import { complianceAutomationApi, getApiErrorMessage } from '../../api/client'

type FieldName = 'name' | 'certificate_type' | 'entity_type' | 'issue_date' | 'expiry_date'

const CONTROL_IDS: Record<FieldName, string> = {
  name: 'certificate-form-name',
  certificate_type: 'certificate-form-type',
  entity_type: 'certificate-form-entity-type',
  issue_date: 'certificate-form-issue-date',
  expiry_date: 'certificate-form-expiry-date',
}

/**
 * `entity_type` values already in use on this column. `organization` matches the
 * spelling the compliance-automation module uses for its own organisation scope,
 * so the two cannot disagree; the visible labels are British.
 */
const ENTITY_TYPES = ['organization', 'user', 'equipment', 'location'] as const

interface FormState {
  name: string
  certificate_type: string
  entity_type: string
  entity_name: string
  reference_number: string
  issuing_body: string
  issue_date: string
  expiry_date: string
  is_critical: boolean
  notes: string
}

function emptyState(): FormState {
  return {
    name: '',
    certificate_type: '',
    entity_type: 'organization',
    entity_name: '',
    reference_number: '',
    issuing_body: '',
    issue_date: '',
    expiry_date: '',
    is_critical: false,
    notes: '',
  }
}

function isValidDate(value: string): boolean {
  return value.trim() !== '' && !Number.isNaN(new Date(value).getTime())
}

export interface CertificateFormDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  /** Called after the certificate is filed, so the host can reload its own view. */
  onSaved: () => void
}

export function CertificateFormDialog({ open, onOpenChange, onSaved }: CertificateFormDialogProps) {
  const { t } = useTranslation()
  const [form, setForm] = useState<FormState>(emptyState)

  // Reopening must not show the previous attempt's typing, including after a
  // submit that failed and left the dialog open.
  useEffect(() => {
    if (!open) return
    setForm(emptyState())
  }, [open])

  const update = useCallback((patch: Partial<FormState>) => {
    setForm((prev) => ({ ...prev, ...patch }))
  }, [])

  const entityTypeLabels: Record<string, string> = useMemo(
    () => ({
      organization: t('compliance.automation.certificate_form.entity_organisation', 'Organisation'),
      user: t('compliance.automation.certificate_form.entity_user', 'Person'),
      equipment: t('compliance.automation.certificate_form.entity_equipment', 'Equipment'),
      location: t('compliance.automation.certificate_form.entity_location', 'Location'),
    }),
    [t],
  )

  const fields: FieldSpecs<FieldName> = useMemo(
    () => ({
      name: {
        label: t('compliance.automation.certificate_form.name', 'Certificate name'),
        required: true,
        validate: (value) =>
          String(value ?? '').trim().length > 255
            ? t(
                'compliance.automation.certificate_form.name_too_long',
                'Certificate name must be 255 characters or fewer',
              )
            : null,
      },
      certificate_type: {
        label: t('compliance.automation.certificate_form.type', 'Certificate type'),
        required: true,
        validate: (value) =>
          String(value ?? '').trim().length > 50
            ? t(
                'compliance.automation.certificate_form.type_too_long',
                'Certificate type must be 50 characters or fewer',
              )
            : null,
      },
      entity_type: {
        label: t('compliance.automation.certificate_form.entity_type', 'Applies to'),
        required: true,
      },
      issue_date: {
        label: t('compliance.automation.certificate_form.issue_date', 'Issue date'),
        required: true,
        validate: (value) =>
          isValidDate(String(value ?? ''))
            ? null
            : t('compliance.automation.certificate_form.date_invalid', 'Enter a valid date'),
      },
      // The countdown the register feeds is driven entirely by this date, so an
      // expiry before the issue date is rejected here as well as by the API —
      // the operator should not have to submit to find out.
      expiry_date: {
        label: t('compliance.automation.certificate_form.expiry_date', 'Expiry date'),
        required: true,
        validate: (value) => {
          const raw = String(value ?? '')
          if (!isValidDate(raw)) {
            return t('compliance.automation.certificate_form.date_invalid', 'Enter a valid date')
          }
          if (isValidDate(form.issue_date) && new Date(raw) < new Date(form.issue_date)) {
            return t(
              'compliance.automation.certificate_form.expiry_before_issue',
              'Expiry date cannot be earlier than the issue date',
            )
          }
          return null
        },
      },
    }),
    [t, form.issue_date],
  )

  const values = useMemo(
    () => ({
      name: form.name,
      certificate_type: form.certificate_type,
      entity_type: form.entity_type,
      issue_date: form.issue_date,
      expiry_date: form.expiry_date,
    }),
    [form],
  )

  const submit = useCallback(async () => {
    await complianceAutomationApi.addCertificate({
      name: form.name.trim(),
      certificate_type: form.certificate_type.trim(),
      entity_type: form.entity_type,
      issue_date: form.issue_date,
      expiry_date: form.expiry_date,
      // Omitted rather than sent empty: the body forbids unknown fields and an
      // empty string is not the same claim as "not recorded".
      ...(form.entity_name.trim() ? { entity_name: form.entity_name.trim() } : {}),
      ...(form.reference_number.trim() ? { reference_number: form.reference_number.trim() } : {}),
      ...(form.issuing_body.trim() ? { issuing_body: form.issuing_body.trim() } : {}),
      ...(form.notes.trim() ? { notes: form.notes.trim() } : {}),
      is_critical: form.is_critical,
    })
    onSaved()
    onOpenChange(false)
  }, [form, onSaved, onOpenChange])

  const controller = useFormController<FieldName>({
    fields,
    values,
    controlId: (name) => CONTROL_IDS[name],
    toErrorMessage: getApiErrorMessage,
    onSubmit: submit,
  })

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="max-h-[90vh] overflow-y-auto sm:max-w-2xl"
        data-testid="certificate-form-dialog"
      >
        <DialogHeader>
          <DialogTitle>
            {t('compliance.automation.certificate_form.title', 'Add certificate')}
          </DialogTitle>
          <DialogDescription>
            {t(
              'compliance.automation.certificate_form.description',
              'Files a certificate on the compliance expiry register. The expiry date drives the register countdown and the framework countdown on the standards matrix.',
            )}
          </DialogDescription>
        </DialogHeader>

        <form {...controller.formProps} className="space-y-5">
          {controller.submitError ? (
            <FormNotice tone="error" data-testid="certificate-form-error">
              {controller.submitError}
            </FormNotice>
          ) : null}

          <FormField {...controller.fieldProps('name')}>
            {(control) => (
              <Input
                {...control}
                type="text"
                value={form.name}
                onChange={(e) => update({ name: e.target.value })}
                error={Boolean(controller.errors.name)}
                placeholder={t(
                  'compliance.automation.certificate_form.name_placeholder',
                  'e.g. ISO 9001:2015 Certificate',
                )}
                data-testid="certificate-form-name-input"
              />
            )}
          </FormField>

          <FormField
            {...controller.fieldProps('certificate_type')}
            hint={t(
              'compliance.automation.certificate_form.type_hint',
              'Name the standard here or in the certificate name (e.g. ISO 9001) and the certificate counts towards that framework column. A PAT or insurance certificate counts towards none, on purpose.',
            )}
          >
            {(control) => (
              <Input
                {...control}
                type="text"
                value={form.certificate_type}
                onChange={(e) => update({ certificate_type: e.target.value })}
                error={Boolean(controller.errors.certificate_type)}
                placeholder={t(
                  'compliance.automation.certificate_form.type_placeholder',
                  'e.g. iso9001, training, equipment',
                )}
                data-testid="certificate-form-type-input"
              />
            )}
          </FormField>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <FormField {...controller.fieldProps('issue_date')}>
              {(control) => (
                <Input
                  {...control}
                  type="date"
                  value={form.issue_date}
                  onChange={(e) => update({ issue_date: e.target.value })}
                  error={Boolean(controller.errors.issue_date)}
                  data-testid="certificate-form-issue-date-input"
                />
              )}
            </FormField>

            <FormField {...controller.fieldProps('expiry_date')}>
              {(control) => (
                <Input
                  {...control}
                  type="date"
                  value={form.expiry_date}
                  onChange={(e) => update({ expiry_date: e.target.value })}
                  error={Boolean(controller.errors.expiry_date)}
                  data-testid="certificate-form-expiry-date-input"
                />
              )}
            </FormField>
          </div>

          <FormField {...controller.fieldProps('entity_type')} nativeControl={false}>
            {(control) => (
              <Select
                value={form.entity_type}
                onValueChange={(value) => {
                  if (value === '') return
                  update({ entity_type: value })
                }}
              >
                <SelectTrigger {...control} data-testid="certificate-form-entity-type-trigger">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ENTITY_TYPES.map((entityType) => (
                    <SelectItem key={entityType} value={entityType}>
                      {entityTypeLabels[entityType]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          </FormField>

          <FormField
            id="certificate-form-entity-name"
            label={t('compliance.automation.certificate_form.entity_name', 'Applies to (name)')}
          >
            {(control) => (
              <Input
                {...control}
                type="text"
                value={form.entity_name}
                onChange={(e) => update({ entity_name: e.target.value })}
                data-testid="certificate-form-entity-name-input"
              />
            )}
          </FormField>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <FormField
              id="certificate-form-issuing-body"
              label={t('compliance.automation.certificate_form.issuing_body', 'Issuing body')}
            >
              {(control) => (
                <Input
                  {...control}
                  type="text"
                  value={form.issuing_body}
                  onChange={(e) => update({ issuing_body: e.target.value })}
                  data-testid="certificate-form-issuing-body-input"
                />
              )}
            </FormField>

            <FormField
              id="certificate-form-reference"
              label={t(
                'compliance.automation.certificate_form.reference_number',
                'Certificate number',
              )}
            >
              {(control) => (
                <Input
                  {...control}
                  type="text"
                  value={form.reference_number}
                  onChange={(e) => update({ reference_number: e.target.value })}
                  data-testid="certificate-form-reference-input"
                />
              )}
            </FormField>
          </div>

          <div className="flex items-start gap-2">
            <Checkbox
              id="certificate-form-critical"
              checked={form.is_critical}
              onCheckedChange={(checked) => update({ is_critical: checked === true })}
              data-testid="certificate-form-critical"
            />
            <div>
              <Label htmlFor="certificate-form-critical" className="text-sm font-medium">
                {t('compliance.automation.certificate_form.is_critical', 'Critical certificate')}
              </Label>
              <p className="text-xs text-muted-foreground">
                {t(
                  'compliance.automation.certificate_form.is_critical_hint',
                  'Marks the certificate as critical on the register and the shelf.',
                )}
              </p>
            </div>
          </div>

          <FormField
            id="certificate-form-notes"
            label={t('compliance.automation.certificate_form.notes', 'Notes')}
          >
            {(control) => (
              <Textarea
                {...control}
                rows={3}
                value={form.notes}
                onChange={(e) => update({ notes: e.target.value })}
                data-testid="certificate-form-notes-input"
              />
            )}
          </FormField>

          <DialogFooter className="gap-3 pt-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              data-testid="certificate-form-cancel"
            >
              {t('common.cancel', 'Cancel')}
            </Button>
            <SubmitButton
              submitting={controller.submitting}
              submittingLabel={t('common.saving', 'Saving…')}
              data-testid="certificate-form-submit"
            >
              {t('compliance.automation.certificate_form.submit', 'Add certificate')}
            </SubmitButton>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
