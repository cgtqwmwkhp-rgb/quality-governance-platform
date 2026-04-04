import { useState, useMemo } from "react";
import type { Meta, StoryObj } from "@storybook/react";
import { ThemeToggle } from "./ThemeToggle";

type Theme = "light" | "dark" | "system";

function ThemeProviderMock({ children }: { children: React.ReactNode }) {
  const [theme, setTheme] = useState<Theme>("light");

  const contextValue = useMemo(
    () => ({
      theme,
      resolvedTheme: theme === "system" ? "light" : theme,
      setTheme,
      toggleTheme: () => setTheme((t) => (t === "light" ? "dark" : "light")),
    }),
    [theme],
  );

  return (
    <div data-testid="mock-theme" data-theme={contextValue.resolvedTheme}>
      {children}
    </div>
  );
}

const meta: Meta<typeof ThemeToggle> = {
  title: "UI/ThemeToggle",
  component: ThemeToggle,
  decorators: [
    (Story) => (
      <ThemeProviderMock>
        <Story />
      </ThemeProviderMock>
    ),
  ],
  parameters: {
    docs: {
      description: {
        component:
          "Requires ThemeContext provider. In Storybook, uses a mock provider. " +
          "Icon variant toggles between light/dark; full variant shows all three options.",
      },
    },
  },
};
export default meta;
type Story = StoryObj<typeof ThemeToggle>;

export const Icon: Story = {
  args: {
    variant: "icon",
  },
};

export const Full: Story = {
  args: {
    variant: "full",
  },
};
