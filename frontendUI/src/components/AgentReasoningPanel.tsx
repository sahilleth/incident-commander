import { ChevronDown } from "lucide-react";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import type { ReActStep, WorkerRun } from "@/lib/types";
import { cn } from "@/lib/utils";

function formatActionInput(input: Record<string, unknown>): string {
  if (!input || Object.keys(input).length === 0) return "";
  try {
    return JSON.stringify(input);
  } catch {
    return String(input);
  }
}

function StepTrace({ step }: { step: ReActStep }) {
  return (
    <div className="space-y-1 rounded border border-border/60 bg-muted/30 p-3 font-mono text-[11px] leading-relaxed">
      <p className="text-muted-foreground">
        <span className="text-foreground/70">thought</span> {step.thought || "—"}
      </p>
      {step.action ? (
        <p>
          <span className="text-status-investigating">action</span> {step.action}
          {formatActionInput(step.action_input)
            ? `(${formatActionInput(step.action_input)})`
            : ""}
        </p>
      ) : null}
      <p className="text-foreground/90 whitespace-pre-wrap break-words">
        <span className="text-status-resolved">observation</span> {step.observation}
      </p>
    </div>
  );
}

export function AgentReasoningPanel({ run }: { run: WorkerRun }) {
  const steps = run.steps ?? [];
  if (steps.length === 0) return null;

  return (
    <Collapsible>
      <CollapsibleTrigger
        className={cn(
          "flex w-full items-center justify-between gap-2 rounded-md px-2 py-1.5",
          "text-[11px] font-medium text-muted-foreground hover:bg-muted/50 hover:text-foreground",
        )}
      >
        <span>Agent reasoning ({steps.length} steps)</span>
        <ChevronDown className="size-3.5 shrink-0 transition-transform [[data-state=open]>&]:rotate-180" />
      </CollapsibleTrigger>
      <CollapsibleContent className="mt-2 space-y-2">
        {steps.map((step, idx) => (
          <div key={`${run.worker}-step-${step.iteration}-${idx}`}>
            <p className="mb-1 font-mono text-[10px] text-muted-foreground uppercase tracking-wider">
              iteration {step.iteration}
            </p>
            <StepTrace step={step} />
          </div>
        ))}
      </CollapsibleContent>
    </Collapsible>
  );
}
