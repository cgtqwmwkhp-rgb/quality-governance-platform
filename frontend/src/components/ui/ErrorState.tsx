import { AlertCircle, RefreshCw, WifiOff } from "lucide-react";
import { Button } from "./Button";
import { cn } from "../../helpers/utils";

interface ErrorStateProps {
  title?: string;
  message?: string;
  onRetry?: () => void;
  variant?: "default" | "network" | "inline";
  className?: string;
}

export function ErrorState({
  title = "Something went wrong",
  message = "An error occurred while loading data. Please try again.",
  onRetry,
  variant = "default",
  className,
}: ErrorStateProps) {
  const Icon = variant === "network" ? WifiOff : AlertCircle;

  if (variant === "inline") {
    return (
      <div
        className={cn(
          "flex items-center gap-3 p-3 rounded-xl bg-destructive/10 border border-destructive/20",
          className,
        )}
      >
        <AlertCircle className="w-5 h-5 text-destructive flex-shrink-0" />
        <p className="text-sm text-destructive flex-1">{message}</p>
        {onRetry && (
          <Button variant="ghost" size="sm" onClick={onRetry}>
            <RefreshCw className="w-4 h-4" />
          </Button>
        )}
      </div>
    );
  }

  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center py-16 gap-4",
        className,
      )}
    >
      <div className="w-16 h-16 rounded-full bg-destructive/10 flex items-center justify-center">
        <Icon className="w-8 h-8 text-destructive" />
      </div>
      <div className="text-center max-w-md">
        <h3 className="text-lg font-semibold text-foreground mb-1">{title}</h3>
        <p className="text-muted-foreground">{message}</p>
      </div>
      {onRetry && (
        <Button onClick={onRetry} variant="outline">
          <RefreshCw className="w-4 h-4" />
          Try Again
        </Button>
      )}
    </div>
  );
}
