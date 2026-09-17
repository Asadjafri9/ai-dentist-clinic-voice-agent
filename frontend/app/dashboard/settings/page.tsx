"use client";

import { useEffect, useState } from "react";
import { usePolling } from "@/hooks/use-polling";
import { patch } from "@/lib/api";
import type { Business } from "@/lib/types";
import { formatInTz } from "@/lib/format";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label, Textarea } from "@/components/ui/input";
import { ErrorState, LoadingState, PageHeader } from "@/components/page-state";

const DAY_ORDER = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"];
const DAY_LABELS: Record<string, string> = {
  mon: "Monday", tue: "Tuesday", wed: "Wednesday", thu: "Thursday",
  fri: "Friday", sat: "Saturday", sun: "Sunday",
};

export default function SettingsPage() {
  const { data, error, isLoading, mutate } = usePolling<Business>("/business", 15000);
  const [form, setForm] = useState<Partial<Business>>({});
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  useEffect(() => {
    if (data && !form.name) setForm(data);
  }, [data, form.name]);

  if (isLoading) return <div className="p-8"><LoadingState /></div>;
  if (error) return <div className="p-8"><ErrorState error={error} onRetry={() => mutate()} /></div>;
  if (!data) return null;

  const tz = data.timezone;
  const sync = data.voice_sync ?? { status: "never" };

  async function save(section: "business" | "voice") {
    setBusy(true);
    setFormError(null);
    setSaved(false);
    try {
      const payload: Record<string, unknown> = {
        name: form.name,
        phone: form.phone,
        address: form.address,
        business_hours: form.business_hours,
        greeting: form.greeting,
        consent_disclosure: form.consent_disclosure,
        transcript_retention_days: form.transcript_retention_days,
      };
      if (section === "voice") {
        await patch("/business/voice", {
          greeting: form.greeting,
          consent_disclosure: form.consent_disclosure,
        });
      } else {
        await patch("/business", payload);
      }
      await mutate();
      setSaved(true);
    } catch (err: any) {
      setFormError(err?.message ?? "Save failed");
    } finally {
      setBusy(false);
    }
  }

  function setHours(day: string, field: "open" | "close" | "closed", value: string | boolean) {
    const hours = { ...(form.business_hours ?? data!.business_hours) };
    hours[day] = { ...hours[day], [field]: value };
    setForm({ ...form, business_hours: hours });
  }

  return (
    <div className="p-6 lg:p-8">
      <PageHeader
        title="Settings"
        subtitle={`Clinic configuration · timezone ${tz}`}
        right={
          <div className="flex items-center gap-2 text-sm">
            <span className="text-muted-foreground">Voice sync:</span>
            <Badge value={sync.status} />
            {sync.last_synced_at && (
              <span className="text-xs text-muted-foreground">
                {formatInTz(sync.last_synced_at, tz)}
              </span>
            )}
          </div>
        }
      />
      {formError && <div className="mb-4"><ErrorState error={new Error(formError)} /></div>}
      {saved && (
        <p className="mb-4 rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800" role="status">
          Saved. Voice changes sync to the assistant in the background — the badge above shows real status.
        </p>
      )}
      {sync.status === "error" && (
        <div className="mb-4"><ErrorState error={new Error(`Voice sync failed: ${sync.error ?? "unknown"}`)} /></div>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader><CardTitle>Clinic identity</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <Field label="Name">
              <Input value={form.name ?? ""} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            </Field>
            <Field label="Phone">
              <Input value={form.phone ?? ""} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
            </Field>
            <Field label="Address">
              <Input value={form.address ?? ""} onChange={(e) => setForm({ ...form, address: e.target.value })} />
            </Field>
            <Field label={`Transcript retention (days)`}>
              <Input type="number" min={1} max={365} value={form.transcript_retention_days ?? 30}
                onChange={(e) => setForm({ ...form, transcript_retention_days: Number(e.target.value) })} />
            </Field>
            <Button onClick={() => save("business")} disabled={busy}>{busy ? "Saving…" : "Save"}</Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>Business hours ({tz})</CardTitle></CardHeader>
          <CardContent className="space-y-2">
            {DAY_ORDER.map((d) => {
              const day = (form.business_hours ?? data.business_hours)?.[d] ?? { open: "", close: "", closed: true };
              return (
                <div key={d} className="flex items-center gap-2 text-sm">
                  <span className="w-24 font-medium">{DAY_LABELS[d]}</span>
                  <label className="flex items-center gap-1 text-xs text-muted-foreground">
                    <input
                      type="checkbox"
                      checked={!day.closed}
                      onChange={(e) => setHours(d, "closed", !e.target.checked)}
                      className="rounded"
                    />
                    Open
                  </label>
                  {!day.closed && (
                    <>
                      <Input type="time" className="h-8 w-28" value={day.open}
                        onChange={(e) => setHours(d, "open", e.target.value)} aria-label={`${DAY_LABELS[d]} open`} />
                      <span className="text-muted-foreground">–</span>
                      <Input type="time" className="h-8 w-28" value={day.close}
                        onChange={(e) => setHours(d, "close", e.target.value)} aria-label={`${DAY_LABELS[d]} close`} />
                    </>
                  )}
                </div>
              );
            })}
            <Button className="mt-2" onClick={() => save("business")} disabled={busy}>{busy ? "Saving…" : "Save hours"}</Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>Greeting &amp; consent</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <Field label="Greeting (spoken at call start)">
              <Textarea rows={3} value={form.greeting ?? ""}
                onChange={(e) => setForm({ ...form, greeting: e.target.value })} />
            </Field>
            <Field label="Consent disclosure">
              <Textarea rows={2} value={form.consent_disclosure ?? ""}
                onChange={(e) => setForm({ ...form, consent_disclosure: e.target.value })} />
            </Field>
            <Button onClick={() => save("voice")} disabled={busy}>
              {busy ? "Saving…" : "Save & sync voice"}
            </Button>
            <p className="text-xs text-muted-foreground">
              Changes push to the voice assistant via the background worker. The sync badge
              shows the real status — a failure stays visibly unsynced.
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>FAQs</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            {(form.faqs ?? data.faqs ?? []).map((f, i) => (
              <div key={i} className="space-y-1 rounded-lg border p-3">
                <Input
                  value={f.question}
                  placeholder="Question"
                  onChange={(e) => {
                    const faqs = [...(form.faqs ?? data.faqs ?? [])];
                    faqs[i] = { ...faqs[i], question: e.target.value };
                    setForm({ ...form, faqs });
                  }}
                />
                <Textarea
                  rows={2}
                  value={f.answer}
                  placeholder="Answer"
                  onChange={(e) => {
                    const faqs = [...(form.faqs ?? data.faqs ?? [])];
                    faqs[i] = { ...faqs[i], answer: e.target.value };
                    setForm({ ...form, faqs });
                  }}
                />
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    const faqs = [...(form.faqs ?? data.faqs ?? [])];
                    faqs.splice(i, 1);
                    setForm({ ...form, faqs });
                  }}
                >
                  Remove
                </Button>
              </div>
            ))}
            <Button
              variant="outline"
              onClick={() =>
                setForm({ ...form, faqs: [...(form.faqs ?? data.faqs ?? []), { question: "", answer: "" }] })
              }
            >
              Add FAQ
            </Button>
            <Button className="ml-2" onClick={() => save("business")} disabled={busy}>
              {busy ? "Saving…" : "Save FAQs"}
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label>{label}</Label>
      {children}
    </div>
  );
}
