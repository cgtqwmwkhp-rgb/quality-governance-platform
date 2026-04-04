import type { Meta, StoryObj } from "@storybook/react";
import { Avatar } from "./Avatar";

const meta: Meta<typeof Avatar> = {
  title: "UI/Avatar",
  component: Avatar,
};
export default meta;
type Story = StoryObj<typeof Avatar>;

export const Default: Story = {
  args: {
    alt: "John Smith",
    size: "md",
  },
};

export const WithFallback: Story = {
  args: {
    fallback: "JS",
    size: "lg",
  },
};

export const Small: Story = {
  args: {
    alt: "Jane Doe",
    size: "sm",
  },
};

export const ExtraLarge: Story = {
  args: {
    alt: "Admin User",
    size: "xl",
  },
};
