import { motion } from "framer-motion";
import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import Swal from "sweetalert2";
import {
  FiActivity,
  FiLayers,
  FiMail,
  FiLock,
  FiTrendingUp,
} from "react-icons/fi";
import { useAuth } from "@/contexts/AuthContext";
import { cn } from "@/lib/cn";

const features = [
  {
    icon: FiLayers,
    title: "Campañas en un solo lugar",
    text: "Visualiza el estado de tus secuencias outbound y el vínculo con HubSpot y Smartlead.",
  },
  {
    icon: FiActivity,
    title: "Trazabilidad por lead",
    text: "Sigue aperturas, clics, respuestas y el paso actual de la secuencia con contexto unificado.",
  },
  {
    icon: FiTrendingUp,
    title: "Operación alineada al CRM",
    text: "La herramienta refleja lo que ocurre en el terreno para priorizar seguimiento y ventas.",
  },
];

export function LoginPage() {
  const { login, isLoading } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    try {
      const loggedUser = await login(email.trim(), password);
      await Swal.fire({
        icon: "success",
        title: `¡Bienvenido, ${loggedUser.name}!`,
        text: "Ya puedes revisar la trazabilidad de tus campañas y los leads en secuencia.",
        confirmButtonText: "Continuar",
        confirmButtonColor: "#6641ed",
        background: "#0f172a",
        color: "#f1f5f9",
      });
      navigate("/", { replace: true });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Error desconocido";
      await Swal.fire({
        icon: "error",
        title: "Acceso no válido",
        text: message,
        confirmButtonColor: "#6641ed",
        background: "#0f172a",
        color: "#f1f5f9",
      });
    }
  }

  return (
    <div className="relative min-h-screen overflow-hidden bg-dark">
      <div
        className="pointer-events-none absolute -left-32 top-0 h-[420px] w-[420px] rounded-full bg-purple/25 blur-[120px]"
        aria-hidden
      />
      <div
        className="pointer-events-none absolute -right-20 bottom-0 h-[380px] w-[380px] rounded-full bg-pink/20 blur-[100px]"
        aria-hidden
      />

      <div className="relative z-10 mx-auto flex min-h-screen max-w-6xl flex-col gap-10 px-4 py-10 lg:flex-row lg:items-center lg:gap-16 lg:px-8">
        <motion.section
          className="flex-1 space-y-8"
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.45 }}
        >
          <div>
            <p className="mb-2 text-sm font-semibold uppercase tracking-[0.2em] text-blue">
              La Neta
            </p>
            <h1 className="bg-brand-gradient bg-clip-text text-4xl font-bold leading-tight text-transparent md:text-5xl">
              Outbound &amp; trazabilidad
            </h1>
            <p className="mt-4 max-w-xl text-lg text-slate-400">
              Interfaz web para el seguimiento de leads en secuencia: campañas, engagement y
              sincronización con tus herramientas de ventas.
            </p>
          </div>

          <ul className="space-y-5">
            {features.map(({ icon: Icon, title, text }, i) => (
              <motion.li
                key={title}
                className="flex gap-4 rounded-2xl border border-white/10 bg-white/[0.04] p-4 backdrop-blur-sm"
                initial={{ opacity: 0, x: -12 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.1 + i * 0.08, duration: 0.35 }}
              >
                <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-brand-gradient text-white shadow-lg shadow-purple/20">
                  <Icon className="h-5 w-5" aria-hidden />
                </span>
                <div>
                  <h2 className="font-semibold text-white">{title}</h2>
                  <p className="mt-1 text-sm leading-relaxed text-slate-400">{text}</p>
                </div>
              </motion.li>
            ))}
          </ul>
        </motion.section>

        <motion.div
          className="w-full flex-1 lg:max-w-md"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15, duration: 0.45 }}
        >
          <div className="rounded-2xl border border-white/10 bg-slate-900/80 p-8 shadow-2xl shadow-black/40 backdrop-blur-md">
            <div className="mb-8 text-center">
              <h2 className="text-xl font-bold text-white">Iniciar sesión</h2>
              <p className="mt-2 text-sm text-slate-400">
                Usa tu correo y contraseña corporativos.
              </p>
            </div>

            <form onSubmit={onSubmit} className="space-y-5">
              <label className="block">
                <span className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-slate-400">
                  Correo
                </span>
                <div className="relative">
                  <FiMail
                    className="pointer-events-none absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-slate-500"
                    aria-hidden
                  />
                  <input
                    type="email"
                    autoComplete="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className={cn(
                      "w-full rounded-xl border border-white/10 bg-dark/80 py-3 pl-11 pr-4 text-white",
                      "placeholder:text-slate-600 outline-none ring-purple/0 transition focus:border-purple/50 focus:ring-2 focus:ring-purple/30",
                    )}
                    placeholder="nombre@laneta.com"
                  />
                </div>
              </label>

              <label className="block">
                <span className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-slate-400">
                  Contraseña
                </span>
                <div className="relative">
                  <FiLock
                    className="pointer-events-none absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-slate-500"
                    aria-hidden
                  />
                  <input
                    type="password"
                    autoComplete="current-password"
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className={cn(
                      "w-full rounded-xl border border-white/10 bg-dark/80 py-3 pl-11 pr-4 text-white",
                      "placeholder:text-slate-600 outline-none transition focus:border-purple/50 focus:ring-2 focus:ring-purple/30",
                    )}
                    placeholder="••••••••"
                  />
                </div>
              </label>

              <button
                type="submit"
                disabled={isLoading}
                className={cn(
                  "w-full rounded-xl bg-brand-gradient py-3.5 text-sm font-semibold text-white shadow-lg shadow-purple/25",
                  "transition hover:opacity-95 disabled:cursor-not-allowed disabled:opacity-50",
                )}
              >
                {isLoading ? "Entrando…" : "Entrar"}
              </button>
            </form>

            <p className="mt-8 text-center text-xs text-slate-500">
              ¿Problemas para acceder?{" "}
              <a
                href="https://laneta.com"
                target="_blank"
                rel="noreferrer"
                className="text-blue underline-offset-2 hover:underline"
              >
                Contacta al equipo La Neta
              </a>
            </p>
          </div>

          <p className="mt-6 text-center text-xs text-slate-600">
            Leaders of the digital ecosystem
          </p>
        </motion.div>
      </div>
    </div>
  );
}
