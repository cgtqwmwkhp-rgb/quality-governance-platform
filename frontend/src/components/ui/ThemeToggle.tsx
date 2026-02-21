import { Moon, Sun, Monitor } from "lucide-react";
import { useTheme } from "../../contexts/ThemeContext";
import { cn } from "../../helpers/utils";

interface ThemeToggleProps {
  variant?: "icon" | "full";
  className?: string;
}

export function ThemeToggle({ variant = "icon", className }: ThemeToggleProps) {
  const { theme, resolvedTheme, setTheme, toggleTheme } = useTheme();

  if (variant === "icon") {
    return (
      <button
        onClick={toggleTheme}
        className={cn(
          "p-2 rounded-lg transition-colors",
          "text-muted-foreground hover:text-foreground hover:bg-surface",
          className,
        )}
        aria-label={`Switch to ${resolvedTheme === "light" ? "dark" : "light"} mode`}
      >
        {resolvedTheme === "light" ? (
          <Moon className="h-5 w-5" />
        ) : (
          <Sun className="h-5 w-5" />
        )}
      </button>
    );
  }

  return (
    <div
      className={cn(
        "flex items-center gap-1 p-1 rounded-lg bg-surface border border-border",
        className,
      )}
    >
      <button
        onClick={() => setTheme("light")}
        aria-pressed={theme === "light"}
        aria-label="Light theme"
        className={cn(
          "flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium transition-all",
          theme === "light"
            ? "bg-background text-foreground shadow-sm"
            : "text-muted-foreground hover:text-foreground",
        )}
      >
        <Sun className="h-4 w-4" />
        <span className="hidden sm:inline">Light</span>
      </button>
      <button
        onClick={() => setTheme("dark")}
        aria-pressed={theme === "dark"}
        aria-label="Dark theme"
        className={cn(
          "flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium transition-all",
          theme === "dark"
            ? "bg-background text-foreground shadow-sm"
            : "text-muted-foreground hover:text-foreground",
        )}
      >
        <Moon className="h-4 w-4" />
        <span className="hidden sm:inline">Dark</span>
      </button>
      <button
        onClick={() => setTheme("system")}
        aria-pressed={theme === "system"}
        aria-label="System theme"
        className={cn(
          "flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium transition-all",
          theme === "system"
            ? "bg-background text-foreground shadow-sm"
            : "text-muted-foreground hover:text-foreground",
        )}
      >
        <Monitor className="h-4 w-4" />
        <span className="hidden sm:inline">System</span>
      </button>
    </div>
  );
}
