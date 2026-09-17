"use client";

import { useRef } from "react";
import useSWR, { type SWRResponse } from "swr";
import { get } from "@/lib/api";

export type PollingResult<T> = SWRResponse<T, any> & {
  isStale: boolean;
  dataUpdatedAt: number | null;
};

/**
 * Polls every `interval` ms only while the document is visible.
 * SWR's refreshWhenHidden=false pauses polling when hidden.
 */
export function usePolling<T>(path: string | null, interval = 5000): PollingResult<T> {
  const updatedAt = useRef<number | null>(null);
  const swr = useSWR<T>(path, (p: string) => get(p), {
    refreshInterval: interval,
    refreshWhenHidden: false,
    refreshWhenOffline: false,
    revalidateOnFocus: true,
    keepPreviousData: true,
    onSuccess: () => {
      updatedAt.current = Date.now();
    },
  });
  return Object.assign(swr, {
    isStale: !swr.isLoading && !swr.isValidating && !!swr.data,
    dataUpdatedAt: updatedAt.current,
  });
}
