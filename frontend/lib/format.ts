export function formatInTz(iso: string | undefined | null, tz: string, opts?: Intl.DateTimeFormatOptions) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return new Intl.DateTimeFormat("en-US", {
    timeZone: tz,
    dateStyle: "medium",
    timeStyle: "short",
    ...opts,
  }).format(d);
}

export function formatTimeInTz(iso: string | undefined | null, tz: string) {
  return formatInTz(iso, tz, { dateStyle: undefined, timeStyle: "short" });
}

export function formatDuration(seconds?: number | null) {
  if (seconds == null) return "—";
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return m ? `${m}m ${s}s` : `${s}s`;
}

export const OUTCOME_LABELS: Record<string, string> = {
  appointment_booked: "Booked",
  information_only: "Info only",
  unsupported_request: "Unsupported",
  no_available_slot: "No slot",
  caller_disconnected: "Disconnected",
  booking_failed: "Booking failed",
  safety_redirect: "Safety redirect",
  unknown: "Unknown",
};
