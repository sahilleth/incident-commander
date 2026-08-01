import type { Incident, TimelineEvent } from "./types";
import { fullTime } from "./format";

export type TimelineExportFormat = "markdown" | "csv" | "json";

function csvCell(value: string): string {
  return `"${value.replace(/"/g, '""')}"`;
}

export function timelineToMarkdown(incident: Incident): string {
  const lines = [
    `# ${incident.incident_id} — evidence timeline`,
    "",
    `- **Service:** deployment/${incident.service}`,
    `- **Namespace:** ${incident.namespace}`,
    `- **Environment:** ${incident.environment ?? "—"}`,
    `- **Severity:** ${incident.severity}`,
    `- **Status:** ${incident.status}`,
    `- **Opened:** ${fullTime(incident.opened_at)}`,
    `- **Exported:** ${fullTime(new Date().toISOString())}`,
    "",
    "| Time (UTC) | Source | Event | Detail |",
    "| --- | --- | --- | --- |",
  ];
  for (const e of incident.timeline) {
    const title = [e.title, e.message].filter(Boolean).join(" — ").replace(/\|/g, "\\|");
    const detail = (e.detail ?? "").replace(/\s*\n\s*/g, " ⏎ ").replace(/\|/g, "\\|");
    lines.push(`| ${new Date(e.ts).toISOString()} | ${e.source} | ${title} | ${detail || "—"} |`);
  }
  return `${lines.join("\n")}\n`;
}

export function timelineToCsv(events: TimelineEvent[]): string {
  const rows = [["ts", "source", "title", "message", "detail"].join(",")];
  for (const e of events) {
    rows.push(
      [
        csvCell(new Date(e.ts).toISOString()),
        csvCell(String(e.source)),
        csvCell(e.title ?? ""),
        csvCell(e.message),
        csvCell(e.detail ?? ""),
      ].join(","),
    );
  }
  return `${rows.join("\n")}\n`;
}

export function downloadFile(filename: string, contents: string, mime: string) {
  const url = URL.createObjectURL(new Blob([contents], { type: `${mime};charset=utf-8` }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export function exportTimeline(incident: Incident, format: TimelineExportFormat): string {
  const base = `${incident.incident_id}-timeline`;
  if (format === "markdown") {
    downloadFile(`${base}.md`, timelineToMarkdown(incident), "text/markdown");
    return `${base}.md`;
  }
  if (format === "csv") {
    downloadFile(`${base}.csv`, timelineToCsv(incident.timeline), "text/csv");
    return `${base}.csv`;
  }
  downloadFile(
    `${base}.json`,
    JSON.stringify(
      {
        incident_id: incident.incident_id,
        service: incident.service,
        namespace: incident.namespace,
        severity: incident.severity,
        status: incident.status,
        exported_at: new Date().toISOString(),
        timeline: incident.timeline,
      },
      null,
      2,
    ),
    "application/json",
  );
  return `${base}.json`;
}
