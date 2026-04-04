import type { Meta, StoryObj } from "@storybook/react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "./Tabs";

const meta: Meta = {
  title: "UI/Tabs",
};
export default meta;
type Story = StoryObj;

export const Default: Story = {
  render: () => (
    <Tabs defaultValue="details">
      <TabsList>
        <TabsTrigger value="details">Details</TabsTrigger>
        <TabsTrigger value="actions">Actions</TabsTrigger>
        <TabsTrigger value="evidence">Evidence</TabsTrigger>
      </TabsList>
      <TabsContent value="details">
        <p className="text-sm text-muted-foreground">Incident details go here.</p>
      </TabsContent>
      <TabsContent value="actions">
        <p className="text-sm text-muted-foreground">CAPA actions list.</p>
      </TabsContent>
      <TabsContent value="evidence">
        <p className="text-sm text-muted-foreground">Uploaded evidence files.</p>
      </TabsContent>
    </Tabs>
  ),
};
