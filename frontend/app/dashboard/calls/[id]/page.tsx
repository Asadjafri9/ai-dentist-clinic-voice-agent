"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { usePolling } from "@/hooks/use-polling";
import type { Appointment, CallRecord } from "@/lib/types";
import { OUTCOME_LABELS, formatDuration, formatInTz } from "@/lib/format";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState, ErrorState, LoadingState, PageHeader } from "@/components/page-state";
import { useClinicTz } from "../../timezone";

export default function CallDetailPage() {
  const { id } = useParams<{ id: string }>();
  const tz = useClinicTz();
  const { data, error, isLoading, mutate } = usePolling<
    CallRecord & { appointment?: Appointment | null }
  >(`/calls/${id}`, 5000);

  if (isLoading) return <div className="p-8"><LoadingState /></div>;
  if (error)
    return (
      <div className="p-8">
        <ErrorState error={error} onRetry={() => mutate()} />
      </div>
    );
  if (!data) return <div className="p-8"><EmptyState message="Call not found." /></div>;

  return (
    <div className="p-6 lg:p-8">
      <PageHeader title="Call detail" subtitle={`Times shown in ${tz}`} />
      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle>Details</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <Row label="Outcome">
              <Badge value={data.outcome} label={OUTCOME_LABELS[data.outcome]} />
            </Row>
            <Row label="Caller">•••{data.phone_suffix ?? "—"}</Row>
            <Row label="Started">{formatInTz(data.started_at ?? data.created_at, tz)}</Row>
            <Row label="Duration">{formatDuration(data.duration_seconds)}</Row>
            <Row label="Ended reason">{data.ended_reason ?? "—"}</Row>
            <Row label="Summary status">{data.summary_status ?? "—"}</Row>
            <Row label="Transcript status">{data.transcript_status ?? "—"}</Row>
            {data.appointment && (
              <Row label="Appointment">
                <Link
                  href={`/dashboard/appointments/${data.appointment.id}`}
                  className="text-primary hover:underline"
                >
                  {formatInTz(data.appointment.start_at, tz)}
                </Link>
              </Row>
            )}
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Summary &amp; transcript</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Summary
              </p>
              <p className="text-sm">{data.summary ?? "No summary available."}</p>
            </div>
            <div>
              <p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Transcript
              </p>
              {data.transcript_status === "deleted" ? (
                <p className="text-sm italic text-muted-foreground">
                  Transcript deleted per retention policy.
                </p>
              ) : data.transcript ? (
                // Rendered as plain text — never raw HTML.
                <pre className="max-h-96 overflow-auto whitespace-pre-wrap rounded-lg bg-muted/50 p-4 text-sm">
                  {data.transcript}
                </pre>
              ) : (
                <p className="text-sm text-muted-foreground">Transcript not available yet.</p>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-muted-foreground">{label}</span>
      <span className="text-right font-medium">{children}</span>
    </div>
  );
}
