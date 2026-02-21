import { AlertTriangle, Settings, ArrowRight } from "lucide-react";

/**
 * SetupRequiredResponse - Matches backend schema from src/api/schemas/setup_required.py
 *
 * This response is returned as HTTP 200 to avoid triggering smoke gate failures,
 * but the error_class: SETUP_REQUIRED signals to clients that the module
 * is not ready for normal operation.
 */
export interface SetupRequiredResponse {
  error_class: "SETUP_REQUIRED";
  setup_required: true;
  module: string;
  message: string;
  next_action: string;
  request_id?: string | null;
}

/**
 * Type guard to check if an API response is a SETUP_REQUIRED response.
 * Use this to detect and handle setup_required responses without retry storms.
 *
 * @param data - Any API response data
 * @returns true if the response is a SETUP_REQUIRED response
 */
export function isSetupRequired(data: unknown): data is SetupRequiredResponse {
  if (!data || typeof data !== "object") return false;
  const obj = data as Record<string, unknown>;
  return (
    obj["error_class"] === "SETUP_REQUIRED" &&
    obj["setup_required"] === true &&
    typeof obj["module"] === "string" &&
    typeof obj["message"] === "string"
  );
}

interface SetupRequiredPanelProps {
  /** The setup required response from the API */
  response: SetupRequiredResponse;
  /** Optional custom title override */
  title?: string;
  /** Optional callback for retry/refresh action */
  onRetry?: () => void;
}

/**
 * SetupRequiredPanel - Reusable UI component for displaying SETUP_REQUIRED state
 *
 * Features:
 * - Clear visual indication that setup is needed
 * - Module name, message, and next action displayed
 * - Request ID shown for debugging/support
 * - Optional retry button for manual refresh
 *
 * Usage:
 *   import { SetupRequiredPanel, isSetupRequired } from '../components/ui/SetupRequiredPanel'
 *
 *   const response = await api.getData()
 *   if (isSetupRequired(response.data)) {
 *     return <SetupRequiredPanel response={response.data} />
 *   }
 */
export function SetupRequiredPanel({
  response,
  title,
  onRetry,
}: SetupRequiredPanelProps) {
  const moduleDisplayName = response.module
    .split("-")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");

  return (
    <div className="flex flex-col items-center justify-center min-h-[400px] p-8">
      <div className="w-full max-w-lg bg-card border border-border rounded-xl shadow-lg overflow-hidden">
        {/* Header */}
        <div className="bg-amber-500/10 border-b border-amber-500/20 px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-amber-500/20 rounded-lg">
              <Settings className="w-6 h-6 text-amber-500" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-foreground">
                {title || `${moduleDisplayName} Setup Required`}
              </h2>
              <p className="text-sm text-muted-foreground">
                Module: {response.module}
              </p>
            </div>
          </div>
        </div>

        {/* Content */}
        <div className="px-6 py-6 space-y-4">
          {/* Alert Message */}
          <div className="flex items-start gap-3 p-4 bg-amber-500/5 border border-amber-500/20 rounded-lg">
            <AlertTriangle className="w-5 h-5 text-amber-500 flex-shrink-0 mt-0.5" />
            <p className="text-sm text-foreground">{response.message}</p>
          </div>

          {/* Next Action */}
          <div className="p-4 bg-primary/5 border border-primary/20 rounded-lg">
            <h3 className="text-sm font-medium text-foreground mb-2 flex items-center gap-2">
              <ArrowRight className="w-4 h-4 text-primary" />
              Next Step
            </h3>
            <p className="text-sm text-muted-foreground">
              {response.next_action}
            </p>
          </div>

          {/* Request ID (for debugging) */}
          {response.request_id && (
            <p className="text-xs text-muted-foreground text-center">
              Request ID: {response.request_id}
            </p>
          )}
        </div>

        {/* Footer */}
        {onRetry && (
          <div className="px-6 py-4 bg-muted/50 border-t border-border">
            <button
              onClick={onRetry}
              className="w-full px-4 py-2 bg-primary text-primary-foreground hover:bg-primary-hover rounded-lg transition-colors text-sm font-medium"
            >
              Refresh
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

export default SetupRequiredPanel;
