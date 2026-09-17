"use client";

import { useState } from "react";
import Link from "next/link";
import { usePolling } from "@/hooks/use-polling";
import type { Patient } from "@/lib/types";
import { formatInTz } from "@/lib/format";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { EmptyState, ErrorState, LoadingState, PageHeader } from "@/components/page-state";
import { useClinicTz } from "../timezone";

export default function PatientsPage() {
  const tz = useClinicTz();
  const [search, setSearch] = useState("");
  const params = new URLSearchParams({ limit: "50" });
  if (search) params.set("search", search);
  const { data, error, isLoading, mutate } =
    usePolling<{ items: Patient[] }>(`/patients?${params}`, 8000);

  return (
    <div className="p-6 lg:p-8">
      <PageHeader
        title="Patients"
        right={
          <Input
            placeholder="Search name or phone…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-64"
            aria-label="Search patients"
          />
        }
      />
      {error && <ErrorState error={error} onRetry={() => mutate()} />}
      <Card>
        <CardContent className="p-0">
          {isLoading ? (
            <LoadingState />
          ) : !data?.items?.length ? (
            <EmptyState message="No patients yet. Patients are created automatically when callers book." />
          ) : (
            <Table>
              <THead>
                <TR>
                  <TH>Name</TH>
                  <TH>Phone</TH>
                  <TH>Since</TH>
                </TR>
              </THead>
              <TBody>
                {data.items.map((p) => (
                  <TR key={p.id}>
                    <TD>
                      <Link href={`/dashboard/patients/${p.id}`} className="font-medium text-primary hover:underline">
                        {p.display_name ?? "—"}
                      </Link>
                    </TD>
                    <TD className="tabular-nums">{p.phone ?? `•••${p.phone_suffix ?? ""}`}</TD>
                    <TD>{formatInTz(p.created_at, tz, { timeStyle: undefined })}</TD>
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
