import type { Meta, StoryObj } from "@storybook/react";
import { Switch } from "./Switch";

const meta: Meta<typeof Switch> = {
  title: "UI/Switch",
  component: Switch,
};
export default meta;
type Story = StoryObj<typeof Switch>;

export const Default: Story = {
  args: {
    "aria-label": "Toggle notifications",
  },
};

export const Checked: Story = {
  args: {
    checked: true,
    "aria-label": "Enabled",
  },
};

export const Disabled: Story = {
  args: {
    disabled: true,
    "aria-label": "Disabled switch",
  },
};
