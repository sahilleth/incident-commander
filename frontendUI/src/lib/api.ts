import { mapBackendIncident, type BackendIncident } from "./api-mapper";
import type { CreateIncidentInput, Incident } from "./types";

/**
 * Browser dev (Vite :3000): `/api` → proxied to the commander API.
 * SSR (Node): absolute URL — relative fetch("/api/...") fails in Node.
 * Production (same origin): `/api` on the FastAPI host.
 */
export function getApiUrl(): string {
  const configured = import.meta.env["VITE_API_URL"] as string | undefined;
  if (configured?.trim()) return configured.trim().replace(/\/$/, "");

  const isBrowser = typeof globalThis.window !== "undefined";
  if (!isBrowser || import.meta.env.SSR) {
    const target =
      (import.meta.env["VITE_API_PROXY_TARGET"] as string | undefined) ??
      process.env["VITE_API_PROXY_TARGET"] ??
      "http://localhost:8080";
    return `${target.replace(/\/$/, "")}/api`;
  }

  return "/api";
}

/** Display label for connection status (header tooltip). */
export const API_URL = getApiUrl();

function authHeaders(): Record<string, string> {
  const token =
    (import.meta.env["VITE_API_TOKEN"] as string | undefined)?.trim() ||
    (typeof process !== "undefined"
      ? (process.env["VITE_API_TOKEN"] as string | undefined)?.trim()
      : undefined);
  if (!token) return {};
  return { Authorization: `Bearer ${token}` };
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const base = getApiUrl();
  const res = await fetch(`${base}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
      ...(init?.headers ?? {}),
    },
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    let message = `${init?.method ?? "GET"} ${path} failed (${res.status})`;
    try {
      const errBody = JSON.parse(detail) as { detail?: string };
      if (errBody.detail) message = errBody.detail;
    } catch {
      if (detail) message += `: ${detail.slice(0, 200)}`;
    }
    throw new Error(message);
  }
  const type = res.headers.get("content-type") ?? "";
  const expectsText = path.endsWith(".md");
  if (expectsText) {
    if (type.includes("html")) throw new Error(`${path} did not return markdown`);
    return (await res.text()) as T;
  }
  if (!type.includes("json")) {
    throw new Error(`${path} did not return JSON`);
  }
  return (await res.json()) as T;
}

export async function getHealth(): Promise<{ status: string }> {
  return request<{ status: string }>("/health");
}

export async function listIncidents(): Promise<Incident[]> {
  const rows = await request<BackendIncident[]>("/incidents");
  return rows.map(mapBackendIncident);
}

export async function getIncident(id: string): Promise<Incident> {
  const raw = await request<BackendIncident>(`/incidents/${id}`);
  return mapBackendIncident(raw);
}

export async function createIncident(input: CreateIncidentInput): Promise<Incident> {
  const raw = await request<BackendIncident>("/incidents", {
    method: "POST",
    body: JSON.stringify(input),
  });
  return mapBackendIncident(raw);
}

export async function investigateIncident(id: string): Promise<Incident> {
  const raw = await request<BackendIncident>(`/incidents/${id}/investigate`, {
    method: "POST",
  });
  return mapBackendIncident(raw);
}

export async function approveAction(id: string, approvalId: string): Promise<Incident> {
  const raw = await request<BackendIncident>(`/incidents/${id}/approve`, {
    method: "POST",
    body: JSON.stringify({ approval_id: approvalId }),
  });
  return mapBackendIncident(raw);
}

export async function getPostmortem(id: string): Promise<string> {
  return request<string>(`/incidents/${id}/postmortem.md`);
}
