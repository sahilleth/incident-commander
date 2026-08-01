import { useState } from "react";
import { Loader2, ShieldAlert } from "lucide-react";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { PendingApproval } from "@/lib/types";

export interface ApprovalCardProps {
  approval: PendingApproval;
  service: string;
  namespace: string;
  isApproving?: boolean;
  onApprove: (approvalId: string) => void;
}

const RISK_TONE: Record<string, string> = {
  high: "text-status-escalated border-status-escalated/40 bg-status-escalated/10",
  medium: "text-status-mitigating border-status-mitigating/40 bg-status-mitigating/10",
  low: "text-status-resolved border-status-resolved/40 bg-status-resolved/10",
};

export function ApprovalCard({
  approval,
  service,
  namespace,
  isApproving,
  onApprove,
}: ApprovalCardProps) {
  const [open, setOpen] = useState(false);

  const isRollback = approval.action.type.toLowerCase() === "rollback";
  const isScale = approval.action.type.toLowerCase() === "scale";
  const confirmLabel = isRollback
    ? "Yes, run rollback"
    : isScale
      ? "Yes, apply scale"
      : `Yes, run ${approval.action.type}`;

  return (
    <div className="rounded-lg border border-status-mitigating/45 bg-status-mitigating/[0.07] p-4">
      <div className="flex flex-wrap items-center gap-2">
        <ShieldAlert className="size-4 text-status-mitigating" />
        <span className="font-mono text-xs font-semibold tracking-wider text-status-mitigating uppercase">
          {approval.action.type}
        </span>
        <span
          className={cn(
            "rounded border px-1.5 py-0.5 font-mono text-[10px] tracking-wider uppercase",
            RISK_TONE[approval.action.risk] ?? RISK_TONE["medium"],
          )}
        >
          risk: {approval.action.risk}
        </span>
        <span className="ml-auto font-mono text-[11px] text-muted-foreground">{approval.id}</span>
      </div>

      <p className="mt-3 text-sm text-foreground">Human approval required before execution.</p>
      <pre className="mt-2 overflow-x-auto rounded-md border border-border bg-background px-3 py-2 font-mono text-[11px] text-foreground/90">
        {approval.action.description}
      </pre>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <Button
          size="sm"
          disabled={isApproving}
          onClick={() => setOpen(true)}
          className="bg-status-mitigating font-medium text-background hover:bg-status-mitigating/85"
        >
          {isApproving ? <Loader2 className="size-3.5 animate-spin" /> : null}
          Approve {approval.action.type}
        </Button>
        <span className="font-mono text-[11px] text-muted-foreground">
          target: deployment/{service} · ns/{namespace}
        </span>
      </div>

      <AlertDialog open={open} onOpenChange={setOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Confirm destructive action</AlertDialogTitle>
            <AlertDialogDescription>
              {isRollback
                ? `This will run kubectl rollout undo on ${service}. Traffic in ns/${namespace} will shift to the previous revision immediately.`
                : isScale
                  ? `This will run kubectl scale on deployment/${service} in ns/${namespace} as described below.`
                  : `This will execute ${approval.action.type} on deployment/${service} in ns/${namespace}.`}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <pre className="overflow-x-auto rounded-md border border-border bg-background px-3 py-2 font-mono text-[11px] text-foreground/90">
            {approval.action.description}
          </pre>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isApproving}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              disabled={isApproving}
              onClick={(e) => {
                e.preventDefault();
                setOpen(false);
                onApprove(approval.id);
              }}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {confirmLabel}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
