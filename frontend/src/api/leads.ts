import { apiUrl } from "./config";
import type { LeadListResponse } from "@/types/leads";

export const LEAD_PAGE_SIZES = [25, 50, 100] as const;
export type LeadPageSize = (typeof LEAD_PAGE_SIZES)[number];

export type LeadListFilters = {
  filter_name?: string;
  filter_email?: string;
  filter_company?: string;
  filter_engagement?: string;
  filter_campaign?: string;
  filter_last_sequence?: string;
};

export type FetchLeadsParams = {
  skip?: number;
  limit?: LeadPageSize;
} & LeadListFilters;

export async function fetchLeads(
  accessToken: string,
  params: FetchLeadsParams = {},
): Promise<LeadListResponse> {
  const search = new URLSearchParams();
  if (params.skip != null) search.set("skip", String(params.skip));
  if (params.limit != null) search.set("limit", String(params.limit));

  const filterKeys: (keyof LeadListFilters)[] = [
    "filter_name",
    "filter_email",
    "filter_company",
    "filter_engagement",
    "filter_campaign",
    "filter_last_sequence",
  ];
  for (const key of filterKeys) {
    const v = params[key];
    if (v != null && String(v).trim() !== "") {
      search.set(key, String(v).trim());
    }
  }

  const qs = search.toString();
  const path = qs ? `/api/v1/leads?${qs}` : "/api/v1/leads";

  const res = await fetch(apiUrl(path), {
    headers: {
      Authorization: `Bearer ${accessToken}`,
      Accept: "application/json",
    },
  });

  if (res.status === 401) {
    throw new Error("Sesión expirada o no válida. Vuelve a iniciar sesión.");
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const detail =
      typeof body.detail === "string"
        ? body.detail
        : `Error ${res.status} al cargar leads.`;
    throw new Error(detail);
  }

  return res.json() as Promise<LeadListResponse>;
}
