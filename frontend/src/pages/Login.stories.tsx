import type { Meta, StoryObj } from '@storybook/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import '../i18n/i18n'
import { ThemeProvider } from '../contexts/ThemeContext'
import { ToastProvider } from '../contexts/ToastContext'
import { LiveAnnouncerProvider } from '../components/ui/LiveAnnouncer'
import { TooltipProvider } from '../components/ui/Tooltip'
import Login from './Login'

const meta: Meta<typeof Login> = {
  title: 'Pages/Auth/Login',
  component: Login,
  decorators: [
    (Story) => (
      <ThemeProvider>
        <LiveAnnouncerProvider>
          <TooltipProvider>
            <ToastProvider>
              <MemoryRouter initialEntries={['/login']}>
                <Routes>
                  <Route path="/login" element={<Story />} />
                </Routes>
              </MemoryRouter>
            </ToastProvider>
          </TooltipProvider>
        </LiveAnnouncerProvider>
      </ThemeProvider>
    ),
  ],
}

export default meta
type Story = StoryObj<typeof Login>

export const Default: Story = {}
