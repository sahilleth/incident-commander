import { useCallback, useEffect, useRef, useState } from "react";

export interface AutoRefreshOptions {
  /** Interval in ms between refreshes. */
  intervalMs?: number;
  /** When false the timer never runs (e.g. incident is resolved). */
  active?: boolean;
  /** Callback invoked on every tick. Should return a promise when async. */
  onRefresh: () => void | Promise<unknown>;
}

/**
 * Visibility-aware polling with a live countdown.
 * - Pauses while the browser tab is hidden and refreshes immediately on return.
 * - Skips a tick while a refresh is still in flight.
 * - Can be toggled off by the user without unmounting.
 */
export function useAutoRefresh({ intervalMs = 15_000, active = true, onRefresh }: AutoRefreshOptions) {
  const [enabled, setEnabled] = useState(true);
  const [visible, setVisible] = useState(true);
  const [secondsLeft, setSecondsLeft] = useState(Math.round(intervalMs / 1000));
  const [lastRefreshedAt, setLastRefreshedAt] = useState<number>(() => Date.now());
  const inFlight = useRef(false);
  const refreshRef = useRef(onRefresh);
  refreshRef.current = onRefresh;

  const run = useCallback(async () => {
    if (inFlight.current) return;
    inFlight.current = true;
    try {
      await refreshRef.current();
      setLastRefreshedAt(Date.now());
    } finally {
      inFlight.current = false;
      setSecondsLeft(Math.round(intervalMs / 1000));
    }
  }, [intervalMs]);

  useEffect(() => {
    if (typeof document === "undefined") return;
    const onChange = () => setVisible(document.visibilityState === "visible");
    onChange();
    document.addEventListener("visibilitychange", onChange);
    return () => document.removeEventListener("visibilitychange", onChange);
  }, []);

  const running = active && enabled && visible;

  useEffect(() => {
    if (!running) return;
    // Catch up right away when polling resumes (tab focus, toggle back on).
    void run();
    const id = setInterval(() => {
      setSecondsLeft((s) => {
        if (s <= 1) {
          void run();
          return Math.round(intervalMs / 1000);
        }
        return s - 1;
      });
    }, 1000);
    return () => clearInterval(id);
  }, [running, intervalMs, run]);

  return {
    enabled,
    setEnabled,
    running,
    paused: active && enabled && !visible,
    secondsLeft,
    lastRefreshedAt,
    refreshNow: run,
  };
}
