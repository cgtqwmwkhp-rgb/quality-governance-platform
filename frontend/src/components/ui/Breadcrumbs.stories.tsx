import type { Meta, StoryObj } from "@storybook/react";
import { MemoryRouter } from "react-router-dom";
import { Breadcrumbs } from "./Breadcrumbs";

const meta: Meta<typeof Breadcrumbs> = {
  title: "UI/Breadcrumbs",
  component: Breadcrumbs,
  decorators: [
    (Story) => (
      <MemoryRouter initialEntries={["/incidents/123"]}>
        <Story />
      </MemoryRouter>
    ),
  ],
};
export default meta;
type Story = StoryObj<typeof Breadcrumbs>;

export const Default: Story = {
  args: {
    items: [
      { label: "Incidents", href: "/incidents" },
      { label: "INC-00042" },
    ],
  },
};

export const DeepNesting: Story = {
  args: {
    items: [
      { label: "Dashboard", href: "/" },
      { label: "Audits", href: "/audits" },
      { label: "AUD-00017", href: "/audits/17" },
      { label: "Findings" },
    ],
  },
};
