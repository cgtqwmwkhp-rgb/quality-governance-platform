import * as React from "react";
import { cn } from "../../helpers/utils";

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  error?: boolean;
  errorMessage?: string;
}

const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, error, errorMessage, id, ...props }, ref) => {
    return (
      <input
        type={type}
        id={id}
        aria-invalid={error || undefined}
        aria-describedby={errorMessage ? `${id}-error` : undefined}
        className={cn(
          "flex h-9 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm",
          "placeholder:text-muted-foreground",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50 focus-visible:border-primary",
          "disabled:cursor-not-allowed disabled:opacity-50",
          "transition-colors",
          error &&
            "border-destructive focus-visible:ring-destructive/50 focus-visible:border-destructive",
          className,
        )}
        ref={ref}
        {...props}
      />
    );
  },
);
Input.displayName = "Input";

export { Input };
