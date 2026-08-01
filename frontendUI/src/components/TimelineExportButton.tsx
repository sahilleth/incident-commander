import { useState } from "react";
import { Download, FileJson, FileText, Table2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { exportTimeline, type TimelineExportFormat } from "@/lib/export";
import type { Incident } from "@/lib/types";

const OPTIONS: { format: TimelineExportFormat; label: string; icon: typeof FileText }[] = [
  { format: "markdown", label: "Markdown (.md)", icon: FileText },
  { format: "csv", label: "CSV (.csv)", icon: Table2 },
  { format: "json", label: "JSON (.json)", icon: FileJson },
];

export function TimelineExportButton({ incident }: { incident: Incident }) {
  const [busy, setBusy] = useState(false);
  const empty = incident.timeline.length === 0;

  function run(format: TimelineExportFormat) {
    setBusy(true);
    try {
      const name = exportTimeline(incident, format);
      toast.success("Timeline exported", { description: name });
    } catch (err) {
      toast.error("Export failed", { description: (err as Error).message });
    } finally {
      setBusy(false);
    }
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          size="sm"
          variant="secondary"
          disabled={empty || busy}
          title={empty ? "No timeline events to export yet" : "Export evidence timeline"}
        >
          <Download className="size-3.5" />
          Export timeline
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-48">
        <DropdownMenuLabel className="font-mono text-[11px] tracking-wider uppercase">
          {incident.timeline.length} events
        </DropdownMenuLabel>
        {OPTIONS.map(({ format, label, icon: Icon }) => (
          <DropdownMenuItem key={format} onSelect={() => run(format)} className="text-xs">
            <Icon className="size-3.5" />
            {label}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
