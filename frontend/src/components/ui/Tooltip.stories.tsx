import type { Meta, StoryObj } from "@storybook/react";
import { Tooltip, TooltipTrigger, TooltipContent, TooltipProvider } from "./Tooltip";

const meta: Meta = {
  title: "UI/Tooltip",
  decorators: [
    (Story) => (
      <TooltipProvider>
        <div className="p-16 flex items-center justify-center">
          <Story />
        </div>
      </TooltipProvider>
    ),
  ],
};
export default meta;
type Story = StoryObj;

export const Default: Story = {
  render: () => (
    <Tooltip>
      <TooltipTrigger asChild>
        <button className="px-4 py-2 rounded-lg border border-border">Hover me</button>
      </TooltipTrigger>
      <TooltipContent>
        <p>View incident details</p>
      </TooltipContent>
    </Tooltip>
  ),
};
