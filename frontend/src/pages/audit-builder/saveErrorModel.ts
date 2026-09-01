/**
 * Structured save/publish error model for Audit Template Builder.
 * Parses FastAPI/axios 422 detail arrays and string messages into actionable issues.
 */
import {
  TIMEOUT_STATUS_CODES,
  classifyWriteTimeoutDisposition,
  isTimeoutOrAbortError,
} from '../../api/timeoutClassification'

export interface SaveIssue {
  id: string
  field: string | null
  label: string
  action: string
  locPath?: string
  raw: string
  questionId?: string
  /** e.g. section title + question text so the user knows which question failed */
  context?: string
}

export interface SaveIssueModel {
  summary: string
  issues: SaveIssue[]
  /** Transport timeout rather than anything the author can fix by editing. */
  isTimeout?: boolean
  /** Timed-out write: the server may still have committed it. Reconcile, don't re-enter. */
  maybeCommitted?: boolean
}

export interface SaveIssueContext {
  questionId?: string
  sectionTitle?: string
  questionText?: string
  /**
   * How far the save had got when it failed, e.g. "6 of 19 questions saved".
   * Used for timeouts, where "which field is wrong" is the wrong question.
   */
  progress?: string
  /** Distinguishes publish 422s so the banner does not say “Couldn’t save”. */
  operation?: 'save' | 'publish'
}

type FieldGuidance = { label: string; action: string }

const FIELD_GUIDANCE: Record<string, FieldGuidance> = {
  risk_category: {
    label: 'Risk level on a question',
    action:
      'Open the highlighted question and check Risk level / criticality, then save again.',
  },
  risk_weight: {
    label: 'Risk weight on a question',
    action: 'Adjust the question’s risk weight, then save again.',
  },
  question_text: {
    label: 'Question text',
    action: 'Enter question text (required), then save again.',
  },
  question_type: {
    label: 'Question type',
    action: 'Pick a supported question type, then save again.',
  },
  criticality: {
    label: 'Criticality',
    action: 'Choose Essential, Required, or Nice to have, then save again.',
  },
  positive_answer: {
    label: 'Positive answer polarity',
    action: 'Set positive answer to Yes or No, then save again.',
  },
  evidence_requirements: {
    label: 'Evidence requirements',
    action: 'Review evidence settings on the question, then save again.',
  },
  conditional_logic: {
    label: 'Conditional logic',
    action: 'Check conditional logic rules (source question and operator), then save again.',
  },
  options: {
    label: 'Answer options',
    action: 'Ensure every option has a label and value, then save again.',
  },
  weight: {
    label: 'Question weight',
    action: 'Set a weight greater than zero, then save again.',
  },
  name: {
    label: 'Template name',
    action: 'Enter a template name, then save again.',
  },
  title: {
    label: 'Section title',
    action: 'Enter a section title, then save again.',
  },
  is_required: {
    label: 'Required flag',
    action: 'Toggle whether the question is required, then save again.',
  },
  allow_na: {
    label: 'Allow N/A',
    action: 'Adjust the Allow N/A setting, then save again.',
  },
  sort_order: {
    label: 'Sort order',
    action: 'Reorder the question or section, then save again.',
  },
}

const EXTRA_FORBIDDEN_RE =
  /extra inputs? are not permitted|extra.?forbid|forbidden/i

function lastLocSegment(loc: unknown): string | null {
  if (!Array.isArray(loc) || loc.length === 0) return null
  const last = loc[loc.length - 1]
  return typeof last === 'string' || typeof last === 'number' ? String(last) : null
}

function formatLocPath(loc: unknown): string | undefined {
  if (!Array.isArray(loc) || loc.length === 0) return undefined
  return loc.map(String).join(' -> ')
}

function guidanceForField(field: string | null): FieldGuidance {
  if (field && FIELD_GUIDANCE[field]) return FIELD_GUIDANCE[field]
  if (field) {
    return {
      label: field.replace(/_/g, ' '),
      action: `Fix the “${field.replace(/_/g, ' ')}” field, then save again.`,
    }
  }
  return {
    label: 'Request failed',
    action: '',
  }
}

function buildContext(ctx?: SaveIssueContext): string | undefined {
  if (!ctx) return undefined
  const section = ctx.sectionTitle?.trim()
  const text = ctx.questionText?.trim() || 'Untitled question'
  if (section) return `${section}: ${text}`
  if (ctx.questionText !== undefined) return text
  return undefined
}

