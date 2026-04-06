import type { Meta, StoryObj } from "@storybook/react";
import { Skeleton, TableSkeleton, CardSkeleton } from "./SkeletonLoader";

const meta: Meta<typeof Skeleton> = {
  title: "UI/SkeletonLoader",
  component: Skeleton,
};
export default meta;
type Story = StoryObj<typeof Skeleton>;

export const TextSkeleton: Story = {
  args: {
    variant: "text",
    lines: 4,
  },
};

export const TableVariant: Story = {
  render: () => <TableSkeleton rows={5} columns={4} />,
};

export const CardVariant: Story = {
  render: () => <CardSkeleton count={3} />,
};
