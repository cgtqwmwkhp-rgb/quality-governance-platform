import type { Meta, StoryObj } from "@storybook/react";
import { ProgressBar } from "./ProgressBar";

const meta: Meta<typeof ProgressBar> = {
  title: "UI/ProgressBar",
  component: ProgressBar,
};
export default meta;
type Story = StoryObj<typeof ProgressBar>;

export const Default: Story = {
  args: {
    value: 60,
    max: 100,
  },
};

export const Success: Story = {
  args: {
    value: 100,
    max: 100,
    variant: "success",
  },
};

export const Warning: Story = {
  args: {
    value: 45,
    max: 100,
    variant: "warning",
    size: "lg",
  },
};

export const Destructive: Story = {
  args: {
    value: 15,
    max: 100,
    variant: "destructive",
    size: "sm",
  },
};
