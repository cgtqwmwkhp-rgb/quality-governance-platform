import type { Meta, StoryObj } from "@storybook/react";
import {
  Dialog,
  DialogTrigger,
  DialogContent,
  DialogHeader,
  DialogFooter,
  DialogTitle,
  DialogDescription,
} from "./Dialog";

const meta: Meta = {
  title: "UI/Dialog",
  component: DialogContent,
};
export default meta;
type Story = StoryObj;

export const Default: Story = {
  render: () => (
    <Dialog>
      <DialogTrigger asChild>
        <button className="px-4 py-2 rounded-lg bg-primary text-primary-foreground">
          Open Dialog
        </button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Edit Incident</DialogTitle>
          <DialogDescription>
            Make changes to the incident details below.
          </DialogDescription>
        </DialogHeader>
        <div className="py-4">
          <p className="text-sm text-muted-foreground">Dialog body content goes here.</p>
        </div>
        <DialogFooter>
          <button className="px-4 py-2 rounded-lg bg-primary text-primary-foreground">
            Save changes
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  ),
};
