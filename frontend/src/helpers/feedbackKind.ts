/** Customer Feedback kinds. API vocabulary stays `complaint`; this is the discriminator. */

export type FeedbackKindCode = 'complaint' | 'compliment' | 'suggestion' | 'general'

export const FEEDBACK_KIND_OPTIONS: { value: FeedbackKindCode; label: string }[] = [
  { value: 'complaint', label: 'Complaint' },
  { value: 'compliment', label: 'Compliment' },
  { value: 'suggestion', label: 'Suggestion' },
  { value: 'general', label: 'General feedback' },
]

const LIGHT_CLOSE: ReadonlySet<FeedbackKindCode> = new Set(['compliment', 'general'])

export function parseFeedbackKind(value: string | undefined | null): FeedbackKindCode {
  if (value === 'compliment' || value === 'suggestion' || value === 'general' || value === 'complaint') {
    return value
  }
  return 'complaint'
}

export function reopenStatusForKind(kind: string | undefined | null): string {
  return LIGHT_CLOSE.has(parseFeedbackKind(kind)) ? 'acknowledged' : 'under_investigation'
}

export function lessonsRequiredForKind(kind: string | undefined | null): boolean {
  return !LIGHT_CLOSE.has(parseFeedbackKind(kind))
}

export function statusOptionsForKind(kind: string | undefined | null): string[] {
  switch (parseFeedbackKind(kind)) {
    case 'compliment':
      return ['received', 'acknowledged', 'closed']
    case 'general':
      return ['received', 'acknowledged', 'closed']
    case 'suggestion':
      return ['received', 'acknowledged', 'under_investigation', 'escalated', 'closed']
    default:
      return [
        'received',
        'acknowledged',
        'under_investigation',
        'pending_response',
        'awaiting_customer',
        'escalated',
        'resolved',
        'closed',
      ]
  }
}
