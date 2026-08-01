import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { toApiEnvironment } from "@/lib/environment";
import type { CreateIncidentInput, Severity } from "@/lib/types";

export interface OpenIncidentModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  isSubmitting?: boolean;
  onSubmit: (input: CreateIncidentInput) => void;
}

const SEVERITIES: { value: Severity; label: string }[] = [
  { value: "SEV1", label: "SEV1 — total outage / revenue impact" },
  { value: "SEV2", label: "SEV2 — major degradation" },
  { value: "SEV3", label: "SEV3 — partial / SLO burn" },
  { value: "SEV4", label: "SEV4 — minor, no user impact" },
];

const ENVIRONMENTS = [
  { value: "production", label: "production" },
  { value: "staging", label: "staging" },
  { value: "development", label: "development" },
];

const DEFAULTS = {
  service: "payment-api",
  namespace: "default",
  trigger: "",
  severity: "SEV2" as Severity,
  environment: "production",
};

export function OpenIncidentModal({
  open,
  onOpenChange,
  isSubmitting,
  onSubmit,
}: OpenIncidentModalProps) {
  const [service, setService] = useState(DEFAULTS.service);
  const [namespace, setNamespace] = useState(DEFAULTS.namespace);
  const [trigger, setTrigger] = useState(DEFAULTS.trigger);
  const [severity, setSeverity] = useState<Severity>(DEFAULTS.severity);
  const [environment, setEnvironment] = useState(DEFAULTS.environment);

  useEffect(() => {
    if (!open) {
      setService(DEFAULTS.service);
      setNamespace(DEFAULTS.namespace);
      setTrigger(DEFAULTS.trigger);
      setSeverity(DEFAULTS.severity);
      setEnvironment(DEFAULTS.environment);
    }
  }, [open]);

  const valid = service.trim() && namespace.trim() && trigger.trim();

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Open incident</DialogTitle>
          <DialogDescription>
            Dispatches the deploy, logs, metrics and cluster workers against a Kubernetes
            deployment.
          </DialogDescription>
        </DialogHeader>

        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            if (!valid || isSubmitting) return;
            onSubmit({
              service: service.trim(),
              namespace: namespace.trim(),
              trigger: trigger.trim(),
              severity,
              environment: toApiEnvironment(environment),
            });
          }}
        >
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="service">Service (deployment name)</Label>
              <Input
                id="service"
                value={service}
                onChange={(e) => setService(e.target.value)}
                placeholder="payment-api"
                className="font-mono text-sm"
                autoFocus
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="namespace">Namespace</Label>
              <Input
                id="namespace"
                value={namespace}
                onChange={(e) => setNamespace(e.target.value)}
                placeholder="default"
                className="font-mono text-sm"
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="trigger">Trigger</Label>
            <Textarea
              id="trigger"
              value={trigger}
              onChange={(e) => setTrigger(e.target.value)}
              placeholder="manual:health-check or Alertmanager: HighHTTP5xxRate"
              rows={3}
              className="text-sm"
            />
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label>Severity</Label>
              <Select value={severity} onValueChange={(v) => setSeverity(v as Severity)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {SEVERITIES.map((s) => (
                    <SelectItem key={s.value} value={s.value}>
                      {s.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>Environment</Label>
              <Select value={environment} onValueChange={setEnvironment}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ENVIRONMENTS.map((env) => (
                    <SelectItem key={env.value} value={env.value} className="font-mono">
                      {env.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="ghost"
              disabled={isSubmitting}
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={!valid || isSubmitting}>
              {isSubmitting ? <Loader2 className="size-3.5 animate-spin" /> : null}
              Dispatch investigation
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
