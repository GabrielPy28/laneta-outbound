import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  FiArrowLeft,
  FiAward,
  FiChevronRight,
  FiEye,
  FiMessageCircle,
  FiMessageSquare,
  FiMousePointer,
} from "react-icons/fi";
import { fetchLeadActivity } from "@/api/leadActivity";
import { useAuth } from "@/contexts/AuthContext";
import { cn } from "@/lib/cn";
import type { LeadActivityResponse, LeadMessageActivity } from "@/types/leadActivity";
import type { IconType } from "react-icons";

type KpiAccent = "purple" | "blue" | "pink";

const accentBar: Record<KpiAccent, string> = {
  purple: "border-t-purple bg-gradient-to-br from-purple/[0.12] via-slate-900/80 to-slate-950/90 shadow-[0_8px_30px_-8px_rgba(102,65,237,0.35)]",
  blue: "border-t-blue bg-gradient-to-br from-blue/[0.12] via-slate-900/80 to-slate-950/90 shadow-[0_8px_30px_-8px_rgba(121,188,247,0.3)]",
  pink: "border-t-pink bg-gradient-to-br from-pink/[0.1] via-slate-900/80 to-slate-950/90 shadow-[0_8px_30px_-8px_rgba(255,71,172,0.25)]",
};

const accentIconWrap: Record<KpiAccent, string> = {
  purple: "bg-purple/25 text-purple ring-1 ring-purple/40",
  blue: "bg-blue/25 text-blue ring-1 ring-blue/40",
  pink: "bg-pink/25 text-pink ring-1 ring-pink/40",
};

function KpiCard({
  label,
  value,
  icon: Icon,
  accent,
}: {
  label: string;
  value: string | number;
  icon: IconType;
  accent: KpiAccent;
}) {
  const isNumber = typeof value === "number";
  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-2xl border border-white/10 border-t-4 p-5 transition hover:border-white/15",
        accentBar[accent],
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-slate-300">
            {label}
          </p>
          <p
            className={cn(
              "mt-2 font-bold tracking-tight text-white",
              isNumber ? "text-3xl tabular-nums" : "text-lg leading-snug",
            )}
          >
            {value}
          </p>
        </div>
        <div
          className={cn(
            "flex h-12 w-12 shrink-0 items-center justify-center rounded-xl",
            accentIconWrap[accent],
          )}
          aria-hidden
        >
          <Icon className="h-6 w-6" strokeWidth={2} />
        </div>
      </div>
    </div>
  );
}

function formatChatTime(iso: string | null): string {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleString("es", {
      dateStyle: "short",
      timeStyle: "short",
    });
  } catch {
    return iso;
  }
}

function ChatBubble({ message }: { message: LeadMessageActivity }) {
  const dir = message.direction.toLowerCase();
  const isOutbound = dir === "outbound";
  const isInbound = dir === "inbound";
  const when = formatChatTime(message.sent_at || message.received_at || message.created_at);
  const hasHtml = Boolean(message.email_body?.trim());

  return (
    <div
      className={cn(
        "flex w-full max-w-[min(100%,42rem)] flex-col gap-1",
        isOutbound && "ml-auto items-end",
        isInbound && "mr-auto items-start",
        !isOutbound && !isInbound && "mx-auto items-center",
      )}
    >
      <div
        className={cn(
          "rounded-2xl border px-4 py-3 shadow-sm",
          isOutbound && "border-purple/40 bg-purple/20 text-slate-100",
          isInbound && "border-white/15 bg-slate-800/90 text-slate-100",
          !isOutbound && !isInbound && "border-white/10 bg-white/5 text-slate-400",
        )}
      >
        {message.subject && (
          <p className="mb-2 text-sm font-semibold text-white">{message.subject}</p>
        )}
        {message.reply_intent && (
          <span className="mb-2 inline-block rounded-md bg-pink/20 px-2 py-0.5 text-xs text-pink-200">
            {message.reply_intent}
          </span>
        )}
        {hasHtml ? (
          <div
            className="max-h-80 overflow-y-auto text-sm leading-relaxed [&_a]:text-blue [&_img]:max-w-full"
            dangerouslySetInnerHTML={{ __html: message.email_body ?? "" }}
          />
        ) : (
          <p className="text-sm text-slate-400 italic">Sin cuerpo de mensaje.</p>
        )}
      </div>
      <div className="flex flex-wrap items-center gap-2 px-1 text-[11px] text-slate-500">
        <span className="uppercase tracking-wide">{message.direction}</span>
        {when && <span>· {when}</span>}
        {message.opened_at && (
          <span className="text-blue/80">Abierto {formatChatTime(message.opened_at)}</span>
        )}
      </div>
    </div>
  );
}