function enrichIssue(issue: SaveIssue, ctx?: SaveIssueContext): SaveIssue {
  if (!ctx) return issue
  return {
    ...issue,
    questionId: issue.questionId ?? ctx.questionId,
    context: issue.context ?? buildContext(ctx),
  }
}

/** Parse `body -> risk_category: Extra inputs are not permitted` style strings. */
export function parseFieldPathMessage(message: string): {
  field: string | null
  locPath?: string
  msg: string
} {
  const trimmed = message.trim()
  // FastAPI / Pydantic style: "body -> risk_category: Extra inputs are not permitted"
  const arrowMatch = trimmed.match(
    /^(?:body\s*->\s*)?([A-Za-z_][\w.]*(?:\s*->\s*[A-Za-z_][\w.]*)*)\s*:\s*(.+)$/s,
  )
  if (arrowMatch) {
    const path = arrowMatch[1].replace(/\s*->\s*/g, ' -> ')
    const segments = path.split(/\s*->\s*/)
    const field = segments[segments.length - 1] || null
    return { field, locPath: path.includes(' -> ') ? path : `body -> ${field}`, msg: arrowMatch[2].trim() }
  }
  // loc as dotted path prefix: "body.risk_category: ..."
  const dotMatch = trimmed.match(/^body\.([A-Za-z_][\w.]*)\s*:\s*(.+)$/s)
  if (dotMatch) {
    const field = dotMatch[1].split('.').pop() || null
    return { field, locPath: `body -> ${dotMatch[1].replace(/\./g, ' -> ')}`, msg: dotMatch[2].trim() }
  }
  return { field: null, msg: trimmed }
}

function issueFromParts(
  raw: string,
  field: string | null,
  locPath: string | undefined,
  index: number,
  ctx?: SaveIssueContext,
): SaveIssue {
  const guidance = guidanceForField(field)
  let action = guidance.action
  let label = guidance.label
  if (!field) {
    label = ctx?.operation === 'publish' ? 'Couldn’t publish' : 'Couldn’t save'
    action = raw.trim() || 'The server rejected this request. See the details below.'
  } else if (EXTRA_FORBIDDEN_RE.test(raw)) {
    action =
      FIELD_GUIDANCE[field]?.action ??
      `The server rejected “${field}” as an unsupported field on this request. Clear or adjust it, then save again — or update the API schema if this field should be allowed.`
  }
  return enrichIssue(
    {
      id: `issue-${index}-${field ?? 'general'}`,
      field,
      label,
      action,
      locPath,
      raw,
    },
    ctx,
  )
}

type DetailItem = {
  loc?: unknown
  msg?: unknown
  message?: unknown
  type?: unknown
  input?: unknown
}

function issuesFromDetailArray(detail: unknown[], ctx?: SaveIssueContext): SaveIssue[] {
  return detail.map((item, index) => {
    if (typeof item === 'string') {
      const parsed = parseFieldPathMessage(item)
      return issueFromParts(item, parsed.field, parsed.locPath, index, ctx)
    }
    if (item && typeof item === 'object') {
      const row = item as DetailItem
      const msg =
        (typeof row.msg === 'string' && row.msg) ||
        (typeof row.message === 'string' && row.message) ||
        JSON.stringify(item)
      const field = lastLocSegment(row.loc)
      const locPath = formatLocPath(row.loc)
      const raw =
        locPath && field ? `${locPath}: ${msg}` : typeof row.msg === 'string' ? msg : String(msg)
      return issueFromParts(raw, field, locPath, index, ctx)
    }
    const raw = String(item)
    return issueFromParts(raw, null, undefined, index, ctx)
  })
}

function normalizeQgpFieldErrors(errors: unknown[]): unknown[] {
  return errors.map((item) => {
    if (!item || typeof item !== 'object') return item
    const row = item as { field?: unknown; message?: unknown; msg?: unknown; loc?: unknown; type?: unknown }
    if (Array.isArray(row.loc)) return item
    const field = typeof row.field === 'string' ? row.field : ''
    return {
      loc: field ? field.split(/\s*->\s*/) : undefined,
      msg: typeof row.message === 'string' ? row.message : row.msg,
      type: row.type,
    }
  })
}

