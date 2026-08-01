/** Map UI environment labels to API / incident commander values. */
export function toApiEnvironment(label: string): string {
  const map: Record<string, string> = {
    production: "prod",
    staging: "staging",
    development: "dev",
    prod: "prod",
  };
  return map[label] ?? label;
}
