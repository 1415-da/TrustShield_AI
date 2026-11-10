"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { api, ApiError } from "@/lib/api";

export interface ApiState<T> {
  data: T | null;
  error: ApiError | null;
  loading: boolean;
  reload: () => Promise<void>;
  setData: (d: T | null) => void;
}

/** Minimal data-fetching hook. Pass `null` to skip. Optional polling interval in ms. */
export function useApi<T>(path: string | null, pollMs?: number): ApiState<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState<boolean>(!!path);
  const mounted = useRef(true);

  const load = useCallback(async () => {
    if (!path) return;
    try {
      const d = await api<T>(path);
      if (mounted.current) {
        setData(d);
        setError(null);
      }
    } catch (e) {
      if (mounted.current) setError(e instanceof ApiError ? e : new ApiError(0, "error", String(e)));
    } finally {
      if (mounted.current) setLoading(false);
    }
  }, [path]);

  useEffect(() => {
    mounted.current = true;
    setLoading(!!path);
    void load();
    if (!pollMs || !path) return () => void (mounted.current = false);
    const id = window.setInterval(() => void load(), pollMs);
    return () => {
      mounted.current = false;
      window.clearInterval(id);
    };
  }, [load, path, pollMs]);

  return { data, error, loading, reload: load, setData };
}
