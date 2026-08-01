import { useEffect, useState } from "react";
import { Pause, Play, RefreshCw } from "lucide-react";
import { cn } from "@/lib/utils";

export interface RefreshControlProps {
  active: boolean;
  enabled: boolean;
  paused: boolean;
  secondsLeft: number;
  lastRefreshedAt: number;
  isFetching?: boolean;
  onToggle: (enabled: boolean) => void;
  onRefreshNow: () => void;
}

function clock(ts: number) {
  return new Date(ts).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}

/** Auto-refresh status + manual override, shared by the board and detail view. */
export function RefreshControl({
  active,
  enabled,
  paused,
  secondsLeft,
  lastRefreshedAt,
  isFetching,
  onToggle,
  onRefreshNow,
}: RefreshControlProps) {
  // Locale clock is client-only: rendering it during SSR causes a hydration mismatch.
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  const status = !active
    ? "auto-refresh off"
    : paused
      ? "paused · tab hidden"
      : !enabled
        ? "auto-refresh paused"
        : isFetching
          ? "refreshing…"
          : `next in ${secondsLeft}s`;

  return (
    <div className="inline-flex items-center gap-2 rounded-md border border-border bg-surface px-2 py-1">
      <span
        className={cn(
          "size-1.5 rounded-full",
          active && enabled && !paused ? "bg-status-resolved pulse-dot" : "bg-muted-foreground",
        )}
        aria-hidden
      />
      <span className="font-mono text-[11px] text-muted-foreground tabular-nums">{status}</span>
      <span className="h-3.5 w-px bg-border" aria-hidden />
      <span
        className="font-mono text-[11px] text-muted-foreground/70 tabular-nums"
        title="Last successful refresh"
      >
        {mounted ? clock(lastRefreshedAt) : "--:--:--"}
      </span>
      {active ? (
        <button
          type="button"
          onClick={() => onToggle(!enabled)}
          aria-label={enabled ? "Pause auto-refresh" : "Resume auto-refresh"}
          className="text-muted-foreground hover:text-foreground"
        >
          {enabled ? <Pause className="size-3.5" /> : <Play className="size-3.5" />}
        </button>
      ) : null}
      <button
        type="button"
        onClick={onRefreshNow}
        disabled={isFetching}
        aria-label="Refresh now"
        className="text-muted-foreground hover:text-foreground disabled:opacity-50"
      >
        <RefreshCw className={cn("size-3.5", isFetching && "animate-spin")} />
      </button>
    </div>
  );
}
