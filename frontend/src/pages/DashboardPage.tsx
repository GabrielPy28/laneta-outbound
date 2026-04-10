import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import Swal from "sweetalert2";
import {
  FiChevronDown,
  FiFilter,
  FiInfo,
  FiLayers,
  FiRefreshCw,
  FiTarget,
} from "react-icons/fi";
import { fetchCampaignActive, putCampaignActive } from "@/api/campaignActive";
import {
  LEAD_PAGE_SIZES,
  type LeadPageSize,
  fetchLeads,
  type LeadListFilters,
} from "@/api/leads";
import { useAuth } from "@/contexts/AuthContext";
import { formatDateLongEs } from "@/lib/formatDateEs";
import { cn } from "@/lib/cn";
import type { LeadListItem } from "@/types/leads";

const emptyFilters: Record<keyof LeadListFilters, string> = {
  filter_name: "",
  filter_email: "",
  filter_company: "",
  filter_engagement: "",
  filter_campaign: "",
  filter_last_sequence: "",
};

function filtersToParams(f: Record<keyof LeadListFilters, string>): LeadListFilters {
  const out: LeadListFilters = {};
  (Object.keys(f) as (keyof LeadListFilters)[]).forEach((k) => {
    const v = f[k].trim();
    if (v) out[k] = v;
  });
  return out;
}

