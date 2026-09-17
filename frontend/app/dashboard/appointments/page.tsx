"use client";

import { useState } from "react";
import Link from "next/link";
import { usePolling } from "@/hooks/use-polling";
import type { Appointment, Provider, Service } from "@/lib/types";
import { formatInTz } from "@/lib/format";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Select } from "@/components/ui/input";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { EmptyState, ErrorState, LoadingState, PageHeader } from "@/components/page-state";
import { useClinicTz } from "../timezone";

export default function AppointmentsPage() {
  const tz = useClinicTz();
  const [status, setStatus] = useState("");
  const [providerId, setProviderId] = useState("");

  const params = new URLSearchParams({ limit: "50" });
  if (status) params.set("status", status);
  if (providerId) params.set("provider_id", providerId);

  const appts = usePolling<{ items: Appointment[] }>(`/appointments?${params}`, 5000);
  const providers = usePolling<{ items: Provider[] }>("/providers", 30000);
  const services = usePolling<{ items: Service[] }>("/services", 30000);

  const providerName = (id: string) =>
    providers.data?.items.find((p) => p.id === id)?.name ?? "—";
  const serviceName = (id: string) =>
    services.data?.items.find((s) => s.id === id)?.display_name ?? "—";

  return (
    <div className="p-6 lg:p-8">
      <PageHeader
        title="Appointments"
        subtitle={`All times shown in clinic timezone (${tz})`}
        right={
          <div className="flex gap-2">
            <Select value={status} onChange={(e) => setStatus(e.target.value)} className="w-40" aria-label="Filter by status">
              <option value="">All statuses</option>
              <option value="confirmed">Confirmed</option>
              <option value="completed">Completed</option>
              <option value="cancelled">Cancelled</option>
            </Select>
            <Select value={providerId} onChange={(e) => setProviderId(e.target.value)} className="w-44" aria-label="Filter by provider">
              <option value="">All providers</option>
              {providers.data?.items.map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </Select>
          </div>
        }
      />
      {appts.error && <ErrorState error={appts.error} onRetry={() => appts.mutate()} />}
      <Card>
        <CardContent className="p-0">
          {appts.isLoading ? (
            <LoadingState />
          ) : !appts.data?.items?.length ? (
            <EmptyState message="No appointments yet." />
          ) : (
            <Table>
              <THead>
                <TR>
                  <TH>Patient</TH>
                  <TH>Service</TH>
                  <TH>Provider</TH>
                  <TH>When</TH>
                  <TH>Status</TH>
                  <TH>Source</TH>
                </TR>
              </THead>
              <TBody>
                {appts.data.items.map((a) => (
                  <TR key={a.id}>
                    <TD>
                      <Link href={`/dashboard/appointments/${a.id}`} className="font-medium text-primary hover:underline">
                        {a.patient_name ?? "—"}
                      </Link>
                      {a.phone_suffix && (
                        <span className="ml-1 text-xs text-muted-foreground">•••{a.phone_suffix}</span>
                      )}
                    </TD>
                    <TD>{serviceName(a.service_id)}</TD>
                    <TD>{providerName(a.provider_id)}</TD>
                    <TD>{formatInTz(a.start_at, tz)}</TD>
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
