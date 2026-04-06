import type { Meta, StoryObj } from "@storybook/react";
import { DataTable, Column } from "./DataTable";

interface SampleRow {
  id: number;
  reference: string;
  title: string;
  status: string;
}

const sampleColumns: Column<SampleRow>[] = [
  { key: "reference", header: "Reference" },
  { key: "title", header: "Title" },
  { key: "status", header: "Status" },
];

const sampleData: SampleRow[] = [
  { id: 1, reference: "INC-00001", title: "Equipment failure", status: "Open" },
  { id: 2, reference: "INC-00002", title: "Near miss in warehouse", status: "Closed" },
  { id: 3, reference: "INC-00003", title: "Chemical spill", status: "Investigating" },
];

const meta: Meta = {
  title: "UI/DataTable",
};
export default meta;
type Story = StoryObj;

export const Default: Story = {
  render: () => (
    <DataTable
      columns={sampleColumns}
      data={sampleData}
      keyExtractor={(row) => row.id}
      caption="Recent incidents"
    />
  ),
};

export const Empty: Story = {
  render: () => (
    <DataTable
      columns={sampleColumns}
      data={[]}
      keyExtractor={(row: SampleRow) => row.id}
      emptyMessage="No incidents found."
    />
  ),
};

export const Loading: Story = {
  render: () => (
    <DataTable
      columns={sampleColumns}
      data={[]}
      keyExtractor={(row: SampleRow) => row.id}
      loading
    />
  ),
};
