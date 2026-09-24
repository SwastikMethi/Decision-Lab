import { useQuery } from "@tanstack/react-query";
import type { Dataset, Manifest, Readiness, Summary } from "./types";

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch("/api/v1" + path, init);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const detail = body.detail;
    throw new Error(
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map((e: { msg: string }) => e.msg).join("; ")
          : "The request could not be completed.",
    );
  }
  return response.json();
}
export function post<T>(path: string, body: unknown = {}): Promise<T> {
  return request<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}
export const isTerminal = (status?: string) =>
  !!status && ["completed", "partial", "cancelled", "failed"].includes(status);
export const useRuns = () =>
  useQuery({
    queryKey: ["runs"],
    queryFn: () => request<{ items: Manifest[]; total: number }>("/runs"),
    refetchInterval: 3000,
  });
export const useDatasets = () =>
  useQuery({
    queryKey: ["datasets"],
    queryFn: () => request<{ items: Dataset[] }>("/datasets"),
  });
export const useReadiness = () =>
  useQuery({
    queryKey: ["readiness"],
    queryFn: () => request<Readiness>("/readiness"),
    refetchInterval: 15000,
  });
export const useRun = (id: string) =>
  useQuery({
    queryKey: ["run", id],
    queryFn: () => request<Manifest>("/runs/" + id),
    enabled: !!id,
    refetchInterval: (q) => (isTerminal(q.state.data?.status) ? false : 1000),
  });
export function filterQuery(params: URLSearchParams) {
  const result = new URLSearchParams();
  [
    "domain",
    "primitive",
    "variant",
    "split",
    "disagreement",
    "jev_correct",
    "laya_correct",
    "confidence_min",
    "confidence_max",
    "error_category",
    "q",
  ].forEach((key) => {
    if (params.has(key)) result.set(key, params.get(key)!);
  });
  return result.toString();
}
export const useSummary = (id: string, filters: string) =>
  useQuery({
    queryKey: ["summary", id, filters],
    queryFn: () => request<Summary>("/runs/" + id + "/summary?" + filters),
    enabled: !!id,
    staleTime: 3000,
  });
export const label = (text: string) =>
  text.replaceAll("_", " ").replace(/^./, (c) => c.toUpperCase());
export const systemName = (id: string) =>
  id.startsWith("jev") ? "Jev" : "Laya";
export const color = (id: string) =>
  id.startsWith("jev") ? "#6366f1" : "#0d9488";
export const pct = (value: number | null | undefined) =>
  value == null ? "Unavailable" : (value * 100).toFixed(1) + "%";
export const number = (value: number | null | undefined, digits = 2) =>
  value == null
    ? "Unavailable"
    : value.toLocaleString(undefined, { maximumFractionDigits: digits });
