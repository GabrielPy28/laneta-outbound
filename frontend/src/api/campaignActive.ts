import { apiUrl } from "./config";
import type { CampaignActiveGetResponse, CampaignActiveSetResponse } from "@/types/campaignActive";

async function authFetch(
  accessToken: string,
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  return fetch(apiUrl(path), {
    ...init,
    headers: {
      Authorization: `Bearer ${accessToken}`,
      Accept: "application/json",
      ...(init.headers as Record<string, string>),
    },
  });
}

export async function fetchCampaignActive(accessToken: string): Promise<CampaignActiveGetResponse> {
  const res = await authFetch(accessToken, "/api/v1/campaign-active");
  if (res.status === 401) {
    throw new Error("Sesión expirada o no válida.");
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const detail = typeof body.detail === "string" ? body.detail : `Error ${res.status}`;
    throw new Error(detail);
  }
  return res.json() as Promise<CampaignActiveGetResponse>;
}

export async function putCampaignActive(
  accessToken: string,
  idCampaign: string,
): Promise<CampaignActiveSetResponse> {
  const res = await authFetch(accessToken, "/api/v1/campaign-active", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id_campaign: idCampaign.trim() }),
  });
  if (res.status === 401) {
    throw new Error("Sesión expirada o no válida.");
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const detail = typeof body.detail === "string" ? body.detail : `Error ${res.status}`;
    throw new Error(detail);
  }
  return res.json() as Promise<CampaignActiveSetResponse>;
}
