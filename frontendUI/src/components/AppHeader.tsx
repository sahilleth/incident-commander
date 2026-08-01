import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { Activity } from "lucide-react";
import { getApiUrl, getHealth } from "@/lib/api";
import { cn } from "@/lib/utils";

export function AppHeader({ action }: { action?: React.ReactNode }) {
  const { data, isPending, isError } = useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
    refetchInterval: 30_000,
    retry: false,
  });

  const ok = data?.status === "ok";
  const label = isPending ? "checking" : ok ? "api ok" : "api unreachable";

  return (
    <header className="sticky top-0 z-20 border-b border-border bg-background/85 backdrop-blur">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-3 px-4 py-3 lg:px-6">
        <Link to="/" className="flex items-center gap-2.5">
          <span className="flex size-7 items-center justify-center rounded-md border border-primary/40 bg-primary/10">
            <Activity className="size-4 text-primary" />
          </span>
          <span className="text-sm font-semibold tracking-tight">
            Incident Commander
            <span className="ml-2 font-mono text-[11px] font-normal text-muted-foreground">
              k8s
            </span>
          </span>
        </Link>

        <div
          className={cn(
            "ml-auto inline-flex items-center gap-2 rounded-full border px-2.5 py-1 font-mono text-[11px]",
            isPending
              ? "border-border text-muted-foreground"
              : ok
                ? "border-status-resolved/40 bg-status-resolved/10 text-status-resolved"
                : "border-status-escalated/40 bg-status-escalated/10 text-status-escalated",
          )}
          title={`${getApiUrl()}/health`}
        >
          <span
            className={cn(
              "size-1.5 rounded-full",
              isPending
                ? "bg-muted-foreground"
                : ok
                  ? "bg-status-resolved pulse-dot"
                  : "bg-status-escalated",
            )}
          />
          {isError ? "api unreachable" : label}
        </div>
        {action}
      </div>
    </header>
  );
}
