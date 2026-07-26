import type { Meta, StoryObj } from "@storybook/react";
import { Bell, Trash2, X } from "lucide-react";
import { IconButton } from "./IconButton";

const meta: Meta<typeof IconButton> = {
  title: "UI/IconButton",
  component: IconButton,
};
export default meta;
type Story = StoryObj<typeof IconButton>;

export const Default: Story = {
  args: {
    label: "Dismiss",
    children: <X className="h-4 w-4" aria-hidden="true" />,
  },
};

export const Destructive: Story = {
  args: {
    variant: "destructive",
    label: "Delete row",
    children: <Trash2 className="h-4 w-4" aria-hidden="true" />,
  },
};

export const Sizes: Story = {
  render: () => (
    <div className="flex items-center gap-2">
      <IconButton size="icon-sm" label="Notifications, small">
        <Bell className="h-4 w-4" aria-hidden="true" />
      </IconButton>
      <IconButton size="icon" label="Notifications">
        <Bell className="h-4 w-4" aria-hidden="true" />
      </IconButton>
      <IconButton size="icon-lg" label="Notifications, large">
        <Bell className="h-5 w-5" aria-hidden="true" />
      </IconButton>
    </div>
  ),
};

export const WithoutTooltip: Story = {
  args: {
    label: "Dismiss",
    tooltip: false,
    children: <X className="h-4 w-4" aria-hidden="true" />,
  },
};

export const Disabled: Story = {
  args: {
    label: "Dismiss",
    disabled: true,
    children: <X className="h-4 w-4" aria-hidden="true" />,
  },
};
