import { cn } from "../../helpers/utils";

interface LoadingSkeletonProps {
  className?: string;
  variant?: "text" | "card" | "table" | "inline";
  lines?: number;
  rows?: number;
  columns?: number;
  count?: number;
}

function ShimmerBar({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "relative overflow-hidden rounded bg-muted",
        "before:absolute before:inset-0",
        "before:-translate-x-full before:animate-[shimmer_1.5s_infinite]",
        "before:bg-gradient-to-r before:from-transparent before:via-white/20 before:to-transparent",
        className,
      )}
    />
  );
}

export function LoadingSkeleton({
  className,
  variant = "text",
  lines = 3,
  rows = 5,
  columns = 4,
  count = 3,
}: LoadingSkeletonProps) {
  if (variant === "inline") {
    return <ShimmerBar className={cn("h-4 w-24", className)} />;
  }

  if (variant === "card") {
    return (
      <div
        className={cn(
          "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4",
          className,
        )}
        role="status"
        aria-busy="true"
        aria-label="Loading"
      >
        {Array.from({ length: count }).map((_, i) => (
          <div
            key={i}
            className="rounded-xl border border-border bg-card p-6 space-y-4"
          >
            <div className="flex items-center gap-3">
              <ShimmerBar className="w-10 h-10 rounded-lg" />
              <div className="flex-1 space-y-2">
                <ShimmerBar className="h-4 w-3/4" />
                <ShimmerBar className="h-3 w-1/2" />
              </div>
            </div>
            <div className="space-y-2">
              <ShimmerBar className="h-3 w-full" />
              <ShimmerBar className="h-3 w-5/6" />
            </div>
            <div className="flex gap-2 pt-2">
              <ShimmerBar className="h-6 w-16 rounded-full" />
              <ShimmerBar className="h-6 w-20 rounded-full" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (variant === "table") {
    return (
      <div
        className={cn("w-full", className)}
        role="status"
        aria-busy="true"
        aria-label="Loading table"
      >
        <div className="flex gap-4 mb-4 pb-3 border-b border-border">
          {Array.from({ length: columns }).map((_, i) => (
            <ShimmerBar key={i} className="h-4 flex-1" />
          ))}
        </div>
        <div className="space-y-3">
          {Array.from({ length: rows }).map((_, row) => (
            <div key={row} className="flex gap-4">
              {Array.from({ length: columns }).map((_, col) => (
                <ShimmerBar
                  key={col}
                  className={cn("h-4 flex-1", col === 0 && "max-w-[140px]")}
                />
              ))}
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div
      className={cn("space-y-3", className)}
      role="status"
      aria-busy="true"
      aria-label="Loading"
    >
      {Array.from({ length: lines }).map((_, i) => (
        <ShimmerBar
          key={i}
          className={cn("h-4", i === lines - 1 ? "w-2/3" : "w-full")}
        />
      ))}
    </div>
  );
}
