import type { Meta, StoryObj } from "@storybook/react";
import { Input } from "./Input";

const meta: Meta<typeof Input> = {
  title: "UI/Input",
  component: Input,
};
export default meta;
type Story = StoryObj<typeof Input>;

export const Default: Story = {};

export const WithPlaceholder: Story = {
  args: { placeholder: "Enter your name" },
};

export const Disabled: Story = {
  args: { placeholder: "Cannot edit", disabled: true },
};

export const WithLabel: Story = {
  render: () => (
    <div className="space-y-2">
      <label htmlFor="email-input" className="text-sm font-medium">
        Email
      </label>
      <Input id="email-input" type="email" placeholder="you@example.com" />
    </div>
  ),
};

export const WithError: Story = {
  render: () => (
    <div className="space-y-2">
      <label htmlFor="error-input" className="text-sm font-medium">
        Username
      </label>
      <Input id="error-input" error placeholder="Invalid value" />
      <p className="text-sm text-destructive">This field is required.</p>
    </div>
  ),
};

export const TypeEmail: Story = {
  args: { type: "email", placeholder: "you@example.com" },
};

export const TypePassword: Story = {
  args: { type: "password", placeholder: "••••••••" },
};

export const TypeNumber: Story = {
  args: { type: "number", placeholder: "0" },
};
