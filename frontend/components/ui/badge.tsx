import { cn } from "@/lib/utils";

const TONES: Record<string, string> = {
  confirmed: "bg-emerald-100 text-emerald-800 border-emerald-200",
  cancelled: "bg-red-100 text-red-800 border-red-200",
  completed: "bg-sky-100 text-sky-800 border-sky-200",
  appointment_booked: "bg-emerald-100 text-emerald-800 border-emerald-200",
  information_only: "bg-slate-100 text-slate-700 border-slate-200",
  unsupported_request: "bg-amber-100 text-amber-800 border-amber-200",
  no_available_slot: "bg-amber-100 text-amber-800 border-amber-200",
  caller_disconnected: "bg-slate-100 text-slate-700 border-slate-200",
  booking_failed: "bg-red-100 text-red-800 border-red-200",
  safety_redirect: "bg-purple-100 text-purple-800 border-purple-200",
  unknown: "bg-slate-100 text-slate-600 border-slate-200",
  synced: "bg-emerald-100 text-emerald-800 border-emerald-200",
  pending: "bg-amber-100 text-amber-800 border-amber-200",
  error: "bg-red-100 text-red-800 border-red-200",
  never: "bg-slate-100 text-slate-600 border-slate-200",
  active: "bg-emerald-100 text-emerald-800 border-emerald-200",
  inactive: "bg-slate-100 text-slate-600 border-slate-200",
};

export function Badge({ value, label }: { value: string; label?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium",
        TONES[value] ?? TONES.unknown
      )}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current" aria-hidden />
      {label ?? value.replace(/_/g, " ")}
    </span>
  );
}
