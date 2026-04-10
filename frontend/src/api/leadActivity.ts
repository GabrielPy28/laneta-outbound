import { apiUrl } from "./config";
import type { LeadActivityResponse } from "@/types/leadActivity";

export async function fetchLeadActivity(
  accessToken: string,
  leadId: string,
): Promise<LeadActivityResponse> {
  const res = await fetch(apiUrl(`/api/v1/leads/${encodeURIComponent(leadId)}/activity`), {
    headers: {
      Authorization: `Bearer ${accessToken}`,
      Accept: "application/json",
    },
  });

  if (res.status === 401) {
    throw new Error("Sesión expirada o no válida.");
  }
  if (res.status === 404) {
    throw new Error("Lead no encontrado.");
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const detail = typeof body.detail === "string" ? body.detail : `Error ${res.status}`;
    throw new Error(detail);
  }

  return res.json() as Promise<LeadActivityResponse>;
}
