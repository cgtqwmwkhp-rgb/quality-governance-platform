import { useId } from 'react'
import { useTranslation } from 'react-i18next'
import { Plus, Trash2, Users } from 'lucide-react'
import type { Witness } from '../../api/client'
import { Button } from '../ui/Button'
import { Card, CardContent, CardHeader, CardTitle } from '../ui/Card'
import { EmptyState } from '../ui/EmptyState'
import { Input } from '../ui/Input'
import { Label } from '../ui/Label'
import { Switch } from '../ui/Switch'
import { Textarea } from '../ui/Textarea'

/** Mirrors the persisted `witnesses_structured` shape used by RTA (and generalized here). */
export interface CaseWitnessesValue {
  witnesses?: Witness[]
}

export interface CaseWitnessesPanelProps {
  value: CaseWitnessesValue | null | undefined
  onChange: (value: CaseWitnessesValue) => void
  readOnly?: boolean
  title?: string
  className?: string
  /** Optional test id prefix, e.g. "incident" → incident-witnesses-panel */
  testIdPrefix?: string
}

const displayValue = (value: string | undefined, fallback: string) =>
  value && value.trim().length > 0 ? value : fallback

/**
 * Structured witnesses editor shared across incident / near-miss / complaint / RTA cases.
 * Fully controlled (value + onChange) so callers own persistence; readOnly renders a
 * plain summary view instead of form controls.
 */
