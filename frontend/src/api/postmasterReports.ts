import { apiUrl } from "./config";
import type { PostmasterReportDetail, PostmasterReportListItem } from "@/types/postmasterReports";

function errorMessage(status: number, detail: unknown, fallback: string): string {
  if (typeof detail === "string" && detail.trim() !== "") return detail;
  return `${fallback} (HTTP ${status})`;
}

export async function fetchPostmasterReports(
  accessToken: string,
  limit = 25,
): Promise<PostmasterReportListItem[]> {
  const res = await fetch(apiUrl(`/api/v1/postmaster/reports?limit=${limit}`), {
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
    throw new Error(errorMessage(res.status, body.detail, "No se pudieron cargar los reportes."));
  }
  return res.json() as Promise<PostmasterReportListItem[]>;
}

export async function fetchPostmasterReportDetail(
  accessToken: string,
  reportId: string,
): Promise<PostmasterReportDetail> {
  const res = await fetch(apiUrl(`/api/v1/postmaster/reports/${reportId}`), {
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
    throw new Error(errorMessage(res.status, body.detail, "No se pudo cargar el detalle del reporte."));
  }
  return res.json() as Promise<PostmasterReportDetail>;
}
