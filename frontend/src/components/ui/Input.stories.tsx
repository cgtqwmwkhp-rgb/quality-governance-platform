import type { Meta, StoryObj } from '@storybook/react'
import { Input } from './Input'

const meta: Meta<typeof Input> = {
  title: 'UI/Input',
  component: Input,
  tags: ['autodocs'],
}

export default meta
type Story = StoryObj<typeof Input>

export const Default: Story = {
  args: { placeholder: 'Enter text…' },
}

export const WithLabel: Story = {
  render: () => (
    <div className="grid gap-1.5">
      <label htmlFor="email-input" className="text-sm font-medium">
        Email
      </label>
      <Input id="email-input" type="email" placeholder="you@example.com" />
    </div>
  ),
}

export const Disabled: Story = {
  args: { placeholder: 'Disabled input', disabled: true },
}

export const ErrorState: Story = {
  args: { placeholder: 'Invalid value', error: true },
}