export function CaseWitnessesPanel({
  value,
  onChange,
  readOnly = false,
  title,
  className,
  testIdPrefix,
}: CaseWitnessesPanelProps) {
  const { t } = useTranslation()
  const baseId = useId()
  const witnesses = value?.witnesses ?? []
  const panelId = testIdPrefix ? `${testIdPrefix}-witnesses-panel` : undefined
  const notProvided = t('case.witnesses.not_provided', 'Not provided')

  const updateWitness = (index: number, patch: Partial<Witness>) => {
    onChange({ witnesses: witnesses.map((w, i) => (i === index ? { ...w, ...patch } : w)) })
  }

  const addWitness = () => {
    onChange({ witnesses: [...witnesses, {}] })
  }

  const removeWitness = (index: number) => {
    onChange({ witnesses: witnesses.filter((_, i) => i !== index) })
  }

  const fieldId = (index: number, field: string) => `${baseId}-witness-${index}-${field}`

  const addButton = (extraProps?: { size?: 'sm' | 'default' }) => (
    <Button
      type="button"
      variant="outline"
      size={extraProps?.size ?? 'sm'}
      onClick={addWitness}
      data-testid={testIdPrefix ? `${testIdPrefix}-witnesses-add` : undefined}
    >
      <Plus className="w-4 h-4 mr-1" aria-hidden="true" />
      {t('case.witnesses.add', 'Add witness')}
    </Button>
  )

  return (
    <Card data-testid={panelId} className={className}>
      <CardHeader className="flex flex-row items-center justify-between gap-3 space-y-0">
        <CardTitle className="flex items-center gap-2">
          <Users className="w-5 h-5 text-primary" aria-hidden="true" />
          {title ?? t('case.witnesses.title', 'Witnesses')}
          <span className="text-sm font-normal text-muted-foreground">
            {t('case.witnesses.count', {
              count: witnesses.length,
              defaultValue: `${witnesses.length} recorded`,
            })}
          </span>
        </CardTitle>
        {!readOnly && witnesses.length > 0 ? addButton() : null}
      </CardHeader>
      <CardContent className="space-y-4">
        {witnesses.length === 0 ? (
          <EmptyState
            icon={<Users className="w-8 h-8 text-muted-foreground" aria-hidden="true" />}
            title={t('case.witnesses.empty_title', 'No witnesses recorded')}
            description={
              readOnly
                ? t(
                    'case.witnesses.empty_description_readonly',
                    'No witness details have been captured for this case.',
                  )
                : t(
                    'case.witnesses.empty_description',
                    'Add a witness to capture their contact details and statement.',
                  )
            }
            action={!readOnly ? addButton({ size: 'default' }) : undefined}
          />
        ) : (
          <div className="space-y-3">
            {witnesses.map((witness, index) => (
              <div
                key={index}
                className="rounded-lg border border-border bg-muted/30 p-4 space-y-3"
                data-testid={testIdPrefix ? `${testIdPrefix}-witness-${index}` : undefined}
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                    {t('case.witnesses.witness_number', {
                      number: index + 1,
                      defaultValue: `Witness ${index + 1}`,
                    })}
                  </span>
                  {!readOnly ? (
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="h-6 px-2 text-xs text-destructive"
                      onClick={() => removeWitness(index)}
                    >
                      <Trash2 className="w-3 h-3 mr-1" aria-hidden="true" />
                      {t('case.witnesses.remove', 'Remove')}
                    </Button>
                  ) : null}
                </div>

                {readOnly ? (
                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                    <ReadOnlyField label={t('case.witnesses.name_label', 'Name')} value={displayValue(witness.name, notProvided)} />
                    <ReadOnlyField label={t('case.witnesses.phone_label', 'Phone')} value={displayValue(witness.phone, notProvided)} />
                    {witness.email ? (
                      <ReadOnlyField label={t('case.witnesses.email_label', 'Email')} value={witness.email} />
                    ) : null}
                    <ReadOnlyField
                      label={t('case.witnesses.consent_label', 'Willing to provide a written statement')}
                      value={
                        witness.willing_to_provide_statement
                          ? t('case.witnesses.consent_yes', 'Yes')
                          : t('case.witnesses.consent_no', 'No')
                      }
                    />
                    {witness.statement ? (
                      <div className="col-span-full">
                        <ReadOnlyField label={t('case.witnesses.statement_label', 'Statement')} value={witness.statement} multiline />
                      </div>
                    ) : null}
                  </div>
                ) : (
                  <>
                    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                      <div>
                        <Label htmlFor={fieldId(index, 'name')} className="mb-1 block text-xs text-muted-foreground">
                          {t('case.witnesses.name_label', 'Name')}
                        </Label>
                        <Input
                          id={fieldId(index, 'name')}
                          value={witness.name ?? ''}
                          onChange={(e) => updateWitness(index, { name: e.target.value })}
                          placeholder={t('case.witnesses.name_placeholder', 'Full name')}
                        />
                      </div>
                      <div>
                        <Label htmlFor={fieldId(index, 'phone')} className="mb-1 block text-xs text-muted-foreground">
                          {t('case.witnesses.phone_label', 'Phone')}
                        </Label>
                        <Input
                          id={fieldId(index, 'phone')}
                          value={witness.phone ?? ''}
                          onChange={(e) => updateWitness(index, { phone: e.target.value })}
                          placeholder={t('case.witnesses.phone_placeholder', '07xxx xxxxxx')}
                        />
                      </div>
                      <div>
                        <Label htmlFor={fieldId(index, 'email')} className="mb-1 block text-xs text-muted-foreground">
                          {t('case.witnesses.email_label', 'Email')}
                        </Label>
                        <Input
                          id={fieldId(index, 'email')}
                          type="email"
                          value={witness.email ?? ''}
                          onChange={(e) => updateWitness(index, { email: e.target.value })}
                          placeholder={t('case.witnesses.email_placeholder', 'name@example.com')}
                        />
                      </div>
                      <div className="flex items-center gap-2 pt-5">
                        <Switch
                          id={fieldId(index, 'consent')}
                          checked={witness.willing_to_provide_statement ?? false}
                          onCheckedChange={(checked) =>
                            updateWitness(index, { willing_to_provide_statement: checked })
                          }
                        />
                        <Label htmlFor={fieldId(index, 'consent')} className="text-sm">
                          {t('case.witnesses.consent_label', 'Willing to provide a written statement')}
                        </Label>
                      </div>
                    </div>
                    <div>
                      <Label htmlFor={fieldId(index, 'statement')} className="mb-1 block text-xs text-muted-foreground">
                        {t('case.witnesses.statement_label', 'Statement')}
                      </Label>
                      <Textarea
                        id={fieldId(index, 'statement')}
                        value={witness.statement ?? ''}
                        onChange={(e) => updateWitness(index, { statement: e.target.value })}
                        rows={3}
                        placeholder={t('case.witnesses.statement_placeholder', 'Witness account of events')}
                      />
                    </div>
                  </>
                )}
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function ReadOnlyField({
  label,
  value,
  multiline = false,
}: {
  label: string
  value: string
  multiline?: boolean
}) {
  return (
    <div>
      <p className="text-xs font-medium text-muted-foreground">{label}</p>
      <p className={multiline ? 'whitespace-pre-wrap text-sm text-foreground' : 'text-sm text-foreground'}>
        {value}
      </p>
    </div>
  )
}
