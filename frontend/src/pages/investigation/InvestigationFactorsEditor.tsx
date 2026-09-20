/**
 * The ICAM contributing-factors picker and list (INV-C12 / DEC-1).
 *
 * Replaces the single contributing-factors textarea on the RCA tab. An
 * investigator picks one of the four ICAM categories, names the factor, adds
 * any sub-causes, and states its HSG245 causal depth; the paragraph the
 * generated pack and the closure gate still read is derived server-side from
 * these factors, so there is nothing to keep in step here.
 *
 * Presentational on purpose, following `InvestigationFindingsEditor`: it owns
 * the draft of the factor being added or edited and nothing else. Every
 * mutation is handed up to `InvestigationDetail`, which calls the API and
 * passes the server's ordered list back down — so the grouping shown is always
 * the grouping stored, never an optimistic guess a failed request would leave
 * on screen.
 *
 * Copy is plain English rather than i18n keys: this component only ever loads
 * on the lazy InvestigationDetail chunk, and locale keys are shell weight
 * (INV-C10's 212 kB gzip ceiling).
 */

import { useEffect, useState } from 'react'
import { Check, Loader2, Pencil, Plus, Trash2, X } from 'lucide-react'
import { Button } from '../../components/ui/Button'
import { Textarea } from '../../components/ui/Textarea'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../../components/ui/Select'
import type { InvestigationFactor, InvestigationFactorInput } from './investigationDetailApi'
import { CAUSAL_DEPTHS, ICAM_CATEGORIES, depthLabel } from './icamFactors'

export interface InvestigationFactorsEditorProps {
  factors: InvestigationFactor[]
  loading: boolean
  /** Set while any mutation is in flight; every control is disabled meanwhile. */
  saving: boolean
  error: string | null
  /** Causes stored under a category this screen does not classify (pre-DEC-1). */
  unmappedCategories: string[]
  unreadableTotal: number
  readOnly?: boolean
  onAdd: (factor: InvestigationFactorInput) => Promise<void>
  onUpdate: (factorId: number, changes: Partial<InvestigationFactorInput>) => Promise<void>
  onDelete: (factorId: number) => Promise<void>
  onRetry: () => void
}

/** Sub-causes are one per line in the box, and blank lines are not sub-causes. */
function splitSubCauses(text: string): string[] {
  return text
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
}

