export type PortalHelpContacts = {
  phone: string
  email: string
  chatUrl: string
  phoneHref: string | null
  emailHref: string | null
  chatHref: string
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

export function getPortalHelpContacts(): PortalHelpContacts {
  const phone = readEnv('VITE_PORTAL_HELP_PHONE')
  const email = readEnv('VITE_PORTAL_HELP_EMAIL') || 'safety@plantexpand.com'
  const chatUrl = readEnv('VITE_PORTAL_HELP_CHAT_URL') || '#chat'
  return {
    phone,
    email,
    chatUrl,
    phoneHref: toTelHref(phone),
    emailHref: email ? `mailto:${email}` : null,
    chatHref: chatUrl,
  }
}