function extractDetail(error: unknown): unknown {
  if (!error || typeof error !== 'object') return undefined
  const maybeAxios = error as {
    response?: {
      data?: {
        detail?: unknown
        message?: unknown
        error?: { message?: unknown; details?: unknown }
      }
    }
    message?: string
  }
  const data = maybeAxios.response?.data
  if (data && typeof data === 'object') {
    if ('detail' in data && data.detail !== undefined) return data.detail
    const nested = data.error
    if (nested && typeof nested === 'object' && nested !== null) {
      const details = nested.details
      if (details && typeof details === 'object' && details !== null) {
        const errors = (details as { errors?: unknown }).errors
        if (Array.isArray(errors) && errors.length > 0) {
          return { message: nested.message, errors: normalizeQgpFieldErrors(errors) }
        }
      }
      if (typeof nested.message === 'string' && nested.message.trim()) return nested.message
    }
    if (typeof data.message === 'string') return data.message
  }
  if (error instanceof Error) return error.message
  if (typeof maybeAxios.message === 'string') return maybeAxios.message
  return undefined
}

function summarize(issues: SaveIssue[], operation?: 'save' | 'publish'): string {
  const verb = operation === 'publish' ? 'publish' : 'save'
  if (issues.length === 0) return `${verb === 'publish' ? 'Publish' : 'Save'} failed. Please try again.`
  if (issues.length === 1) {
    const only = issues[0]
    if (!only.field) {
      return only.raw.trim() || only.action
    }
    const where = only.context ? ` (${only.context})` : ''
    return `Couldn’t ${verb}: ${only.label}${where}. ${only.action}`
  }
  return `Couldn’t ${verb} — fix ${issues.length} issues, then try again.`
}

type TimeoutShapedError = {
  code?: string
  message?: string
  name?: string
  isTimeout?: boolean
  maybeCommitted?: boolean
  classifiedMessage?: string
  config?: { method?: string }
  response?: { status?: number }
}

export interface SaveTimeoutClassification {
  isTimeout: boolean
  /** True when the request that timed out may still have been committed server-side. */
  maybeCommitted: boolean
}

const NOT_A_TIMEOUT: SaveTimeoutClassification = { isTimeout: false, maybeCommitted: false }

/**
 * Decide whether a save failure is a transport/gateway timeout.
 *
 * Trusts the flags the axios response interceptor already stamped on the error
 * (`isTimeout` / `maybeCommitted`) and falls back to the raw axios shape so this
 * still classifies correctly for errors raised outside that interceptor.
 */
export function classifySaveTimeout(error: unknown): SaveTimeoutClassification {
  if (!error || typeof error !== 'object') return NOT_A_TIMEOUT
  const candidate = error as TimeoutShapedError
  const method = candidate.config?.method
  const writeMayHaveLanded = () =>
    classifyWriteTimeoutDisposition({ code: 'ECONNABORTED' }, method) === 'maybe_committed'

  if (candidate.isTimeout === true) {
    return {
      isTimeout: true,
      maybeCommitted: candidate.maybeCommitted ?? writeMayHaveLanded(),
    }
  }

  const status = candidate.response?.status
  if (status !== undefined) {
    // A response came back: only the server's own timeout statuses count. Anything
    // else (422, 500, …) is a real answer and must keep its validation/server copy.
    if (TIMEOUT_STATUS_CODES.has(status)) {
      return { isTimeout: true, maybeCommitted: writeMayHaveLanded() }
    }
    return NOT_A_TIMEOUT
  }

  if (
    isTimeoutOrAbortError({
      code: candidate.code,
      message: candidate.message ?? candidate.classifiedMessage,
      name: candidate.name,
    })
  ) {
    return { isTimeout: true, maybeCommitted: writeMayHaveLanded() }
  }
  return NOT_A_TIMEOUT
}

function timeoutRaw(error: unknown): string {
  const candidate = (error ?? {}) as TimeoutShapedError
  const raw = candidate.message || candidate.classifiedMessage
  return typeof raw === 'string' && raw.trim() ? raw : 'Request timed out'
}

