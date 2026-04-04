import type { Meta, StoryObj } from "@storybook/react";
import { LoadingSkeleton } from "./LoadingSkeleton";

const meta: Meta<typeof LoadingSkeleton> = {
  title: "UI/LoadingSkeleton",
  component: LoadingSkeleton,
};
export default meta;
type Story = StoryObj<typeof LoadingSkeleton>;

export const Text: Story = {
  args: {
    variant: "text",
    lines: 3,
  },
};

export const Card: Story = {
  args: {
    variant: "card",
    count: 3,
  },
};

export const Table: Story = {
  args: {
    variant: "table",
    rows: 5,
    columns: 4,
  },
};

export const Inline: Story = {
  args: {
    variant: "inline",
  },
};
