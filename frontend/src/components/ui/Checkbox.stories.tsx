import type { Meta, StoryObj } from "@storybook/react";
import { Checkbox } from "./Checkbox";

const meta: Meta<typeof Checkbox> = {
  title: "UI/Checkbox",
  component: Checkbox,
};
export default meta;
type Story = StoryObj<typeof Checkbox>;

export const Default: Story = {
  args: {
    id: "terms",
    "aria-label": "Accept terms",
  },
};

export const Checked: Story = {
  args: {
    id: "checked",
    checked: true,
    "aria-label": "Checked",
  },
};

export const Disabled: Story = {
  args: {
    id: "disabled",
    disabled: true,
    "aria-label": "Disabled checkbox",
  },
};
