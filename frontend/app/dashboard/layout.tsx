"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import useSWR from "swr";
import {
  CalendarDays,
  CalendarClock,
  LayoutDashboard,
  LogOut,
  PhoneCall,
  Settings,
  Stethoscope,
  Users,
  Wrench,
} from "lucide-react";
import { get, post } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { TimezoneContext } from "./timezone";

const NAV = [
  { href: "/dashboard", label: "Overview", icon: LayoutDashboard },
  { href: "/dashboard/calls", label: "Calls", icon: PhoneCall },
  { href: "/dashboard/appointments", label: "Appointments", icon: CalendarDays },
  { href: "/dashboard/patients", label: "Patients", icon: Users },
  { href: "/dashboard/services", label: "Services", icon: Wrench },
  { href: "/dashboard/providers", label: "Providers", icon: Stethoscope },
  { href: "/dashboard/availability", label: "Availability", icon: CalendarClock },
  { href: "/dashboard/settings", label: "Settings", icon: Settings },
];

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { data, error, isLoading } = useSWR("/auth/me", (p: string) => get(p), {
    shouldRetryOnError: false,
    revalidateOnFocus: false,
  });

  if (error?.status === 401) {
    if (typeof window !== "undefined") router.replace("/login");
    return null;
  }

  const clinicName = data?.business?.name ?? "…";
  const tz = data?.business?.timezone ?? "UTC";

  async function logout() {
    try {
      await post("/auth/logout");
    } finally {
      router.replace("/login");
    }
  }

  return (
    <div className="flex min-h-screen">
      <aside className="flex w-56 flex-col border-r bg-card">
        <div className="flex items-center gap-2 border-b px-4 py-4">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <PhoneCall className="h-4 w-4" />
          </span>
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold">{isLoading ? "Loading…" : clinicName}</p>
            <p className="text-xs text-muted-foreground">AI receptionist</p>
          </div>
        </div>
        <nav className="flex-1 space-y-0.5 p-2" aria-label="Dashboard">
          {NAV.map((item) => {
            const active =
              item.href === "/dashboard"
                ? pathname === "/dashboard"
                : pathname.startsWith(item.href);
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                  active
                    ? "bg-accent text-accent-foreground"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground"
                )}
              >
                <Icon className="h-4 w-4" aria-hidden />
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="border-t p-2">
          <Button variant="ghost" size="sm" className="w-full justify-start" onClick={logout}>
            <LogOut className="h-4 w-4" /> Sign out
          </Button>
        </div>
      </aside>
      <div className="flex-1">
        <TimezoneContext.Provider value={tz}>{children}</TimezoneContext.Provider>
      </div>
    </div>
  );
}
