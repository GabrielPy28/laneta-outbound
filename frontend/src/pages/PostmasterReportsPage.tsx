import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import Swal from "sweetalert2";
import { FiArrowLeft, FiMail, FiRefreshCw } from "react-icons/fi";
import { fetchPostmasterReportDetail, fetchPostmasterReports } from "@/api/postmasterReports";
import { useAuth } from "@/contexts/AuthContext";
import { formatDateLongEs } from "@/lib/formatDateEs";
import { cn } from "@/lib/cn";
import type { PostmasterReportDetail, PostmasterReportListItem } from "@/types/postmasterReports";

export function PostmasterReportsPage() {
  const { token, logout } = useAuth();
  const [reports, setReports] = useState<PostmasterReportListItem[]>([]);
  const [selected, setSelected] = useState<PostmasterReportDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSessionError = useCallback(
    async (msg: string) => {
      if (!msg.includes("Sesión expirada")) return;
      await Swal.fire({
        icon: "warning",
        title: "Sesión",
        text: msg,
        confirmButtonColor: "#6641ed",
        background: "#0f172a",
        color: "#f1f5f9",
      });
      logout();
    },
    [logout],
  );

  const loadReports = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      const items = await fetchPostmasterReports(token, 50);
      setReports(items);
      if (items.length > 0) {
        setDetailLoading(true);
        const detail = await fetchPostmasterReportDetail(token, items[0].id);
        setSelected(detail);
      } else {
        setSelected(null);
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : "No se pudieron cargar reportes.";
      setError(msg);
      await handleSessionError(msg);
    } finally {
      setLoading(false);
      setDetailLoading(false);
    }
  }, [token, handleSessionError]);

  useEffect(() => {
    void loadReports();
  }, [loadReports]);

  async function onSelectReport(reportId: string) {
    if (!token) return;
    setDetailLoading(true);
    setError(null);
    try {
      const detail = await fetchPostmasterReportDetail(token, reportId);
      setSelected(detail);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "No se pudo cargar detalle del reporte.";
      setError(msg);
      await handleSessionError(msg);
    } finally {
      setDetailLoading(false);
    }
  }

  const rows = selected?.payload.results ?? [];
  const errors = selected?.payload.errors ?? [];

  return (
    <div className="min-h-screen bg-dark p-4 md:p-8">
      <header className="mx-auto flex max-w-[1600px] flex-wrap items-center justify-between gap-3 border-b border-white/10 pb-5">
        <div>
          <p className="text-sm font-medium text-blue">Google Postmaster</p>
          <h1 className="text-2xl font-bold text-white">Historial de reportes</h1>
        </div>
        <div className="flex items-center gap-2">
          <Link
            to="/"
            className="inline-flex items-center gap-2 rounded-xl border border-white/15 bg-white/5 px-4 py-2 text-sm font-medium text-white transition hover:bg-white/10"
          >
            <FiArrowLeft className="h-4 w-4" aria-hidden />
            Volver al dashboard
          </Link>
          <button
            type="button"
            onClick={() => void loadReports()}
            className="inline-flex items-center gap-2 rounded-xl border border-purple/40 bg-purple/15 px-4 py-2 text-sm font-medium text-white transition hover:bg-purple/25"
          >
            <FiRefreshCw className={cn("h-4 w-4", loading && "animate-spin")} aria-hidden />
            Actualizar
          </button>
        </div>
      </header>

      <main className="mx-auto mt-6 grid max-w-[1600px] gap-6 lg:grid-cols-[360px_1fr]">
        <section className="rounded-2xl border border-white/10 bg-slate-900/40">
          <div className="border-b border-white/10 px-4 py-3 text-sm font-semibold text-slate-100">
            Reportes guardados
          </div>
          {loading ? (
            <p className="px-4 py-8 text-sm text-slate-400">Cargando…</p>
          ) : reports.length === 0 ? (
            <p className="px-4 py-8 text-sm text-slate-400">Aún no hay reportes persistidos.</p>
          ) : (
            <ul className="max-h-[75vh] overflow-y-auto">
              {reports.map((r) => (
                <li key={r.id} className="border-b border-white/5 last:border-b-0">
                  <button
                    type="button"
                    onClick={() => void onSelectReport(r.id)}
                    className={cn(
                      "w-full px-4 py-3 text-left transition hover:bg-white/[0.04]",
                      selected?.id === r.id && "bg-purple/15",
                    )}
                  >
                    <p className="text-xs text-slate-400">{formatDateLongEs(r.created_at)}</p>
                    <p className="mt-1 text-sm font-semibold text-white">
                      {r.results_count} OK · {r.errors_count} errores
                    </p>
                    <p className="mt-1 text-xs text-slate-300">Dominios solicitados: {r.domains_requested}</p>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="rounded-2xl border border-white/10 bg-slate-900/40 p-5">
          {error && <div className="mb-4 rounded-lg bg-pink/10 px-3 py-2 text-sm text-pink-100">{error}</div>}
          {!selected ? (
            <p className="text-sm text-slate-400">Selecciona un reporte para ver su detalle.</p>
          ) : (
            <div className="space-y-5">
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                <div className="rounded-xl border border-white/10 bg-white/[0.03] p-3">
                  <p className="text-xs text-slate-400">Fecha de ejecución</p>
                  <p className="text-sm font-semibold text-white">{formatDateLongEs(selected.created_at)}</p>
                </div>
                <div className="rounded-xl border border-white/10 bg-white/[0.03] p-3">
                  <p className="text-xs text-slate-400">Dominios solicitados</p>
                  <p className="text-sm font-semibold text-white">{selected.domains_requested}</p>
                </div>
                <div className="rounded-xl border border-white/10 bg-white/[0.03] p-3">
                  <p className="text-xs text-slate-400">Resultados exitosos</p>
                  <p className="text-sm font-semibold text-emerald-300">{selected.results_count}</p>
                </div>
                <div className="rounded-xl border border-white/10 bg-white/[0.03] p-3">
                  <p className="text-xs text-slate-400">Errores</p>
                  <p className="text-sm font-semibold text-rose-300">{selected.errors_count}</p>
                </div>
              </div>

              <div className="rounded-xl border border-white/10 bg-white/[0.03] p-3 text-sm text-slate-200">
                <p className="inline-flex items-center gap-2 text-xs text-slate-400">
                  <FiMail className="h-4 w-4" aria-hidden />
                  Estado de envío correo
                </p>
                <p className="mt-1">
                  {selected.email_sent ? "Enviado" : "No enviado"}
                  {selected.email_to ? ` · ${selected.email_to}` : ""}
                </p>
                {selected.email_error && <p className="mt-1 text-rose-300">{selected.email_error}</p>}
              </div>

              <div>
                <h2 className="mb-2 text-sm font-semibold text-slate-100">Resultados por dominio</h2>
                {detailLoading ? (
                  <p className="text-sm text-slate-400">Cargando detalle…</p>
                ) : rows.length === 0 ? (
                  <p className="text-sm text-slate-400">Este reporte no tiene resultados exitosos.</p>
                ) : (
                  <div className="overflow-x-auto rounded-xl border border-white/10">
                    <table className="w-full min-w-[760px] text-left text-sm">
                      <thead className="bg-white/[0.04] text-xs uppercase tracking-wide text-slate-400">
                        <tr>
                          <th className="px-3 py-2">Dominio</th>
                          <th className="px-3 py-2">Estado</th>
                          <th className="px-3 py-2">Score</th>
                          <th className="px-3 py-2">Acción</th>
                          <th className="px-3 py-2">Fecha de referencia</th>
                          <th className="px-3 py-2">Resumen</th>
                        </tr>
                      </thead>
                      <tbody>
                        {rows.map((row, i) => (
                          <tr key={`${row.domain ?? "row"}-${i}`} className="border-t border-white/5 text-slate-200">
                            <td className="px-3 py-2 font-medium text-white">{row.domain ?? "—"}</td>
                            <td className="px-3 py-2">{row.status ?? "—"}</td>
                            <td className="px-3 py-2">{row.score ?? "—"}</td>
                            <td className="px-3 py-2">{row.action ?? "—"}</td>
                            <td className="px-3 py-2">{row.evaluated_date ?? "—"}</td>
                            <td className="px-3 py-2">{row.summary ?? "—"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>

              <div>
                <h2 className="mb-2 text-sm font-semibold text-slate-100">Errores del reporte</h2>
                {errors.length === 0 ? (
                  <p className="text-sm text-slate-400">Sin errores en esta ejecución.</p>
                ) : (
                  <ul className="space-y-2">
                    {errors.map((e, i) => (
                      <li key={`${e.domain ?? "err"}-${i}`} className="rounded-lg bg-rose-950/30 px-3 py-2 text-sm text-rose-200">
                        <strong>{e.domain ?? "Dominio desconocido"}:</strong> {e.error ?? "Error sin detalle"}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
