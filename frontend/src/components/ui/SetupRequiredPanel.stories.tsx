import type { Meta, StoryObj } from "@storybook/react";
import { SetupRequiredPanel, SetupRequiredResponse } from "./SetupRequiredPanel";

const sampleResponse: SetupRequiredResponse = {
  error_class: "SETUP_REQUIRED",
  setup_required: true,
  module: "vehicle-checklists",
  message: "The vehicle checklists module requires initial configuration before use.",
  next_action: "Navigate to Admin > Modules > Vehicle Checklists and complete the setup wizard.",
  request_id: "req-abc-123",
};

const meta: Meta<typeof SetupRequiredPanel> = {
  title: "UI/SetupRequiredPanel",
  component: SetupRequiredPanel,
};
export default meta;
type Story = StoryObj<typeof SetupRequiredPanel>;

export const Default: Story = {
  args: {
    response: sampleResponse,
  },
};

export const WithRetry: Story = {
  args: {
    response: sampleResponse,
    onRetry: () => alert("Retrying..."),
  },
};

export const CustomTitle: Story = {
  args: {
    response: { ...sampleResponse, module: "risk-register" },
    title: "Risk Register Not Configured",
  },
};
