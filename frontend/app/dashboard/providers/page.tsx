"use client";

import { useState } from "react";
import { usePolling } from "@/hooks/use-polling";
import { patch, post } from "@/lib/api";
import type { Provider, Service } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/input";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { EmptyState, ErrorState, LoadingState, PageHeader } from "@/components/page-state";

export default function ProvidersPage() {
  const providers = usePolling<{ items: Provider[] }>("/providers", 10000);
  const services = usePolling<{ items: Service[] }>("/services", 10000);
  const [form, setForm] = useState({ name: "", title: "" });
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const serviceName = (id: string) =>
    services.data?.items.find((s) => s.id === id)?.display_name ?? id;

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setFormError(null);
    try {
      await post("/providers", { name: form.name, title: form.title || null, service_ids: [] });
      setForm({ name: "", title: "" });
      await providers.mutate();
    } catch (err: any) {
      setFormError(err?.message ?? "Create failed");
    } finally {
      setBusy(false);
    }
  }

  async function toggleService(p: Provider, serviceId: string) {
    const ids = p.service_ids.includes(serviceId)
      ? p.service_ids.filter((s) => s !== serviceId)
      : [...p.service_ids, serviceId];
    try {
      await patch(`/providers/${p.id}`, { service_ids: ids, version: p.version });
      await providers.mutate();
    } catch (err: any) {
      alert(err?.message ?? "Update failed");
    }
  }

  async function toggleActive(p: Provider) {
    try {
      await patch(`/providers/${p.id}`, { active: !p.active, version: p.version });
      await providers.mutate();
    } catch (err: any) {
      alert(err?.message ?? "Update failed");
    }
  }

  return (
    <div className="p-6 lg:p-8">
      <PageHeader title="Providers" subtitle="Who can perform which services" />
      {providers.error && <ErrorState error={providers.error} onRetry={() => providers.mutate()} />}
      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardContent className="p-0">
            {providers.isLoading ? (
              <LoadingState />
            ) : !providers.data?.items?.length ? (
              <EmptyState message="No providers configured." />
            ) : (
              <Table>
                <THead>
                  <TR>
                    <TH>Name</TH>
                    <TH>Title</TH>
                    <TH>Services</TH>
                    <TH>Status</TH>
                  </TR>
                </THead>
                <TBody>
                  {providers.data.items.map((p) => (
                    <TR key={p.id}>
                      <TD className="font-medium">{p.name}</TD>
                      <TD className="text-muted-foreground">{p.title ?? "—"}</TD>
                      <TD>
                        <div className="flex max-w-md flex-wrap gap-1.5">
                          {services.data?.items.map((s) => {
                            const on = p.service_ids.includes(s.id);
                            return (
                              <button
                                key={s.id}
                                onClick={() => toggleService(p, s.id)}
                                className={`rounded-full border px-2 py-0.5 text-xs transition-colors focus-visible:ring-2 focus-visible:ring-ring ${
                                  on
                                    ? "border-primary/30 bg-accent text-accent-foreground"
                                    : "border-border text-muted-foreground hover:bg-muted"
                                }`}
                                aria-pressed={on}
                              >
                                {s.display_name}
                              </button>
                            );
                          })}
                        </div>
                      </TD>
                      <TD>
                        <button
                          onClick={() => toggleActive(p)}
                          className="rounded focus-visible:ring-2 focus-visible:ring-ring"
                          aria-label={`Toggle active for ${p.name}`}
                        >
                          <Badge value={p.active ? "active" : "inactive"} />
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
          <CardHeader><CardTitle>Add provider</CardTitle></CardHeader>
          <CardContent>
            <form onSubmit={create} className="flex flex-col gap-3">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="prv-name">Name</Label>
                <Input id="prv-name" required value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Dr. Jane Doe" />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="prv-title">Title</Label>
                <Input id="prv-title" value={form.title}
                  onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="Dentist" />
              </div>
              {formError && <p role="alert" className="text-sm text-destructive">{formError}</p>}
              <Button type="submit" disabled={busy}>{busy ? "Adding…" : "Add provider"}</Button>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
