"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { usePolling } from "@/hooks/use-polling";
import { patch } from "@/lib/api";
import type { Appointment, CallRecord, Patient, Provider, Service } from "@/lib/types";
import { formatInTz } from "@/lib/format";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/dialog";
import { EmptyState, ErrorState, LoadingState, PageHeader } from "@/components/page-state";
import { useClinicTz } from "../../timezone";

export default function AppointmentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const tz = useClinicTz();
  const { data, error, isLoading, mutate } = usePolling<
    Appointment & { call?: CallRecord | null; patient?: Patient | null }
  >(`/appointments/${id}`, 5000);
  const providers = usePolling<{ items: Provider[] }>("/providers", 30000);
  const services = usePolling<{ items: Service[] }>("/services", 30000);

  const [confirm, setConfirm] = useState<null | "cancelled" | "completed">(null);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  if (isLoading) return <div className="p-8"><LoadingState /></div>;
  if (error) return <div className="p-8"><ErrorState error={error} onRetry={() => mutate()} /></div>;
  if (!data) return <div className="p-8"><EmptyState message="Appointment not found." /></div>;

  const provider = providers.data?.items.find((p) => p.id === data.provider_id);
  const service = services.data?.items.find((s) => s.id === data.service_id);

  async function changeStatus(target: "cancelled" | "completed") {
    setBusy(true);
    setActionError(null);
    try {
      await patch(`/appointments/${id}/status`, {
        status: target,
        idempotency_key: `ui-${id}-${target}-${Date.now()}`,
        allow_early_completion: true,
      });
      await mutate();
    } catch (e: any) {
      setActionError(e?.message ?? "Update failed");
    } finally {
      setBusy(false);
      setConfirm(null);
    }
  }

  return (
    <div className="p-6 lg:p-8">
      <PageHeader
        title="Appointment"
        subtitle={`Times shown in ${tz}`}
        right={
          data.status === "confirmed" ? (
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => setConfirm("completed")}>
                Mark completed
              </Button>
              <Button variant="destructive" onClick={() => setConfirm("cancelled")}>
                Cancel appointment
              </Button>
            </div>
          ) : undefined
        }
      />
      {actionError && <div className="mb-4"><ErrorState error={new Error(actionError)} /></div>}

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader><CardTitle>Details</CardTitle></CardHeader>
          <CardContent className="space-y-3 text-sm">
            <Row label="Status"><Badge value={data.status} /></Row>
            <Row label="Patient">{data.patient_name ?? "—"}</Row>
            <Row label="Callback">•••{data.phone_suffix ?? "—"}</Row>
            <Row label="Service">{service?.display_name ?? data.service_id}</Row>
            <Row label="Provider">{provider?.name ?? data.provider_id}</Row>
            <Row label="Start">{formatInTz(data.start_at, tz)}</Row>
            <Row label="End">{formatInTz(data.end_at, tz)}</Row>
            <Row label="Source">{data.source ?? "—"}</Row>
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Linked records</CardTitle></CardHeader>
          <CardContent className="space-y-3 text-sm">
            <Row label="Call">
              {data.call ? (
                <Link href={`/dashboard/calls/${data.call.id}`} className="text-primary hover:underline">
                  View call
                </Link>
              ) : "—"}
            </Row>
            <Row label="Patient record">
              {data.patient ? (
                <Link href={`/dashboard/patients/${data.patient.id}`} className="text-primary hover:underline">
                  {data.patient.display_name ?? "View patient"}
                </Link>
              ) : "—"}
            </Row>
          </CardContent>
        </Card>
      </div>

      <ConfirmDialog
        open={confirm === "cancelled"}
        title="Cancel this appointment?"
        description="This releases the slot immediately. The cancellation is audited and cannot be undone."
        confirmLabel="Cancel appointment"
        destructive
        onCancel={() => setConfirm(null)}
        onConfirm={() => void changeStatus("cancelled")}
      />
      <ConfirmDialog
        open={confirm === "completed"}
        title="Mark as completed?"
        description="Marks this appointment as completed. This is audited."
        confirmLabel="Mark completed"
        onCancel={() => setConfirm(null)}
        onConfirm={() => void changeStatus("completed")}
      />
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
