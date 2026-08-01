import { Terminal } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Hypothesis } from "@/lib/types";

export interface HypothesisCardProps {
  hypothesis: Hypothesis;
  rank: number;
}

export function HypothesisCard({ hypothesis, rank }: HypothesisCardProps) {
  const pct = Math.round(hypothesis.confidence * 100);
  const tone =
    pct >= 70 ? "text-status-escalated" : pct >= 40 ? "text-status-mitigating" : "text-muted-foreground";
  const bar =
    pct >= 70 ? "bg-status-escalated" : pct >= 40 ? "bg-status-mitigating" : "bg-muted-foreground";

  return (
    <article className="rounded-lg border border-border bg-surface p-4">
      <div className="flex items-start gap-3">
        <span className="mt-0.5 font-mono text-[11px] text-muted-foreground">
          H{rank.toString().padStart(2, "0")}
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-sm leading-relaxed text-foreground">{hypothesis.description}</p>

          <div className="mt-3 flex items-center gap-3">
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
              <div className={cn("h-full rounded-full", bar)} style={{ width: `${pct}%` }} />
            </div>
            <span className={cn("font-mono text-xs font-semibold tabular-nums", tone)}>
              {pct}%
            </span>
          </div>

          {hypothesis.evidence?.length ? (
            <ul className="mt-3 space-y-1">
              {hypothesis.evidence.map((e) => (
                <li key={e} className="font-mono text-[11px] text-muted-foreground">
                  · {e}
                </li>
              ))}
            </ul>
          ) : null}

          {hypothesis.suggested_actions.length ? (
            <div className="mt-3 border-t border-border pt-3">
              <p className="flex items-center gap-1.5 text-[11px] font-medium tracking-wide text-muted-foreground uppercase">
                <Terminal className="size-3" />
                Suggested actions
              </p>
              <ul className="mt-2 space-y-1.5">
                {hypothesis.suggested_actions.map((action) => (
                  <li key={action} className="flex gap-2 text-xs text-foreground/90">
                    <span className="text-primary">›</span>
                    <span className="font-mono">{action}</span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      </div>
    </article>
  );
}
