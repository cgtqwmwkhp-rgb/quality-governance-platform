import type { Meta, StoryObj } from "@storybook/react";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
} from "./Card";
import { Button } from "./Button";

const meta: Meta<typeof Card> = {
  title: "UI/Card",
  component: Card,
};
export default meta;
type Story = StoryObj<typeof Card>;

export const Default: Story = {
  render: () => (
    <Card className="w-[380px]">
      <CardHeader>
        <CardTitle>Card Title</CardTitle>
        <CardDescription>
          Card description with supporting text.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <p>Card content goes here. This is the main body of the card.</p>
      </CardContent>
      <CardFooter className="gap-2">
        <Button variant="outline">Cancel</Button>
        <Button>Save</Button>
      </CardFooter>
    </Card>
  ),
};

export const Interactive: Story = {
  render: () => (
    <Card hoverable className="w-[380px] cursor-pointer">
      <CardHeader>
        <CardTitle>Interactive Card</CardTitle>
        <CardDescription>
          This card has hover effects. Try hovering over it.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <p>Hoverable cards lift slightly and gain a stronger border on hover.</p>
      </CardContent>
    </Card>
  ),
};
