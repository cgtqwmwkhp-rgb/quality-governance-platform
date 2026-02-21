import * as React from "react";
import { cn } from "../../helpers/utils";

interface AvatarProps extends React.HTMLAttributes<HTMLDivElement> {
  size?: "sm" | "md" | "lg" | "xl";
  src?: string;
  alt?: string;
  fallback?: string;
}

const sizeClasses = {
  sm: "h-8 w-8 text-xs",
  md: "h-10 w-10 text-sm",
  lg: "h-12 w-12 text-base",
  xl: "h-16 w-16 text-lg",
};

const Avatar = React.forwardRef<HTMLDivElement, AvatarProps>(
  ({ className, size = "md", src, alt, fallback, ...props }, ref) => {
    const [imageError, setImageError] = React.useState(false);

    const initials =
      fallback ||
      (alt
        ? alt
            .split(" ")
            .map((w) => w[0])
            .join("")
            .slice(0, 2)
            .toUpperCase()
        : "?");

    return (
      <div
        ref={ref}
        role={!src || imageError ? "img" : undefined}
        aria-label={!src || imageError ? alt || initials : undefined}
        className={cn(
          "relative flex shrink-0 items-center justify-center overflow-hidden rounded-full bg-surface font-medium text-muted-foreground",
          sizeClasses[size],
          className,
        )}
        {...props}
      >
        {src && !imageError ? (
          <img
            src={src}
            alt={alt || ""}
            className="aspect-square h-full w-full object-cover"
            onError={() => setImageError(true)}
          />
        ) : (
          <span aria-hidden="true">{initials}</span>
        )}
      </div>
    );
  },
);
Avatar.displayName = "Avatar";

export { Avatar };
