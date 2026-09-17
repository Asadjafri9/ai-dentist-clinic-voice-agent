"use client";

import { useState } from "react";
import { usePolling } from "@/hooks/use-polling";
import { patch, post } from "@/lib/api";
import type { Service } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/input";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { EmptyState, ErrorState, LoadingState, PageHeader } from "@/components/page-state";

export default function ServicesPage() {
  const { data, error, isLoading, mutate } =
    usePolling<{ items: Service[] }>("/services", 10000);
  const [form, setForm] = useState({ slug: "", display_name: "", duration_minutes: 30 });
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setFormError(null);
    try {
      await post("/services", {
        slug: form.slug,
        display_name: form.display_name,
        duration_minutes: Number(form.duration_minutes),
      });
      setForm({ slug: "", display_name: "", duration_minutes: 30 });
      await mutate();
    } catch (err: any) {
      setFormError(err?.message ?? "Create failed");
    } finally {
      setBusy(false);
    }
  }

  async function toggle(s: Service, field: "active" | "voice_bookable") {
    try {
      await patch(`/services/${s.id}`, { [field]: !s[field], version: s.version });
      await mutate();
    } catch (err: any) {
      alert(err?.message ?? "Update failed");
    }
  }

  return (
    <div className="p-6 lg:p-8">
      <PageHeader title="Services" subtitle="Voice-bookable services and durations" />
      {error && <ErrorState error={error} onRetry={() => mutate()} />}
      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardContent className="p-0">
            {isLoading ? (
              <LoadingState />
            ) : !data?.items?.length ? (
              <EmptyState message="No services configured." />
            ) : (
              <Table>
                <THead>
                  <TR>
                    <TH>Name</TH>
                    <TH>Slug</TH>
                    <TH>Duration</TH>
                    <TH>Aliases</TH>
                    <TH>Active</TH>
                    <TH>Voice</TH>
                  </TR>
                </THead>
                <TBody>
                  {data.items.map((s) => (
                    <TR key={s.id}>
                      <TD className="font-medium">{s.display_name}</TD>
                      <TD className="font-mono text-xs">{s.slug}</TD>
                      <TD>{s.duration_minutes} min</TD>
                      <TD className="max-w-40 truncate text-xs text-muted-foreground">
                        {s.aliases.join(", ") || "—"}
                      </TD>
                      <TD>
                        <button
                          onClick={() => toggle(s, "active")}
                          className="rounded focus-visible:ring-2 focus-visible:ring-ring"
                          aria-label={`Toggle active for ${s.display_name}`}
                        >
                          <Badge value={s.active ? "active" : "inactive"} />
                        </button>
                      </TD>
                      <TD>
                        <button
                          onClick={() => toggle(s, "voice_bookable")}
                          className="rounded focus-visible:ring-2 focus-visible:ring-ring"
                          aria-label={`Toggle voice booking for ${s.display_name}`}
                        >
                          <Badge value={s.voice_bookable ? "active" : "inactive"} label={s.voice_bookable ? "bookable" : "off"} />
                        </button>
                      </TD>
                    </TR>
                  ))}
                </TBody>
              </Table>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>Add service</CardTitle></CardHeader>
          <CardContent>
            <form onSubmit={create} className="flex flex-col gap-3">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="svc-slug">Slug</Label>
                <Input id="svc-slug" required pattern="[a-z0-9_]+" value={form.slug}
                  onChange={(e) => setForm({ ...form, slug: e.target.value })} placeholder="dental_cleaning" />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="svc-name">Display name</Label>
                <Input id="svc-name" required value={form.display_name}
                  onChange={(e) => setForm({ ...form, display_name: e.target.value })} placeholder="Dental Cleaning" />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="svc-dur">Duration (minutes)</Label>
                <Input id="svc-dur" type="number" min={5} max={480} required value={form.duration_minutes}
                  onChange={(e) => setForm({ ...form, duration_minutes: Number(e.target.value) })} />
              </div>
              {formError && <p role="alert" className="text-sm text-destructive">{formError}</p>}
              <Button type="submit" disabled={busy}>{busy ? "Adding…" : "Add service"}</Button>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