export default function InvestigationFactorsEditor({
  factors,
  loading,
  saving,
  error,
  unmappedCategories,
  unreadableTotal,
  readOnly = false,
  onAdd,
  onUpdate,
  onDelete,
  onRetry,
}: InvestigationFactorsEditorProps) {
  const [draftCategory, setDraftCategory] = useState('')
  const [draftCause, setDraftCause] = useState('')
  const [draftSubCauses, setDraftSubCauses] = useState('')
  const [draftDepth, setDraftDepth] = useState('')

  const [editingId, setEditingId] = useState<number | null>(null)
  const [editCause, setEditCause] = useState('')
  const [editSubCauses, setEditSubCauses] = useState('')
  const [editCategory, setEditCategory] = useState('')
  const [editDepth, setEditDepth] = useState('')

  // A factor deleted in another tab must not leave this one editing a row that
  // is no longer in the list, with a save button that can only 404.
  useEffect(() => {
    if (editingId !== null && !factors.some((factor) => factor.id === editingId)) {
      setEditingId(null)
    }
  }, [factors, editingId])

  const busy = saving || loading
  // Category, text and depth are all required: DEC-1 is ICAM crossed with
  // HSG245 depth, and a default for either would be this screen making the
  // investigator's judgement for them.
  const canAdd =
    !busy && !readOnly && Boolean(draftCategory) && Boolean(draftDepth) && draftCause.trim().length > 0

  const handleAdd = async () => {
    if (!canAdd) return
    await onAdd({
      category: draftCategory,
      cause: draftCause.trim(),
      sub_causes: splitSubCauses(draftSubCauses),
      depth: draftDepth,
    })
    // Cleared only after the call resolves, so a failed add does not lose the text.
    setDraftCause('')
    setDraftSubCauses('')
  }

  const startEditing = (factor: InvestigationFactor) => {
    setEditingId(factor.id)
    setEditCategory(factor.category)
    setEditCause(factor.cause)
    setEditSubCauses(factor.sub_causes.join('\n'))
    setEditDepth(factor.depth || '')
  }

  const handleSaveEdit = async (factorId: number) => {
    const cause = editCause.trim()
    if (!cause) return
    await onUpdate(factorId, {
      category: editCategory,
      cause,
      sub_causes: splitSubCauses(editSubCauses),
      // Explicit null is how the API is told to clear a depth; an omitted key
      // would leave the stored one in place.
      depth: editDepth || null,
    })
    setEditingId(null)
  }

  const grouped = ICAM_CATEGORIES.map((category) => ({
    category,
    rows: factors.filter((factor) => factor.category === category.value),
  })).filter((group) => group.rows.length > 0)

  return (
    <div className="space-y-4" data-testid="investigation-factors-list">
      {error ? (
        <div className="flex items-center justify-between gap-3" role="alert">
          <p className="text-sm text-destructive" data-testid="investigation-factors-error">
            {error}
          </p>
          <Button size="sm" variant="outline" onClick={onRetry} data-testid="investigation-factors-retry">
            Try again
          </Button>
        </div>
      ) : null}

      {loading ? (
        <p className="text-sm text-muted-foreground" data-testid="investigation-factors-loading">
          <Loader2 className="inline w-4 h-4 mr-2 animate-spin" />
          Loading contributing factors…
        </p>
      ) : null}

      {!loading && factors.length === 0 && !error ? (
        <p className="text-sm text-muted-foreground" data-testid="investigation-factors-empty">
          No contributing factors recorded yet. Pick an ICAM category and name one — nothing is
          filled in for you.
        </p>
      ) : null}

      {unreadableTotal > 0 ? (
        <p className="text-sm text-muted-foreground" data-testid="investigation-factors-unmapped">
          {unreadableTotal} stored cause{unreadableTotal === 1 ? '' : 's'} on this investigation
          {unmappedCategories.length
            ? ` sit under ${unmappedCategories.join(', ')}, which is not an ICAM category`
            : ' could not be read'}
          , so {unreadableTotal === 1 ? 'it is' : 'they are'} not listed here. Nothing has been
          deleted or re-categorised.
        </p>
      ) : null}

      {grouped.map(({ category, rows }) => (
        <section key={category.value} data-testid={`investigation-factor-group-${category.value}`}>
          <h4 className="text-sm font-semibold text-foreground">{category.label}</h4>
          <ul className="mt-2 space-y-3">
            {rows.map((factor) => (
              <li
                key={factor.id}
                className="rounded-md border border-border p-3"
                data-testid={`investigation-factor-${factor.id}`}
              >
                {editingId === factor.id ? (
                  <div className="space-y-2">
                    <label htmlFor={`inv-factor-edit-category-${factor.id}`} className="sr-only">
                      ICAM category
                    </label>
                    <Select value={editCategory} onValueChange={setEditCategory}>
                      <SelectTrigger
                        id={`inv-factor-edit-category-${factor.id}`}
                        data-testid={`investigation-factor-edit-category-${factor.id}`}
                      >
                        <SelectValue placeholder="ICAM category" />
                      </SelectTrigger>
                      <SelectContent>
                        {ICAM_CATEGORIES.map((option) => (
                          <SelectItem key={option.value} value={option.value}>
                            {option.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <label htmlFor={`inv-factor-edit-cause-${factor.id}`} className="sr-only">
                      Contributing factor
                    </label>
                    <Textarea
                      id={`inv-factor-edit-cause-${factor.id}`}
                      rows={2}
                      value={editCause}
                      onChange={(event) => setEditCause(event.target.value)}
                      data-testid={`investigation-factor-edit-cause-input-${factor.id}`}
                    />
                    <label htmlFor={`inv-factor-edit-subs-${factor.id}`} className="sr-only">
                      Sub-causes, one per line
                    </label>
                    <Textarea
                      id={`inv-factor-edit-subs-${factor.id}`}
                      rows={2}
                      placeholder="Sub-causes, one per line. Optional."
                      value={editSubCauses}
                      onChange={(event) => setEditSubCauses(event.target.value)}
                      data-testid={`investigation-factor-edit-subs-input-${factor.id}`}
                    />
                    <label htmlFor={`inv-factor-edit-depth-${factor.id}`} className="sr-only">
                      Causal depth
                    </label>
                    <Select value={editDepth} onValueChange={setEditDepth}>
                      <SelectTrigger
                        id={`inv-factor-edit-depth-${factor.id}`}
                        data-testid={`investigation-factor-edit-depth-${factor.id}`}
                      >
                        <SelectValue placeholder="Causal depth (HSG245)" />
                      </SelectTrigger>
                      <SelectContent>
                        {CAUSAL_DEPTHS.map((option) => (
                          <SelectItem key={option.value} value={option.value}>
                            {option.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        disabled={busy || editCause.trim().length === 0}
                        onClick={() => void handleSaveEdit(factor.id)}
                        data-testid={`investigation-factor-save-${factor.id}`}
                      >
                        <Check className="w-4 h-4 mr-1" />
                        Save
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={busy}
                        onClick={() => setEditingId(null)}
                        data-testid={`investigation-factor-cancel-${factor.id}`}
                      >
                        <X className="w-4 h-4 mr-1" />
                        Cancel
                      </Button>
                    </div>
                  </div>
                ) : (
                  <div className="flex items-start justify-between gap-3">
                    <div className="space-y-1">
                      <p
                        className="text-sm text-foreground whitespace-pre-wrap"
                        data-testid={`investigation-factor-cause-${factor.id}`}
                      >
                        {factor.cause}
                      </p>
                      {factor.sub_causes.length ? (
                        <ul
                          className="ml-4 list-disc text-sm text-muted-foreground"
                          data-testid={`investigation-factor-subs-${factor.id}`}
                        >
                          {factor.sub_causes.map((sub) => (
                            <li key={sub}>{sub}</li>
                          ))}
                        </ul>
                      ) : null}
                      <p
                        className="text-xs text-muted-foreground"
                        data-testid={`investigation-factor-depth-${factor.id}`}
                      >
                        {depthLabel(factor.depth)}
                      </p>
                    </div>
                    {readOnly ? null : (
                      <div className="flex shrink-0 gap-1">
                        <Button
                          size="sm"
                          variant="ghost"
                          aria-label={`Edit contributing factor: ${factor.cause}`}
                          disabled={busy}
                          onClick={() => startEditing(factor)}
                          data-testid={`investigation-factor-edit-${factor.id}`}
                        >
                          <Pencil className="w-4 h-4" />
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          aria-label={`Delete contributing factor: ${factor.cause}`}
                          disabled={busy}
                          onClick={() => void onDelete(factor.id)}
                          data-testid={`investigation-factor-delete-${factor.id}`}
                        >
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      </div>
                    )}
                  </div>
                )}
              </li>
            ))}
          </ul>
        </section>
      ))}

      {readOnly ? null : (
        <div className="space-y-2 border-t border-border pt-4">
          <label htmlFor="inv-factor-new-category" className="block text-sm font-medium text-foreground">
            ICAM category
          </label>
          <Select value={draftCategory} onValueChange={setDraftCategory}>
            <SelectTrigger id="inv-factor-new-category" data-testid="investigation-factor-new-category">
              <SelectValue placeholder="Choose a category" />
            </SelectTrigger>
            <SelectContent>
              {ICAM_CATEGORIES.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {draftCategory ? (
            <p className="text-xs text-muted-foreground" data-testid="investigation-factor-category-hint">
              {ICAM_CATEGORIES.find((option) => option.value === draftCategory)?.hint}
            </p>
          ) : null}

          <label htmlFor="inv-factor-new-cause" className="block text-sm font-medium text-foreground">
            Contributing factor
          </label>
          <Textarea
            id="inv-factor-new-cause"
            rows={2}
            placeholder="Name one factor. It is stored exactly as you write it."
            value={draftCause}
            onChange={(event) => setDraftCause(event.target.value)}
            data-testid="investigation-factor-new-cause"
          />

          <label htmlFor="inv-factor-new-subs" className="block text-sm font-medium text-muted-foreground">
            Sub-causes
          </label>
          <Textarea
            id="inv-factor-new-subs"
            rows={2}
            placeholder="One per line. Optional — leave empty when there are none."
            value={draftSubCauses}
            onChange={(event) => setDraftSubCauses(event.target.value)}
            data-testid="investigation-factor-new-subs"
          />

          <label htmlFor="inv-factor-new-depth" className="block text-sm font-medium text-foreground">
            Causal depth (HSG245)
          </label>
          <Select value={draftDepth} onValueChange={setDraftDepth}>
            <SelectTrigger id="inv-factor-new-depth" data-testid="investigation-factor-new-depth">
              <SelectValue placeholder="Choose a depth" />
            </SelectTrigger>
            <SelectContent>
              {CAUSAL_DEPTHS.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {draftDepth ? (
            <p className="text-xs text-muted-foreground" data-testid="investigation-factor-depth-hint">
              {CAUSAL_DEPTHS.find((option) => option.value === draftDepth)?.hint}
            </p>
          ) : null}

          <Button
            size="sm"
            disabled={!canAdd}
            onClick={() => void handleAdd()}
            data-testid="investigation-factor-add"
          >
            {saving ? (
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <Plus className="w-4 h-4 mr-2" />
            )}
            Add contributing factor
          </Button>
        </div>
      )}
    </div>
  )
}
