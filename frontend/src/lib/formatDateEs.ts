/**
 * Ej.: "10 de marzo de 2026 a las 12:39 p. m." (es-MX, hora 12 h).
 */
export function formatDateLongEs(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) {
    return iso;
  }
  const day = d.getDate();
  const monthRaw = new Intl.DateTimeFormat("es", { month: "long" }).format(d);
  const month = monthRaw.charAt(0).toUpperCase() + monthRaw.slice(1);
  const year = d.getFullYear();
  let time = new Intl.DateTimeFormat("es-MX", {
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  }).format(d);
  time = time.replace(/p\.m\./gi, "p. m.").replace(/a\.m\./gi, "a. m.");
  return `${day} de ${month} de ${year} a las ${time}`;
}
