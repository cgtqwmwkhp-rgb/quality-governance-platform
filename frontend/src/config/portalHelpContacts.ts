export type PortalHelpContacts = {
  phone: string
  email: string
  chatUrl: string
  phoneHref: string | null
  emailHref: string | null
  chatHref: string | null
}

function readEnv(name: string): string {
  const value = import.meta.env[name]
  return typeof value === 'string' ? value.trim() : ''
}

function toTelHref(phone: string): string | null {
  if (!phone) return null
  // Keep leading +, strip other non-digits for tel: URI
  const normalized = phone.replace(/[^\d+]/g, '')
  if (!normalized || normalized === '+') return null
  return `tel:${normalized}`
}

function toChatHref(chatUrl: string): string | null {
  if (!chatUrl) return null
  // Fail-closed: reject placeholder / hash-only anchors (#, #chat, etc.)
  if (chatUrl.startsWith('#')) return null
  return chatUrl
}

/**
 * Portal help contact channels.
 *
 * Fail-closed rules:
 * - Phone / chat omitted unless a real dialable / http(s) value is configured.
 * - Email uses VITE_PORTAL_HELP_EMAIL when set; otherwise a documented real
 *   mailbox (not a placeholder). Production builds should set the env var
 *   explicitly (see .env.example / frontend/.env.example).
 */
export function getPortalHelpContacts(): PortalHelpContacts {
  const phone = readEnv('VITE_PORTAL_HELP_PHONE')
  const email = readEnv('VITE_PORTAL_HELP_EMAIL') || 'safety@plantexpand.com'
  const chatUrl = readEnv('VITE_PORTAL_HELP_CHAT_URL')
  return {
    phone,
    email,
    chatUrl,
    phoneHref: toTelHref(phone),
    emailHref: email ? `mailto:${email}` : null,
    chatHref: toChatHref(chatUrl),
  }
}
