"use client";

import { AlertCircle, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";

export function PageHeader({
  title,
  subtitle,
  updatedAt,
  right,
}: {
  title: string;
  subtitle?: string;
  updatedAt?: string | null;
  right?: React.ReactNode;
}) {
  return (
    <div className="mb-6 flex items-start justify-between gap-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {subtitle && <p className="mt-0.5 text-sm text-muted-foreground">{subtitle}</p>}
        {updatedAt && (
          <p className="mt-1 text-xs text-muted-foreground/70">
            Last updated {new Date(updatedAt).toLocaleTimeString()}
          </p>
        )}
      </div>
      {right}
    </div>
  );
}

export function LoadingState() {
  return (
    <div className="flex items-center gap-2 py-12 text-sm text-muted-foreground" role="status">
      <Loader2 className="h-4 w-4 animate-spin" /> Loading…
    </div>
  );
}

export function EmptyState({ message }: { message: string }) {
  return (
    <div className="rounded-xl border border-dashed py-12 text-center text-sm text-muted-foreground">
      {message}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  return (
    <div className="flex items-center gap-3 rounded-xl border border-destructive/30 bg-destructive/5 p-4 text-sm" role="alert">
      <AlertCircle className="h-4 w-4 text-destructive" />
      <span className="flex-1">{(error as Error)?.message ?? "Something went wrong"}</span>
      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry}>
          Retry
        </Button>
      )}
    </div>
  );
}
