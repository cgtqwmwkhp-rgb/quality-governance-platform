import { afterEach, describe, expect, it, vi } from 'vitest'

describe('getPortalHelpContacts', () => {
  afterEach(() => {
    vi.resetModules()
    vi.unstubAllEnvs()
  })

  async function loadContacts() {
    const mod = await import('../portalHelpContacts')
    return mod.getPortalHelpContacts
  }

  it('fail-closes chat/phone placeholders and keeps documented email default', async () => {
    const getPortalHelpContacts = await loadContacts()

    expect(getPortalHelpContacts()).toEqual({
      phone: '',
      email: 'safety@plantexpand.com',
      chatUrl: '',
      phoneHref: null,
      emailHref: 'mailto:safety@plantexpand.com',
      chatHref: null,
    })
  })

  it('reads and trims configured contact values', async () => {
    vi.stubEnv('VITE_PORTAL_HELP_PHONE', ' +44 (0) 20 7946 0958 ')
    vi.stubEnv('VITE_PORTAL_HELP_EMAIL', ' help@example.com ')
    vi.stubEnv('VITE_PORTAL_HELP_CHAT_URL', ' https://chat.example.com/help ')

    const getPortalHelpContacts = await loadContacts()

    expect(getPortalHelpContacts()).toEqual({
      phone: '+44 (0) 20 7946 0958',
      email: 'help@example.com',
      chatUrl: 'https://chat.example.com/help',
      phoneHref: 'tel:+4402079460958',
      emailHref: 'mailto:help@example.com',
      chatHref: 'https://chat.example.com/help',
    })
  })

  it('does not create a phone link for non-dialable input', async () => {
    vi.stubEnv('VITE_PORTAL_HELP_PHONE', ' + ')

    const getPortalHelpContacts = await loadContacts()

    expect(getPortalHelpContacts().phoneHref).toBeNull()
  })

  it('rejects hash-only chat placeholders', async () => {
    vi.stubEnv('VITE_PORTAL_HELP_CHAT_URL', '#chat')

    const getPortalHelpContacts = await loadContacts()

    expect(getPortalHelpContacts().chatHref).toBeNull()
  })
})
