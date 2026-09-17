"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { usePolling } from "@/hooks/use-polling";
import type { Appointment, Patient } from "@/lib/types";
import { formatInTz } from "@/lib/format";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { EmptyState, ErrorState, LoadingState, PageHeader } from "@/components/page-state";
import { useClinicTz } from "../../timezone";

export default function PatientDetailPage() {
  const { id } = useParams<{ id: string }>();
  const tz = useClinicTz();
  const { data, error, isLoading, mutate } = usePolling<
    Patient & { appointments?: Appointment[] }
  >(`/patients/${id}`, 8000);

  if (isLoading) return <div className="p-8"><LoadingState /></div>;
  if (error) return <div className="p-8"><ErrorState error={error} onRetry={() => mutate()} /></div>;
  if (!data) return <div className="p-8"><EmptyState message="Patient not found." /></div>;

  return (
    <div className="p-6 lg:p-8">
      <PageHeader title={data.display_name ?? "Patient"} subtitle={`Times shown in ${tz}`} />
      <Card>
        <CardHeader><CardTitle>Appointments</CardTitle></CardHeader>
        <CardContent className="p-0">
          {!data.appointments?.length ? (
            <EmptyState message="No appointments for this patient." />
          ) : (
            <Table>
              <THead>
                <TR>
                  <TH>When</TH>
                  <TH>Status</TH>
                  <TH>Source</TH>
                </TR>
              </THead>
              <TBody>
                {data.appointments.map((a) => (
                  <TR key={a.id}>
                    <TD>
                      <Link href={`/dashboard/appointments/${a.id}`} className="text-primary hover:underline">
                        {formatInTz(a.start_at, tz)}
                      </Link>
                    </TD>
                    <TD><Badge value={a.status} /></TD>
                    <TD className="text-muted-foreground">{a.source ?? "—"}</TD>
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
