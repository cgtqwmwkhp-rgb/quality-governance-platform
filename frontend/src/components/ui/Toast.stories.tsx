import type { Meta, StoryObj } from "@storybook/react";
import { ToastContainer, ToastData } from "./Toast";
import { LiveAnnouncerProvider } from "./LiveAnnouncer";

const sampleToasts: ToastData[] = [
  { id: "1", message: "Incident saved successfully.", variant: "success" },
  { id: "2", message: "Failed to upload evidence.", variant: "error" },
  { id: "3", message: "Audit deadline approaching.", variant: "warning" },
  { id: "4", message: "New CAPA assigned to you.", variant: "info" },
];

const meta: Meta<typeof ToastContainer> = {
  title: "UI/Toast",
  component: ToastContainer,
  decorators: [
    (Story) => (
      <LiveAnnouncerProvider>
        <div className="relative min-h-[300px]">
          <Story />
        </div>
      </LiveAnnouncerProvider>
    ),
  ],
};
export default meta;
type Story = StoryObj<typeof ToastContainer>;

export const Default: Story = {
  args: {
    toasts: [sampleToasts[0]],
    onDismiss: () => {},
  },
};

export const AllVariants: Story = {
  args: {
    toasts: sampleToasts,
    onDismiss: () => {},
  },
};
