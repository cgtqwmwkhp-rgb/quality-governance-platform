import type { Meta, StoryObj } from "@storybook/react";
import { EmptyState } from "./EmptyState";

const meta: Meta<typeof EmptyState> = {
  title: "UI/EmptyState",
  component: EmptyState,
};
export default meta;
type Story = StoryObj<typeof EmptyState>;

export const Default: Story = {
  args: {
    title: "No incidents found",
    description: "There are no incidents matching your filters.",
  },
};

export const WithAction: Story = {
  args: {
    title: "No audits yet",
    description: "Get started by creating your first audit template.",
    action: (
      <button className="px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm">
        Create Audit
      </button>
    ),
  },
};
