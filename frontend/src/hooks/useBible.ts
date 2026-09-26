import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { SceneBible } from "../types";

/** Poll the scene bible ~once a second. The bible is the source of truth,
 *  so the whole UI is a pure function of this state. */
export function useBible(runId: string | null, intervalMs = 1000) {
  const [bible, setBible] = useState<SceneBible | null>(null);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<number | null>(null);

  useEffect(() => {
    if (!runId) return;
    let alive = true;
    const tick = async () => {
      try {
        const b = await api.bible(runId);
        if (alive) { setBible(b); setError(null); }
      } catch (e: any) {
        if (alive) setError(e.message);
      }
    };
    tick();
    timer.current = window.setInterval(tick, intervalMs);
    return () => {
      alive = false;
      if (timer.current) window.clearInterval(timer.current);
    };
  }, [runId, intervalMs]);

  return { bible, error };
}

/** Live elapsed time (seconds) computed from bible.timings — survives page
 *  switches because it is derived from persisted start/end timestamps. */
export function usePipelineElapsed(bible: SceneBible | null) {
  const [, force] = useState(0);
  useEffect(() => {
    const t = window.setInterval(() => force((n) => n + 1), 250);
    return () => window.clearInterval(t);
  }, []);
  if (!bible || bible.timings.length === 0) return 0;
  const starts = bible.timings.map((t) => new Date(t.started).getTime());
  const start = Math.min(...starts);
  // In a terminal phase the clock freezes at the last recorded end, even if a
  // crashed stage never wrote its `ended` — so the timer can't run away.
  const terminal = ["rendered", "done", "failed"].includes(bible.phase);
  const anyRunning = bible.timings.some((t) => t.ended === null);
  const ends = bible.timings.filter((t) => t.ended).map((t) => new Date(t.ended!).getTime());
  const lastEnd = ends.length ? Math.max(...ends) : start;
  const end = anyRunning && !terminal ? Date.now() : lastEnd;
  return Math.max(0, (end - start) / 1000);
}
