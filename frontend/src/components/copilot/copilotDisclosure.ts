/**
 * What the copilot panel is allowed to say it is, given what this deployment has on.
 *
 * The panel used to state "Demonstration only — no AI model is involved" in every
 * environment, because the only signal it had was a build-time flag baked into a
 * static bundle. Once `AI_COPILOT_INFERENCE_ENABLED` existed that sentence became
 * false wherever it mattered: a model really does phrase those answers, over facts
 * this platform computed from the caller's own registers. A disclosure that is wrong
 * in the direction of "we are only pretending" is still wrong.
 *
 * The two runtime flags come from `GET /api/v1/meta/features`, which folds the same
 * configuration and the same kill switch the copilot routes themselves read.
 *
 * Which way the defaults lean
 * ---------------------------
 * Every unknown resolves to the *smaller* claim. Flags arrive asynchronously and
 * default false, so the first render of a grounded deployment briefly describes a
 * simulator. Understating what the surface does is a wording bug; overstating it is
 * the defect this module exists to remove, so the asymmetry is deliberate.
 */

export type CopilotDisclosureMode = 'unavailable' | 'simulated' | 'grounded'

export interface CopilotDisclosureBanner {
  testId: string
  /** Emphasised opening claim. */
  lead: string
  /** The limits that make the lead honest. */
  detail: string
  /** `warning` for a surface whose output must not be relied on; `info` otherwise. */
  tone: 'warning' | 'info'
}

export interface CopilotDisclosure {
  mode: CopilotDisclosureMode
  title: string
  subtitle: string
  /** null when a separate alert already carries the whole disclosure. */
  banner: CopilotDisclosureBanner | null
  welcome: string
  inputPlaceholder: string
  /** Shown against an action the server reports it did not perform. */
  actionNotPerformed: string
}

export interface CopilotRuntimeState {
  /** The API has answered 404: closed by configuration or by the kill switch. */
  unavailable: boolean
  /** `ai_copilot` — the surface is open in this deployment. */
  copilotOpen: boolean
  /** `ai_copilot_inference` — grounded answers over register facts are on. */
  inferenceOpen: boolean
}

/**
 * An observed 404 outranks both flags: it is the endpoint's own answer, while the
 * flags are a cached read that can be up to a minute stale.
 */
export function resolveCopilotDisclosureMode({
  unavailable,
  copilotOpen,
  inferenceOpen,
}: CopilotRuntimeState): CopilotDisclosureMode {
  if (unavailable) return 'unavailable'
  if (copilotOpen && inferenceOpen) return 'grounded'
  return 'simulated'
}

const UNAVAILABLE: CopilotDisclosure = {
  mode: 'unavailable',
  title: 'AI Copilot',
  subtitle: 'Not enabled here',
  // The unavailable alert states this already; a second banner would only repeat it.
  banner: null,
  welcome: '',
  inputPlaceholder: 'Copilot unavailable',
  actionNotPerformed: 'Not performed — the copilot is not enabled here',
}

const SIMULATED: CopilotDisclosure = {
  mode: 'simulated',
  title: 'AI Copilot (Demo)',
  subtitle: 'Simulated — not live data',
  banner: {
    testId: 'ai-copilot-demo-banner',
    lead: 'Demonstration only — no AI model is involved.',
    detail:
      'Replies are fixed keyword responses. Live-data questions are refused. Writes are never performed. Do not quote this surface as organisational truth.',
    tone: 'warning',
  },
  welcome: `This is a demonstration of a planned AI assistant. It is not connected to any AI model or to your organisation's records.\n\nI will **refuse** live-data questions (compliance status, risk summaries) and will **not** claim to create incidents or actions. Concept explanations (for example CAPA or RIDDOR) are general guidance only.\n\nTry "what is CAPA" for a concept preview, or open Compliance / Risk Register for real figures.`,
  inputPlaceholder: 'Ask me anything...',
  actionNotPerformed: 'Not performed — demo cannot write or read live registers',
}

const GROUNDED: CopilotDisclosure = {
  mode: 'grounded',
  title: 'AI Copilot',
  subtitle: 'Live register facts — fixed question set',
  banner: {
    testId: 'ai-copilot-grounded-banner',
    lead: 'Answers come from your own register records, not from open chat.',
    // Every clause here is a property the server enforces, not a promise about
    // model behaviour: the intent set is closed, figures and reference numbers are
    // validated against the computed facts, and the copilot has no write path.
    detail:
      'A fixed set of questions is answered by AI wording figures this platform computed from your registers, and every reference number and figure it quotes must appear in those facts — anything else is refused rather than guessed. Records are never created, edited or deleted.',
    tone: 'info',
  },
  welcome: `I answer a fixed set of questions from your organisation's own registers — for example incident, near-miss and complaint counts, overdue actions, and compliance obligations.\n\nAnswers are worded by an AI model over figures this platform computed, and every reference number or figure I quote has to appear in those figures. Anything outside that set I will **refuse** rather than guess, and I **never** create, edit or delete records.\n\nTry "how many incidents do we have" or "which actions are overdue".`,
  inputPlaceholder: 'Ask about your registers...',
  actionNotPerformed: 'Not performed — the copilot never writes to registers',
}

export function copilotDisclosure(mode: CopilotDisclosureMode): CopilotDisclosure {
  if (mode === 'unavailable') return UNAVAILABLE
  if (mode === 'grounded') return GROUNDED
  return SIMULATED
}
