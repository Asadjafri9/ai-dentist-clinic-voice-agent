"use client";

import Link from "next/link";
import { CalendarDays, PhoneCall, TrendingUp } from "lucide-react";
import { usePolling } from "@/hooks/use-polling";
import type { DashboardSummary } from "@/lib/types";
import { formatTimeInTz } from "@/lib/format";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { EmptyState, ErrorState, LoadingState, PageHeader } from "@/components/page-state";
import { useClinicTz } from "./timezone";

export default function DashboardPage() {
  const tz = useClinicTz();
  const summary = usePolling<DashboardSummary>("/dashboard/summary", 5000);
  const activity = usePolling<{ items: any[] }>("/dashboard/activity?limit=10", 5000);

  const s = summary.data;

  return (
    <div className="p-6 lg:p-8">
      <PageHeader
        title="Overview"
        subtitle={`All times shown in clinic timezone (${tz})`}
        updatedAt={summary.dataUpdatedAt ? new Date(summary.dataUpdatedAt).toISOString() : null}
      />

      {summary.error && <ErrorState error={summary.error} onRetry={() => summary.mutate()} />}

      <div className="grid gap-4 sm:grid-cols-3">
        <Stat icon={PhoneCall} label="Calls today" value={s?.calls_today} />
        <Stat icon={CalendarDays} label="AI-booked appointments" value={s?.ai_booked_appointments} />
        <Stat
          icon={TrendingUp}
          label="Booking rate (eligible calls)"
          value={s?.booking_rate == null ? "—" : `${Math.round(s.booking_rate * 100)}%`}
        />
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Upcoming appointments</CardTitle>
          </CardHeader>
          <CardContent>
            {summary.isLoading ? (
              <LoadingState />
            ) : !s?.upcoming?.length ? (
              <EmptyState message="No upcoming appointments." />
            ) : (
              <Table>
                <THead>
                  <TR>
                    <TH>Patient</TH>
                    <TH>When ({tz})</TH>
                    <TH>Status</TH>
                  </TR>
                </THead>
                <TBody>
                  {s.upcoming.map((a) => (
                    <TR key={a.id}>
                      <TD>
                        <Link
                          href={`/dashboard/appointments/${a.id}`}
                          className="font-medium text-primary hover:underline"
                        >
                          {a.patient_name ?? "—"}
                        </Link>
                      </TD>
                      <TD>{formatTimeInTz(a.start_at, tz)}</TD>
                      <TD>
                        <Badge value={a.status} />
                      </TD>
                    </TR>
                  ))}
                </TBody>
              </Table>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Recent activity</CardTitle>
          </CardHeader>
          <CardContent>
            {activity.isLoading ? (
              <LoadingState />
            ) : !activity.data?.items?.length ? (
              <EmptyState message="No activity yet." />
            ) : (
              <ul className="space-y-3">
                {activity.data.items.map((i: any) => (
                  <li key={i.id} className="flex items-start justify-between gap-3 text-sm">
                    <div>
                      <p className="font-medium">{i.action}</p>
                      {i.summary?.service && (
                        <p className="text-xs text-muted-foreground">
                          {i.summary.service} · {i.summary.provider ?? ""}
                        </p>
                      )}
                    </div>
                    <time className="shrink-0 text-xs text-muted-foreground">
                      {i.created_at ? formatTimeInTz(i.created_at, tz) : ""}
                    </time>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function Stat({
  icon: Icon,
  label,
  value,
}: {
  icon: any;
  label: string;
  value: React.ReactNode;
}) {
  return (
    <Card>
      <CardContent className="flex items-center gap-4 p-5">
        <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent text-accent-foreground">
          <Icon className="h-5 w-5" aria-hidden />
        </span>
        <div>
          <p className="text-2xl font-semibold tabular-nums">{value ?? "—"}</p>
          <p className="text-xs text-muted-foreground">{label}</p>
        </div>
      </CardContent>
    </Card>
  );
}
