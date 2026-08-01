import { sourceMeta } from "./StatusBadge";
import { clockTime, fullTime } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { TimelineEvent } from "@/lib/types";

export interface TimelineProps {
  events: TimelineEvent[];
}

export function Timeline({ events }: TimelineProps) {
  if (events.length === 0) {
    return (
      <p className="px-4 py-10 text-center text-xs text-muted-foreground">
        No evidence recorded yet. Worker output appears here as it streams in.
      </p>
    );
  }

  return (
    <ol className="relative space-y-5 pl-6">
      <span className="absolute top-1.5 bottom-1.5 left-[5px] w-px bg-border" aria-hidden />
      {events.map((event, idx) => {
        const meta = sourceMeta(event.source);
        return (
          <li key={event.id ?? `${event.ts}-${idx}`} className="relative">
            <span
              className={cn(
                "absolute top-1.5 -left-6 size-[11px] rounded-full ring-3 ring-surface",
                meta.dot,
              )}
              aria-hidden
            />
            <div className="flex flex-wrap items-center gap-2">
              <span
                className={cn(
                  "rounded border px-1.5 py-0.5 font-mono text-[10px] tracking-wide",
                  meta.text,
                  meta.border,
                  meta.bg,
                )}
              >
                {meta.label}
              </span>
              <time
                className="font-mono text-[11px] text-muted-foreground"
                dateTime={event.ts}
                title={fullTime(event.ts)}
              >
                {clockTime(event.ts)}
              </time>
            </div>
            {event.title ? (
              <p className="mt-1.5 text-sm font-medium text-foreground">{event.title}</p>
            ) : null}
            <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">{event.message}</p>
            {event.detail ? (
              <pre className="mt-2 overflow-x-auto rounded-md border border-border bg-background px-3 py-2 font-mono text-[11px] leading-relaxed text-muted-foreground">
                {event.detail}
              </pre>
            ) : null}
          </li>
        );
      })}
    </ol>
  );
}
