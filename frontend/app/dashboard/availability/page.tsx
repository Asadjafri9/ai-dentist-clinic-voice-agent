"use client";

import { useState } from "react";
import { usePolling } from "@/hooks/use-polling";
import { del, patch, post } from "@/lib/api";
import type { AvailabilityDay, Provider } from "@/lib/types";
import { formatTimeInTz } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label, Select } from "@/components/ui/input";
import { EmptyState, ErrorState, LoadingState, PageHeader } from "@/components/page-state";
import { useClinicTz } from "../timezone";

const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

export default function AvailabilityPage() {
  const tz = useClinicTz();
  const [weekStart, setWeekStart] = useState(() => {
    const d = new Date();
    return d.toISOString().slice(0, 10);
  });
  const [providerFilter, setProviderFilter] = useState("");

  const providers = usePolling<{ items: Provider[] }>("/providers", 15000);
  const params = new URLSearchParams({ from: weekStart });
  params.set("to", addDays(weekStart, 6));
  if (providerFilter) params.set("provider_id", providerFilter);
  const availability = usePolling<{ timezone: string; days: AvailabilityDay[] }>(
    `/availability?${params}`,
    10000
  );

  const [ruleForm, setRuleForm] = useState({
    provider_id: "",
    weekday: 0,
    start_local: "09:00",
    end_local: "17:00",
  });
  const [excForm, setExcForm] = useState({
    provider_id: "",
    local_date: weekStart,
    kind: "closed" as "closed" | "added",
    start_local: "",
    end_local: "",
  });
  const [formError, setFormError] = useState<string | null>(null);

  async function addRule(e: React.FormEvent) {
    e.preventDefault();
    setFormError(null);
    try {
      await post("/availability/rules", {
        provider_id: ruleForm.provider_id || undefined,
        weekday: Number(ruleForm.weekday),
        start_local: ruleForm.start_local,
        end_local: ruleForm.end_local,
      });
      await availability.mutate();
    } catch (err: any) {
      setFormError(err?.message ?? "Failed to add rule");
    }
  }

  async function addException(e: React.FormEvent) {
    e.preventDefault();
    setFormError(null);
    try {
      await post("/availability/exceptions", {
        provider_id: excForm.provider_id || null,
        local_date: excForm.local_date,
        kind: excForm.kind,
        start_local: excForm.kind === "added" ? excForm.start_local : null,
        end_local: excForm.kind === "added" ? excForm.end_local : null,
      });
      await availability.mutate();
    } catch (err: any) {
      setFormError(err?.message ?? "Failed to add exception");
    }
  }

  return (
    <div className="p-6 lg:p-8">
      <PageHeader
        title="Availability"
        subtitle={`Provider windows and bookings · ${tz}`}
        right={
          <div className="flex items-end gap-2">
            <div className="flex flex-col gap-1">
              <Label htmlFor="wk">Week of</Label>
              <Input id="wk" type="date" value={weekStart} onChange={(e) => setWeekStart(e.target.value)} />
            </div>
            <Select value={providerFilter} onChange={(e) => setProviderFilter(e.target.value)} className="w-44" aria-label="Provider filter">
              <option value="">All providers</option>
              {providers.data?.items.map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </Select>
          </div>
        }
      />
      {availability.error && <ErrorState error={availability.error} onRetry={() => availability.mutate()} />}

      <div className="grid gap-4 xl:grid-cols-3">
        <div className="space-y-4 xl:col-span-2">
          {availability.isLoading ? (
            <LoadingState />
          ) : !availability.data?.days?.length ? (
            <EmptyState message="No availability data." />
          ) : (
            availability.data.days.map((day) => (
              <Card key={day.local_date}>
                <CardHeader className="pb-2">
                  <CardTitle className="text-base">{day.local_date}</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  {day.providers.map((p) => (
                    <div key={p.provider_id} className="text-sm">
                      <p className="mb-1 font-medium">{p.provider_name}</p>
                      <div className="flex flex-wrap gap-1.5">
                        {p.windows.length === 0 && (
                          <span className="text-xs text-muted-foreground">Closed</span>
                        )}
                        {p.windows.map((w, i) => (
                          <span
                            key={i}
                            className="rounded-md border border-primary/25 bg-accent px-2 py-1 text-xs text-accent-foreground"
                          >
                            {formatTimeInTz(w.start, tz)} – {formatTimeInTz(w.end, tz)}
                          </span>
                        ))}
                        {p.booked.map((b) => (
                          <span
                            key={b.id}
                            className="rounded-md border border-emerald-300 bg-emerald-50 px-2 py-1 text-xs text-emerald-800"
                            title={b.patient_name ?? "Booked"}
                          >
                            Booked {formatTimeInTz(b.start_at, tz)}
                          </span>
                        ))}
                      </div>
                    </div>
                  ))}
                </CardContent>
              </Card>
            ))
          )}
        </div>

        <div className="space-y-4">
          <Card>
            <CardHeader><CardTitle>Add recurring window</CardTitle></CardHeader>
            <CardContent>
              <form onSubmit={addRule} className="flex flex-col gap-3">
                <div className="flex flex-col gap-1.5">
                  <Label>Provider</Label>
                  <Select required value={ruleForm.provider_id}
                    onChange={(e) => setRuleForm({ ...ruleForm, provider_id: e.target.value })}>
                    <option value="" disabled>Choose…</option>
                    {providers.data?.items.map((p) => (
                      <option key={p.id} value={p.id}>{p.name}</option>
                    ))}
                  </Select>
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label>Weekday</Label>
                  <Select value={ruleForm.weekday}
                    onChange={(e) => setRuleForm({ ...ruleForm, weekday: Number(e.target.value) })}>
                    {WEEKDAYS.map((d, i) => <option key={d} value={i}>{d}</option>)}
                  </Select>
                </div>
                <div className="flex gap-2">
                  <div className="flex flex-1 flex-col gap-1.5">
                    <Label>Start</Label>
                    <Input type="time" value={ruleForm.start_local}
                      onChange={(e) => setRuleForm({ ...ruleForm, start_local: e.target.value })} />
                  </div>
                  <div className="flex flex-1 flex-col gap-1.5">
                    <Label>End</Label>
                    <Input type="time" value={ruleForm.end_local}
                      onChange={(e) => setRuleForm({ ...ruleForm, end_local: e.target.value })} />
                  </div>
                </div>
                <Button type="submit">Add window</Button>
              </form>
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle>Add exception</CardTitle></CardHeader>
            <CardContent>
              <form onSubmit={addException} className="flex flex-col gap-3">
                <div className="flex flex-col gap-1.5">
                  <Label>Provider (optional — blank = clinic-wide)</Label>
                  <Select value={excForm.provider_id}
                    onChange={(e) => setExcForm({ ...excForm, provider_id: e.target.value })}>
                    <option value="">Clinic-wide</option>
                    {providers.data?.items.map((p) => (
                      <option key={p.id} value={p.id}>{p.name}</option>
                    ))}
                  </Select>
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label>Date</Label>
                  <Input type="date" required value={excForm.local_date}
                    onChange={(e) => setExcForm({ ...excForm, local_date: e.target.value })} />
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label>Type</Label>
                  <Select value={excForm.kind}
                    onChange={(e) => setExcForm({ ...excForm, kind: e.target.value as "closed" | "added" })}>
                    <option value="closed">Closed (whole day)</option>
                    <option value="added">Extra hours</option>
                  </Select>
                </div>
                {excForm.kind === "added" && (
                  <div className="flex gap-2">
                    <div className="flex flex-1 flex-col gap-1.5">
                      <Label>Start</Label>
                      <Input type="time" value={excForm.start_local}
                        onChange={(e) => setExcForm({ ...excForm, start_local: e.target.value })} />
                    </div>
                    <div className="flex flex-1 flex-col gap-1.5">
                      <Label>End</Label>
                      <Input type="time" value={excForm.end_local}
                        onChange={(e) => setExcForm({ ...excForm, end_local: e.target.value })} />
                    </div>
                  </div>
                )}
                <Button type="submit">Add exception</Button>
              </form>
            </CardContent>
          </Card>
          {formError && <ErrorState error={new Error(formError)} />}
        </div>
      </div>
    </div>
  );
}

function addDays(iso: string, days: number) {
  const d = new Date(`${iso}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}
