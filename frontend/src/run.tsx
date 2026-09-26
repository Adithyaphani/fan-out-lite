import { createContext, useContext, useEffect, useState } from "react";

/** The active run id, shared across pages and persisted so a reload keeps it. */
interface RunCtx {
  runId: string | null;
  setRunId: (id: string | null) => void;
}
const Ctx = createContext<RunCtx>({ runId: null, setRunId: () => {} });

export function RunProvider({ children }: { children: React.ReactNode }) {
  const [runId, setRunIdState] = useState<string | null>(() => {
    try { return localStorage.getItem("fanout_run") || null; } catch { return null; }
  });
  const setRunId = (id: string | null) => {
    setRunIdState(id);
    try { id ? localStorage.setItem("fanout_run", id) : localStorage.removeItem("fanout_run"); }
    catch { /* ignore */ }
  };
  return <Ctx.Provider value={{ runId, setRunId }}>{children}</Ctx.Provider>;
}

export const useRun = () => useContext(Ctx);
