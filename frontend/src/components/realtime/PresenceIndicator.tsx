/**
 * PresenceIndicator - Shows online/offline status for users
 *
 * Features:
 * - Color-coded status indicator
 * - Tooltip with last seen time
 * - Animated pulse for online users
 */

import React from "react";

type PresenceStatus = "online" | "away" | "busy" | "offline";

interface PresenceIndicatorProps {
  status: PresenceStatus;
  size?: "sm" | "md" | "lg";
  showLabel?: boolean;
  className?: string;
}

const PresenceIndicator: React.FC<PresenceIndicatorProps> = ({
  status,
  size = "md",
  showLabel = false,
  className = "",
}) => {
  const sizeClasses = {
    sm: "w-2 h-2",
    md: "w-3 h-3",
    lg: "w-4 h-4",
  };

  const statusConfig = {
    online: {
      color: "bg-emerald-500",
      label: "Online",
      pulse: true,
    },
    away: {
      color: "bg-yellow-500",
      label: "Away",
      pulse: false,
    },
    busy: {
      color: "bg-red-500",
      label: "Busy",
      pulse: false,
    },
    offline: {
      color: "bg-gray-500",
      label: "Offline",
      pulse: false,
    },
  };

  const config = statusConfig[status];

  return (
    <div className={`flex items-center gap-1.5 ${className}`}>
      <span className="relative flex">
        <span
          className={`
            ${sizeClasses[size]} 
            ${config.color} 
            rounded-full
          `}
        />
        {config.pulse && (
          <span
            className={`
              absolute inline-flex h-full w-full 
              rounded-full ${config.color} opacity-75 
              animate-ping
            `}
          />
        )}
      </span>
      {showLabel && (
        <span className="text-xs text-gray-400">{config.label}</span>
      )}
    </div>
  );
};

export default PresenceIndicator;
