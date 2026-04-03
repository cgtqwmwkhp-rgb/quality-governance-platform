import type { Meta, StoryObj } from '@storybook/react'
import { Button } from './Button'

const meta: Meta<typeof Button> = {
  title: 'UI/Button',
  component: Button,
  tags: ['autodocs'],
}

export default meta
type Story = StoryObj<typeof Button>

export const Default: Story = {
  args: { children: 'Button' },
}

export const Primary: Story = {
  args: { variant: 'default', children: 'Primary' },
}

export const Destructive: Story = {
  args: { variant: 'destructive', children: 'Delete' },
}

export const Disabled: Story = {
  args: { children: 'Disabled', disabled: true },
}

export const Loading: Story = {
  args: { children: 'Loading…', disabled: true, 'aria-busy': true },
}
