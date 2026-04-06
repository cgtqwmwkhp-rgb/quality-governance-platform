import type { Meta, StoryObj } from '@storybook/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import '../i18n/i18n'
import { ThemeProvider } from '../contexts/ThemeContext'
import { ToastProvider } from '../contexts/ToastContext'
import { LiveAnnouncerProvider } from '../components/ui/LiveAnnouncer'
import { TooltipProvider } from '../components/ui/Tooltip'
import ForgotPassword from './ForgotPassword'

const meta: Meta<typeof ForgotPassword> = {
  title: 'Pages/Auth/ForgotPassword',
  component: ForgotPassword,
  decorators: [
    (Story) => (
      <ThemeProvider>
        <LiveAnnouncerProvider>
          <TooltipProvider>
            <ToastProvider>
              <MemoryRouter initialEntries={['/forgot-password']}>
                <Routes>
                  <Route path="/forgot-password" element={<Story />} />
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
type Story = StoryObj<typeof ForgotPassword>

export const Default: Story = {}
