import { PlugZap, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { getApiUrl } from "@/lib/api";

export interface ErrorStateProps {
  title?: string;
  message?: string;
  hint?: string;
  onRetry?: () => void;
  isRetrying?: boolean;
  compact?: boolean;
}

/** Real, actionable failure state — never a bare "something went wrong". */
export function ErrorState({
  title = "Could not reach the incident API",
  message,
  hint,
  onRetry,
  isRetrying,
  compact,
}: ErrorStateProps) {
  return (
    <div
      className={
        compact
          ? "flex flex-col items-center px-4 py-8 text-center"
          : "flex flex-col items-center px-6 py-16 text-center"
      }
      role="alert"
    >
      <div className="mb-4 flex size-11 items-center justify-center rounded-lg border border-status-escalated/40 bg-status-escalated/10">
        <PlugZap className="size-5 text-status-escalated" />
      </div>
      <p className="text-sm font-medium">{title}</p>
      {message ? (
        <p className="mt-1 max-w-sm font-mono text-[11px] break-words text-status-escalated/90">
          {message}
        </p>
      ) : null}
      <p className="mt-2 max-w-sm text-xs leading-relaxed text-muted-foreground">
        {hint ?? (
          <>
            The dashboard reads from{" "}
            <code className="font-mono text-foreground/80">{getApiUrl()}</code>. Check that the
            commander service is running and that VITE_API_URL points at it.
          </>
        )}
      </p>
      {onRetry ? (
        <Button size="sm" variant="secondary" className="mt-4" onClick={onRetry} disabled={isRetrying}>
          <RefreshCw className={isRetrying ? "size-3.5 animate-spin" : "size-3.5"} />
          {isRetrying ? "Retrying…" : "Retry"}
        </Button>
      ) : null}
    </div>
  );
}
