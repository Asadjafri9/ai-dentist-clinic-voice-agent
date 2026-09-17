"use client";

import Link from "next/link";
import { usePolling } from "@/hooks/use-polling";
import type { CallRecord } from "@/lib/types";
import { OUTCOME_LABELS, formatDuration, formatInTz } from "@/lib/format";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { EmptyState, ErrorState, LoadingState, PageHeader } from "@/components/page-state";
import { useClinicTz } from "../timezone";

export default function CallsPage() {
  const tz = useClinicTz();
  const { data, error, isLoading, mutate, dataUpdatedAt } =
    usePolling<{ items: CallRecord[]; next_cursor: string | null }>("/calls?limit=50", 5000);

  return (
    <div className="p-6 lg:p-8">
      <PageHeader
        title="Calls"
        subtitle={`Inbound calls handled by the AI receptionist · ${tz}`}
        updatedAt={dataUpdatedAt ? new Date(dataUpdatedAt).toISOString() : null}
      />
      {error && <ErrorState error={error} onRetry={() => mutate()} />}
      <Card>
        <CardContent className="p-0">
          {isLoading ? (
            <LoadingState />
          ) : !data?.items?.length ? (
            <EmptyState message="No calls yet. They'll appear here within seconds of ending." />
          ) : (
            <Table>
              <THead>
                <TR>
                  <TH>Caller</TH>
                  <TH>Started</TH>
                  <TH>Duration</TH>
                  <TH>Outcome</TH>
                  <TH>Summary</TH>
                </TR>
              </THead>
              <TBody>
                {data.items.map((c) => (
                  <TR key={c.id}>
                    <TD>
                      <Link href={`/dashboard/calls/${c.id}`} className="font-medium text-primary hover:underline">
                        •••{c.phone_suffix ?? "—"}
                      </Link>
                    </TD>
                    <TD>{formatInTz(c.started_at ?? c.created_at, tz)}</TD>
                    <TD>{formatDuration(c.duration_seconds)}</TD>
                    <TD>
                      <Badge value={c.outcome} label={OUTCOME_LABELS[c.outcome]} />
                    </TD>
                    <TD className="max-w-xs truncate text-muted-foreground">{c.summary ?? "—"}</TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
