import { createFileRoute } from "@tanstack/react-router";
import { AppHeader } from "@/components/AppHeader";
import { IncidentDetail } from "@/components/IncidentDetail";
import { getIncident } from "@/lib/api";

export const Route = createFileRoute("/incidents/$id")({
  loader: async ({ context, params }) => {
    await context.queryClient.ensureQueryData({
      queryKey: ["incident", params.id],
      queryFn: () => getIncident(params.id),
    });
  },
  head: ({ params }) => ({
    meta: [
      { title: `${params.id} — Incident Commander` },
      {
        name: "description",
        content: `Evidence timeline, ranked hypotheses, worker runs and pending rollback approvals for incident ${params.id}.`,
      },
      { property: "og:title", content: `${params.id} — Incident Commander` },
      {
        property: "og:description",
        content: `Kubernetes incident ${params.id}: correlated evidence and human-approved remediation.`,
      },
    ],
  }),
  component: IncidentDetailPage,
});

function IncidentDetailPage() {
  const { id } = Route.useParams();
  return (
    <div className="min-h-screen">
      <AppHeader />
      <main>
        <IncidentDetail incidentId={id} />
      </main>
    </div>
  );
}
