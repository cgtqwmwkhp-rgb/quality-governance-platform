import type { Meta, StoryObj } from "@storybook/react";
import { Textarea } from "./Textarea";

const meta: Meta<typeof Textarea> = {
  title: "UI/Textarea",
  component: Textarea,
};
export default meta;
type Story = StoryObj<typeof Textarea>;

export const Default: Story = {
  args: {
    placeholder: "Describe the incident...",
  },
};

export const WithError: Story = {
  args: {
    placeholder: "Required field",
    error: true,
  },
};

export const Disabled: Story = {
  args: {
    placeholder: "Cannot edit",
    disabled: true,
  },
};
