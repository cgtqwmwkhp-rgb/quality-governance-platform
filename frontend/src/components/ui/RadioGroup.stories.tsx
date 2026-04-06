import { useState } from "react";
import type { Meta, StoryObj } from "@storybook/react";
import { RadioGroup, RadioGroupItem } from "./RadioGroup";
import { Label } from "./Label";

const meta: Meta<typeof RadioGroup> = {
  title: "UI/RadioGroup",
  component: RadioGroup,
};
export default meta;
type Story = StoryObj<typeof RadioGroup>;

function RadioGroupDemo() {
  const [value, setValue] = useState("medium");
  return (
    <RadioGroup value={value} onValueChange={setValue}>
      <div className="flex items-center gap-2">
        <RadioGroupItem value="low" id="low" />
        <Label htmlFor="low">Low</Label>
      </div>
      <div className="flex items-center gap-2">
        <RadioGroupItem value="medium" id="medium" />
        <Label htmlFor="medium">Medium</Label>
      </div>
      <div className="flex items-center gap-2">
        <RadioGroupItem value="high" id="high" />
        <Label htmlFor="high">High</Label>
      </div>
    </RadioGroup>
  );
}

export const Default: Story = {
  render: () => <RadioGroupDemo />,
};
