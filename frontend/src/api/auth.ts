import { apiUrl } from "./config";
import type { LoginResponse } from "@/types/auth";

export type LoginCredentials = {
  email: string;
  password: string;
};

export async function loginRequest(credentials: LoginCredentials): Promise<LoginResponse> {
  const res = await fetch(apiUrl("/api/v1/auth/login"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(credentials),
  });

  const data = (await res.json().catch(() => ({}))) as Partial<LoginResponse> & {
    detail?: string | { msg?: string }[];
  };

  if (!res.ok) {
    let message = "No se pudo iniciar sesión.";
    if (typeof data.detail === "string") {
      message = data.detail;
    } else if (Array.isArray(data.detail) && data.detail[0]?.msg) {
      message = data.detail[0].msg;
    }
    throw new Error(message);
  }

  if (!data.access_token || !data.user) {
    throw new Error("Respuesta del servidor incompleta.");
  }

  return data as LoginResponse;
}