export function LeadActivityPage() {
  const { leadId } = useParams<{ leadId: string }>();
  const { token, logout } = useAuth();
  const navigate = useNavigate();
  const [data, setData] = useState<LeadActivityResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!token || !leadId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetchLeadActivity(token, leadId);
      setData(res);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Error al cargar actividad.";
      setError(msg);
      if (msg.includes("Sesión expirada")) {
        logout();
        navigate("/login", { replace: true });
      }
    } finally {
      setLoading(false);
    }
  }, [token, leadId, logout, navigate]);

  useEffect(() => {
    void load();
  }, [load]);

  const s = data?.statistics;

  return (
    <div className="min-h-screen bg-dark">
      <header className="border-b border-white/10 bg-slate-900/40 px-4 py-4 md:px-8">
        <div className="mx-auto flex max-w-5xl flex-col gap-3">
          <button
            type="button"
            onClick={() => navigate(-1)}
            className="inline-flex w-fit items-center gap-2 text-sm text-slate-400 transition hover:text-white"
          >
            <FiArrowLeft className="h-4 w-4" aria-hidden />
            Volver al listado
          </button>
          <nav
            className="flex flex-wrap items-center gap-2 text-sm text-slate-400"
            aria-label="Migas de pan"
          >
            <Link to="/" className="font-medium text-blue transition hover:text-blue/80">
              Leads
            </Link>
            <FiChevronRight className="h-4 w-4 shrink-0 text-slate-600" aria-hidden />
            <span className="font-semibold text-white">
              {data?.lead.display_name ?? (loading ? "…" : "Lead")}
            </span>
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-5xl space-y-8 px-4 py-8 md:px-8">
        {loading && (
          <p className="text-center text-slate-500">Cargando actividad…</p>
        )}
        {error && !loading && (
          <div className="rounded-xl border border-pink/30 bg-pink/10 px-4 py-3 text-sm text-pink-100">
            {error}
          </div>
        )}

        {!loading && !error && data && (
          <>
            <section className="rounded-2xl border border-white/10 bg-slate-900/30 p-6 shadow-inner ring-1 ring-white/5 md:p-8">
              <div className="mb-6 flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
                <div>
                  <h2 className="text-xl font-bold tracking-tight text-white md:text-2xl">
                    Indicadores del lead
                  </h2>
                  <p className="mt-1 text-sm text-slate-400">
                    Datos sincronizados desde{" "}
                    <span className="font-medium text-blue">lead_statistics</span> (Smartlead)
                  </p>
                </div>
                <span className="inline-flex w-fit items-center rounded-full border border-purple/30 bg-purple/15 px-3 py-1 text-xs font-semibold text-purple-200">
                  KPI en vivo
                </span>
              </div>
              {s ? (
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                  <KpiCard
                    label="Aperturas"
                    value={s.total_opens}
                    icon={FiEye}
                    accent="purple"
                  />
                  <KpiCard
                    label="Clics"
                    value={s.total_clicks}
                    icon={FiMousePointer}
                    accent="blue"
                  />
                  <KpiCard
                    label="Respuestas"
                    value={s.total_replies}
                    icon={FiMessageSquare}
                    accent="pink"
                  />
                  <KpiCard
                    label="Lead score"
                    value={s.lead_score ?? "—"}
                    icon={FiAward}
                    accent="purple"
                  />
                </div>
              ) : (
                <p className="rounded-xl border border-white/10 bg-slate-900/30 px-4 py-6 text-center text-sm text-slate-400">
                  Aún no hay fila en <code className="text-purple">lead_statistics</code> para este
                  lead. Se crea al sincronizar el export de Smartlead.
                </p>
              )}
            </section>

            <section>
              <h2 className="mb-4 flex items-center gap-2 text-lg font-bold text-white">
                <FiMessageCircle className="h-5 w-5 text-blue" aria-hidden />
                Historial de mensajes
              </h2>
              <div className="flex min-h-[200px] flex-col gap-4 rounded-2xl border border-white/10 bg-slate-900/40 p-4 md:p-6">
                {data.messages.length === 0 ? (
                  <p className="py-8 text-center text-sm text-slate-500">
                    No hay mensajes en <code className="text-slate-400">lead_message_history</code>.
                  </p>
                ) : (
                  data.messages.map((m) => <ChatBubble key={m.id} message={m} />)
                )}
              </div>
            </section>
          </>
        )}
      </main>
    </div>
  );
}
