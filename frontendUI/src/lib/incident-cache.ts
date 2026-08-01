import type { QueryClient } from "@tanstack/react-query";
import type { Incident } from "./types";

/** Keep incident detail + board list in sync after mutations. */
export function syncIncidentCaches(queryClient: QueryClient, incident: Incident) {
  queryClient.setQueryData(["incident", incident.incident_id], incident);
  queryClient.setQueriesData<Incident[]>({ queryKey: ["incidents"] }, (old) => {
    if (!old) return old;
    const idx = old.findIndex((i) => i.incident_id === incident.incident_id);
    if (idx === -1) return [incident, ...old];
    const next = [...old];
    next[idx] = incident;
    return next;
  });
}