function timeoutIssueModel(
  error: unknown,
  classification: SaveTimeoutClassification,
  ctx?: SaveIssueContext,
): SaveIssueModel {
  const progress = ctx?.progress?.trim()
  const where = progress ? ` (${progress})` : ''
  const action = classification.maybeCommitted
    ? 'Some of your changes may already have been saved. Reload this template to see what saved before you try again — re-entering the changes now could duplicate them.'
    : 'The request timed out before the server answered. Check your connection, then save again.'
  const summary = classification.maybeCommitted
    ? `Save timed out${where}. Some changes may already have been saved — reload this template to check before saving again.`
    : `Save timed out${where}. Check your connection, then save again.`

  return {
    summary,
    // No questionId: a timeout is not a fault in any one question, and offering
    // "Show question" would frame it as something to fix by editing.
    issues: [
      {
        id: 'issue-timeout',
        field: null,
        label: 'Save timed out',
        action,
        raw: timeoutRaw(error),
        context: progress,
      },
    ],
    isTimeout: true,
    maybeCommitted: classification.maybeCommitted,
  }
}

/**
 * Build a structured save-issue model from an axios/FastAPI (or generic) error.
 */
export function buildSaveIssueModel(error: unknown, ctx?: SaveIssueContext): SaveIssueModel {
  const timeout = classifySaveTimeout(error)
  if (timeout.isTimeout) return timeoutIssueModel(error, timeout, ctx)

  const detail = extractDetail(error)

  let issues: SaveIssue[] = []
  if (Array.isArray(detail)) {
    issues = issuesFromDetailArray(detail, ctx)
  } else if (detail && typeof detail === 'object') {
    // Nested: { message, errors: [...] } or { msg, loc }
    const obj = detail as Record<string, unknown>
    if (Array.isArray(obj.errors)) {
      issues = issuesFromDetailArray(obj.errors, ctx)
    } else if (typeof obj.msg === 'string' || typeof obj.message === 'string') {
      issues = issuesFromDetailArray([obj], ctx)
    } else {
      const raw = JSON.stringify(detail)
      issues = [issueFromParts(raw, null, undefined, 0, ctx)]
    }
  } else if (typeof detail === 'string' && detail.trim()) {
    const parsed = parseFieldPathMessage(detail)
    issues = [issueFromParts(detail, parsed.field, parsed.locPath, 0, ctx)]
  } else {
    const fallback =
      error instanceof Error && error.message
        ? error.message
        : 'An unexpected error occurred while saving.'
    issues = [issueFromParts(fallback, null, undefined, 0, ctx)]
  }

  return { summary: summarize(issues, ctx?.operation), issues }
}

/**
 * Map client-side publish validation strings into the same issue shape
 * so SaveIssueBanner is the single blocker UX.
 */
export function fromPublishValidationErrors(
  publishErrors: string[],
  options?: {
    questionErrors?: Record<string, string[]>
    firstQuestionId?: string
  },
): SaveIssueModel {
  const questionIds = options?.questionErrors ? Object.keys(options.questionErrors) : []
  const issues: SaveIssue[] = publishErrors.map((raw, index) => {
    const questionId =
      options?.firstQuestionId ??
      (questionIds.length === 1 ? questionIds[0] : questionIds[index]) ??
      undefined
    // Heuristic field hints from common validation copy
    let field: string | null = null
    if (/question text/i.test(raw)) field = 'question_text'
    else if (/weight/i.test(raw)) field = 'weight'
    else if (/option/i.test(raw)) field = 'options'
    else if (/template name/i.test(raw)) field = 'name'
    else if (/section title/i.test(raw)) field = 'title'
    else if (/not publishable|question type/i.test(raw)) field = 'question_type'

    const guidance = guidanceForField(field)
    return {
      id: `publish-${index}-${field ?? 'validation'}`,
      field,
      label: field ? guidance.label : 'Publish validation',
      action: field
        ? guidance.action.replace(/save again/gi, 'fix it before publishing')
        : raw,
      raw,
      questionId,
      context: !field ? raw : undefined,
    }
  })

  const summary =
    issues.length === 0
      ? 'Fix validation issues before publishing.'
      : issues.length === 1
        ? issues[0].raw
        : `Fix ${issues.length} validation issues before publishing.`

  return { summary, issues }
}

/** First question id referenced by issues, if any. */
export function firstIssueQuestionId(model: SaveIssueModel): string | undefined {
  return model.issues.find((i) => i.questionId)?.questionId
}
