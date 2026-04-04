import type { Meta, StoryObj } from "@storybook/react";
import { Mail } from "lucide-react";
import { Button } from "./Button";

const meta: Meta<typeof Button> = {
  title: "UI/Button",
  component: Button,
};
export default meta;
type Story = StoryObj<typeof Button>;

export const Default: Story = {
  args: { children: "Button" },
};

export const Primary: Story = {
  args: { variant: "default", children: "Primary" },
};

export const Secondary: Story = {
  args: { variant: "secondary", children: "Secondary" },
};

export const Destructive: Story = {
  args: { variant: "destructive", children: "Destructive" },
};

export const Outline: Story = {
  args: { variant: "outline", children: "Outline" },
};

export const Ghost: Story = {
  args: { variant: "ghost", children: "Ghost" },
};

export const Link: Story = {
  args: { variant: "link", children: "Link" },
};

export const Small: Story = {
  args: { size: "sm", children: "Small" },
};

export const DefaultSize: Story = {
  args: { size: "default", children: "Default" },
};

export const Large: Story = {
  args: { size: "lg", children: "Large" },
};

export const WithIcon: Story = {
  render: () => (
    <Button>
      <Mail className="h-4 w-4" />
      Send Email
    </Button>
  ),
};

export const Disabled: Story = {
  args: { disabled: true, children: "Disabled" },
};
