import type { Meta, StoryObj } from "@storybook/react";
import { LiveAnnouncerProvider, useLiveAnnouncer } from "./LiveAnnouncer";

function AnnounceDemo() {
  const { announce } = useLiveAnnouncer();

  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm text-muted-foreground">
        Click the buttons below to trigger screen-reader announcements.
      </p>
      <div className="flex gap-2">
        <button
          className="px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm"
          onClick={() => announce("Incident saved successfully.")}
        >
          Polite announce
        </button>
        <button
          className="px-4 py-2 rounded-lg bg-destructive text-destructive-foreground text-sm"
          onClick={() => announce("Critical error occurred!", "assertive")}
        >
          Assertive announce
        </button>
      </div>
    </div>
  );
}

const meta: Meta = {
  title: "UI/LiveAnnouncer",
  decorators: [
    (Story) => (
      <LiveAnnouncerProvider>
        <Story />
      </LiveAnnouncerProvider>
    ),
  ],
};
export default meta;
type Story = StoryObj;

export const Default: Story = {
  render: () => <AnnounceDemo />,
};