export function DashboardPage() {
  const { user, token, logout } = useAuth();
  const [leads, setLeads] = useState<LeadListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [effectiveCampaignId, setEffectiveCampaignId] = useState<string | null>(null);
  const [campaignLoading, setCampaignLoading] = useState(true);

  const [pageIndex, setPageIndex] = useState(0);
  const [pageSize, setPageSize] = useState<LeadPageSize>(25);
  const [draftFilters, setDraftFilters] = useState({ ...emptyFilters });
  const [appliedFilters, setAppliedFilters] = useState<LeadListFilters>({});

  const loadCampaign = useCallback(async () => {
    if (!token) return;
    setCampaignLoading(true);
    try {
      const data = await fetchCampaignActive(token);
      setEffectiveCampaignId(data.effective_id_campaign);
    } catch {
      setEffectiveCampaignId(null);
    } finally {
      setCampaignLoading(false);
    }
  }, [token]);

  const load = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      const data = await fetchLeads(token, {
        skip: pageIndex * pageSize,
        limit: pageSize,
        ...appliedFilters,
      });
      setLeads(data.items);
      setTotal(data.total);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "No se pudieron cargar los leads.";
      setError(msg);
      if (msg.includes("Sesión expirada")) {
        await Swal.fire({
          icon: "warning",
          title: "Sesión",
          text: msg,
          confirmButtonColor: "#6641ed",
          background: "#0f172a",
          color: "#f1f5f9",
        });
        logout();
      }
    } finally {
      setLoading(false);
    }
  }, [token, logout, pageIndex, pageSize, appliedFilters]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    void loadCampaign();
  }, [loadCampaign]);

  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const currentPageDisplay = Math.min(pageIndex + 1, totalPages);
  const canPrev = pageIndex > 0;
  const canNext = pageIndex + 1 < totalPages;

  function applyFilters() {
    setAppliedFilters(filtersToParams(draftFilters));
    setPageIndex(0);
  }

  function clearFilters() {
    setDraftFilters({ ...emptyFilters });
    setAppliedFilters({});
    setPageIndex(0);
  }

  function onPageSizeChange(size: LeadPageSize) {
    setPageSize(size);
    setPageIndex(0);
  }

  async function onChangeCampaign() {
    if (!token) return;
    const current = effectiveCampaignId ?? "";
    const { value, isConfirmed } = await Swal.fire({
      title: "Campaña para nuevos leads",
      html:
        "<p class='text-left text-sm text-slate-300 mb-3'>Este ID se usará cuando el sistema sincronice contactos nuevos desde HubSpot y los inserte en Smartlead. Los leads ya existentes conservan el <code class=\"text-pink\">campaign_id</code> guardado en su fila.</p>",
      input: "text",
      inputLabel: "ID de campaña Smartlead",
      inputValue: current,
      showCancelButton: true,
      confirmButtonText: "Guardar",
      cancelButtonText: "Cancelar",
      confirmButtonColor: "#6641ed",
      cancelButtonColor: "#334155",
      background: "#0f172a",
      color: "#f1f5f9",
      inputValidator: (v) => {
        if (!v || !String(v).trim()) {
          return "Ingresa un ID de campaña";
        }
        return undefined;
      },
    });
    if (!isConfirmed || value == null) return;
    try {
      const res = await putCampaignActive(token, String(value));
      setEffectiveCampaignId(res.effective_id_campaign);
      await Swal.fire({
        icon: "success",
        title: "Listo",
        text: `Campaña activa: ${res.id_campaign}`,
        confirmButtonColor: "#6641ed",
        background: "#0f172a",
        color: "#f1f5f9",
      });
    } catch (e) {
      const msg = e instanceof Error ? e.message : "No se pudo guardar.";
      await Swal.fire({
        icon: "error",
        title: "Error",
        text: msg,
        confirmButtonColor: "#6641ed",
        background: "#0f172a",
        color: "#f1f5f9",
      });
    }
  }

  const filterField = (
    key: keyof LeadListFilters,
    label: string,
    placeholder: string,
  ) => (
    <label key={key} className="block">
      <span className="mb-1 block text-xs font-medium text-slate-300">{label}</span>
      <input
        type="text"
        value={draftFilters[key]}
        onChange={(e) => setDraftFilters((p) => ({ ...p, [key]: e.target.value }))}
        placeholder={placeholder}
        className="w-full rounded-lg border border-white/15 bg-dark/80 px-3 py-2 text-sm text-white placeholder:text-slate-600 outline-none focus:border-purple/50 focus:ring-1 focus:ring-purple/40"
      />
    </label>
  );

  return (
    <div className="min-h-screen bg-dark p-4 md:p-8">
      <header className="mx-auto flex max-w-[1600px] flex-col gap-4 border-b border-white/10 pb-6 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-sm font-medium text-blue">La Neta — Trazabilidad</p>
          <h1 className="text-2xl font-bold text-white">Leads en secuencia</h1>
          <p className="mt-1 text-sm text-slate-400">{user?.name}</p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={() => {
              void load();
              void loadCampaign();
            }}
            disabled={loading}
            className={cn(
              "inline-flex items-center gap-2 rounded-xl border border-purple/40 bg-purple/15 px-4 py-2 text-sm font-medium text-white",
              "transition hover:bg-purple/25 disabled:opacity-50",
            )}
          >
            <FiRefreshCw className={cn("h-4 w-4", loading && "animate-spin")} aria-hidden />
            Actualizar
          </button>
          <button
            type="button"
            onClick={logout}
            className="rounded-xl border border-white/15 bg-white/5 px-4 py-2 text-sm font-medium text-white transition hover:bg-white/10"
          >
            Cerrar sesión
          </button>
        </div>
      </header>

      <main className="mx-auto mt-8 max-w-[1600px] space-y-8">
        <section className="grid gap-4 lg:grid-cols-3">
          <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-5 lg:col-span-2">
            <div className="mb-3 flex items-center gap-2 text-blue">
              <FiInfo className="h-5 w-5" aria-hidden />
              <h2 className="text-sm font-semibold uppercase tracking-wide">¿Qué es esta vista?</h2>
            </div>
            <p className="text-sm leading-relaxed text-slate-300">
              Es el panel operativo para seguir el recorrido de tus prospectos en las secuencias de
              email (Smartlead) y cómo se reflejan en el CRM (HubSpot). Aquí ves un snapshot de la
              base local: estado de secuencia, engagement reciente, campaña asignada y métricas de
              correo.
            </p>
            <ul className="mt-4 space-y-2 text-sm text-slate-300">
              <li className="flex gap-2">
                <FiLayers className="mt-0.5 h-4 w-4 shrink-0 text-purple" aria-hidden />
                <span>
                  Cada fila es un <strong className="text-white">lead</strong> ya sincronizado; la
                  columna <em className="text-blue">Campaña</em> es el ID de secuencia en Smartlead
                  asociado a ese contacto.
                </span>
              </li>
              <li className="flex gap-2">
                <FiTarget className="mt-0.5 h-4 w-4 shrink-0 text-pink" aria-hidden />
                <span>
                  Usa esta tabla para priorizar seguimiento: respuestas, clics y paso actual del
                  guion de mensajes.
                </span>
              </li>
            </ul>
          </div>

          <div className="rounded-2xl border border-purple/20 bg-gradient-to-br from-purple/10 to-blue/5 p-5">
            <h2 className="text-sm font-semibold text-white">Campaña para nuevas altas</h2>
            <p className="mt-2 text-xs leading-relaxed text-slate-300">
              Al correr la sincronización HubSpot → Smartlead, los contactos nuevos se inscriben en
              esta campaña (configurable abajo).
            </p>
            <p className="mt-4 font-mono text-lg font-semibold text-white">
              {campaignLoading ? "…" : (effectiveCampaignId ?? "—")}
            </p>
            <button
              type="button"
              onClick={() => void onChangeCampaign()}
              className="mt-4 w-full rounded-xl bg-brand-gradient py-2.5 text-sm font-semibold text-white shadow-lg shadow-purple/20 transition hover:opacity-95"
            >
              Cambiar ID de campaña activa
            </button>
          </div>
        </section>

        <details className="group rounded-2xl border border-white/10 bg-slate-800/50 shadow-inner">
          <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-5 py-4 text-sm font-semibold text-slate-100 transition hover:bg-white/[0.04] [&::-webkit-details-marker]:hidden">
            <span>Cómo leer la tabla</span>
            <FiChevronDown
              className="h-5 w-5 shrink-0 text-blue transition-transform group-open:rotate-180"
              aria-hidden
            />
          </summary>
          <div className="border-t border-white/10 px-5 pb-5 pt-4">
            <dl className="grid gap-4 text-sm sm:grid-cols-2 lg:grid-cols-3">
              <div>
                <dt className="font-semibold text-blue">Secuencia</dt>
                <dd className="mt-1 leading-relaxed text-slate-200">
                  Estado del lead en la secuencia (p. ej. active, completed, paused).
                </dd>
              </div>
              <div>
                <dt className="font-semibold text-blue">Engagement</dt>
                <dd className="mt-1 leading-relaxed text-slate-200">
                  Resumen del último tipo de interacción detectado (apertura, clic, respuesta…).
                </dd>
              </div>
              <div>
                <dt className="font-semibold text-blue">Aperturas · Clics · Respuestas</dt>
                <dd className="mt-1 leading-relaxed text-slate-200">
                  Cuántas veces abrió el correo, hizo clic y respondió.
                </dd>
              </div>
              <div>
                <dt className="font-semibold text-blue">Última secuencia de mensaje</dt>
                <dd className="mt-1 leading-relaxed text-slate-200">
                  Identificador o paso del último mensaje de la secuencia aplicado al lead.
                </dd>
              </div>
              <div>
                <dt className="font-semibold text-blue">Actualizado</dt>
                <dd className="mt-1 leading-relaxed text-slate-200">
                  Última vez que se modificó el registro en esta base de datos.
                </dd>
              </div>
            </dl>
          </div>
        </details>

        <details className="group rounded-2xl border border-white/10 bg-slate-800/50 shadow-inner">
          <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-5 py-4 text-sm font-semibold text-slate-100 transition hover:bg-white/[0.04] [&::-webkit-details-marker]:hidden">
            <span className="flex flex-wrap items-center gap-2">
              <FiFilter className="h-5 w-5 shrink-0 text-purple" aria-hidden />
              Filtrar resultados
              {Object.keys(appliedFilters).length > 0 && (
                <span className="rounded-full bg-purple/25 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-purple-200">
                  {Object.keys(appliedFilters).length} activo
                  {Object.keys(appliedFilters).length !== 1 ? "s" : ""}
                </span>
              )}
            </span>
            <FiChevronDown
              className="h-5 w-5 shrink-0 text-blue transition-transform group-open:rotate-180"
              aria-hidden
            />
          </summary>
          <div className="border-t border-white/10 px-5 pb-5 pt-4">
            <p className="mb-4 text-xs leading-relaxed text-slate-300">
              Coincidencia parcial, sin distinguir mayúsculas. Pulsa{" "}
              <strong className="text-white">Aplicar filtros</strong> para buscar.
            </p>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {filterField("filter_name", "Nombre", "Nombre o apellido")}
              {filterField("filter_email", "Email", "correo@…")}
              {filterField("filter_company", "Empresa", "Nombre empresa")}
              {filterField("filter_engagement", "Engagement", "p. ej. REPLIED")}
              {filterField("filter_campaign", "Campaña", "ID campaña")}
              {filterField(
                "filter_last_sequence",
                "Última secuencia de mensaje",
                "Paso o texto del mensaje",
              )}
            </div>
            <div className="mt-4 flex flex-wrap gap-3">
              <button
                type="button"
                onClick={applyFilters}
                className="rounded-xl bg-purple px-5 py-2 text-sm font-semibold text-white shadow-md shadow-purple/30 hover:opacity-95"
              >
                Aplicar filtros
              </button>
              <button
                type="button"
                onClick={clearFilters}
                className="rounded-xl border border-white/20 bg-white/5 px-5 py-2 text-sm font-medium text-slate-200 hover:bg-white/10"
              >
                Limpiar
              </button>
            </div>
          </div>
        </details>

        {error && !loading && (
          <div className="rounded-xl border border-pink/30 bg-pink/10 px-4 py-3 text-sm text-pink-100">
            {error}
          </div>
        )}

        <div className="flex flex-col gap-4 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between">
          <p className="text-sm text-slate-300">
            {loading ? (
              "Cargando…"
            ) : (
              <>
                <span className="font-medium text-white">{leads.length}</span> en esta página ·{" "}
                <span className="font-medium text-white">{total}</span> resultados
                {Object.keys(appliedFilters).length > 0 ? " (filtrados)" : " (total)"}
              </>
            )}
          </p>
          <div className="flex flex-wrap items-center gap-3">
            <label className="flex items-center gap-2 text-sm text-slate-300">
              <span>Por página</span>
              <select
                value={pageSize}
                onChange={(e) => onPageSizeChange(Number(e.target.value) as LeadPageSize)}
                className="rounded-lg border border-white/15 bg-dark px-3 py-2 text-sm text-white outline-none focus:border-purple/50"
              >
                {LEAD_PAGE_SIZES.map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </select>
            </label>
            <div className="flex items-center gap-2">
              <button
                type="button"
                disabled={!canPrev || loading}
                onClick={() => setPageIndex((p) => Math.max(0, p - 1))}
                className="rounded-lg border border-white/15 px-3 py-2 text-sm text-white disabled:opacity-40 hover:bg-white/10"
              >
                Anterior
              </button>
              <span className="min-w-[120px] text-center text-sm text-slate-300">
                Página {currentPageDisplay} de {totalPages}
              </span>
              <button
                type="button"
                disabled={!canNext || loading}
                onClick={() => setPageIndex((p) => p + 1)}
                className="rounded-lg border border-white/15 px-3 py-2 text-sm text-white disabled:opacity-40 hover:bg-white/10"
              >
                Siguiente
              </button>
            </div>
          </div>
        </div>

        <div className="overflow-x-auto rounded-2xl border border-white/10 bg-slate-900/40 shadow-xl">
          <table className="w-full min-w-[1180px] border-collapse text-left text-sm">
            <thead>
              <tr className="border-b border-white/10 bg-white/[0.04] text-xs font-semibold uppercase tracking-wide text-slate-400">
                <th className="px-3 py-3">Email</th>
                <th className="px-3 py-3">Nombre</th>
                <th className="px-3 py-3">Empresa</th>
                <th className="px-3 py-3">Secuencia</th>
                <th className="px-3 py-3">Engagement</th>
                <th className="px-3 py-3">Campaña</th>
                <th className="px-3 py-3 text-center align-bottom">
                  <div>Interacción email</div>
                  <div className="mt-1 text-[10px] font-normal normal-case leading-snug text-slate-500">
                    Aperturas · Clics · Respuestas
                  </div>
                </th>
                <th className="min-w-[140px] px-3 py-3 align-bottom normal-case">
                  Última secuencia de mensaje
                </th>
                <th className="min-w-[220px] px-3 py-3 align-bottom">Actualizado</th>
                <th className="whitespace-nowrap px-3 py-3 text-center normal-case">Ver actividad</th>
              </tr>
            </thead>
            <tbody>
              {loading && leads.length === 0 ? (
                <tr>
                  <td colSpan={10} className="px-4 py-12 text-center text-slate-500">
                    Cargando leads…
                  </td>
                </tr>
              ) : leads.length === 0 ? (
                <tr>
                  <td colSpan={10} className="px-4 py-12 text-center text-slate-500">
                    No hay leads que coincidan con los filtros o la página está vacía.
                  </td>
                </tr>
              ) : (
                leads.map((row) => {
                  const name = [row.first_name, row.last_name].filter(Boolean).join(" ") || "—";
                  return (
                    <tr
                      key={row.id}
                      className="border-b border-white/5 transition hover:bg-white/[0.03]"
                    >
                      <td className="max-w-[200px] truncate px-3 py-2.5 font-medium text-white">
                        {row.email}
                      </td>
                      <td className="max-w-[140px] truncate px-3 py-2.5 text-slate-300">{name}</td>
                      <td className="max-w-[140px] truncate px-3 py-2.5 text-slate-400">
                        {row.company_name ?? "—"}
                      </td>
                      <td className="px-3 py-2.5">
                        <span className="rounded-lg bg-blue/15 px-2 py-0.5 text-xs text-blue">
                          {row.sequence_status ?? "—"}
                        </span>
                      </td>
                      <td className="px-3 py-2.5 text-slate-400">
                        {row.engagement_status ?? "—"}
                      </td>
                      <td className="max-w-[100px] truncate px-3 py-2.5 font-mono text-xs text-slate-500">
                        {row.campaign_id ?? "—"}
                      </td>
                      <td
                        className="px-3 py-2.5 text-center font-mono text-xs text-slate-300"
                        title="Aperturas de email / Clics en enlaces / Respuestas recibidas"
                      >
                        <span className="text-slate-500">{row.total_opens}</span>
                        <span className="mx-1 text-slate-600">/</span>
                        <span className="text-slate-500">{row.total_clicks}</span>
                        <span className="mx-1 text-slate-600">/</span>
                        <span className="text-slate-500">{row.total_replies}</span>
                      </td>
                      <td className="max-w-[180px] truncate px-3 py-2.5 text-slate-400">
                        {row.last_sequence_step ?? "—"}
                      </td>
                      <td className="px-3 py-2.5 text-sm leading-snug text-slate-300">
                        {formatDateLongEs(row.updated_at)}
                      </td>
                      <td className="px-3 py-2.5 text-center">
                        <Link
                          to={`/leads/${row.id}/actividad`}
                          className="inline-flex rounded-lg border border-purple/40 bg-purple/15 px-3 py-1.5 text-xs font-semibold text-purple-200 transition hover:bg-purple/25 hover:text-white"
                        >
                          Ver actividad
                        </Link>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </main>
    </div>
  );
}
