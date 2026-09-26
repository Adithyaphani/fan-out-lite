import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, assetUrl } from "../api";
import { useRun } from "../run";
import { useBible, usePipelineElapsed } from "../hooks/useBible";
import { BibleStrip, StagePills, StatusPill, fmtElapsed } from "../components";

export default function Manage() {
  const nav = useNavigate();
  const { runId } = useRun();
  const { bible } = useBible(runId);
  const elapsed = usePipelineElapsed(bible);
  const [instr, setInstr] = useState("slow down the hero moment and add gentle rising steam");
  const [logLine, setLogLine] = useState<string | null>(null);

  const lastMaster = useMemo(
    () => bible?.edits.filter((e) => e.scope === "master_clip").slice(-1)[0] || null,
    [bible?.version],
  );

  if (!runId) return (
    <div className="card" style={{ textAlign: "center", padding: 48 }}>
      <div className="h2">No active run</div>
      <button className="btn primary" onClick={() => nav("/")}>Home</button>
    </div>
  );
  if (!bible) return <div className="card">Loading run…</div>;

  const clipsReady = bible.clips.some((c) => c.raw_video);
  const canPropagate = clipsReady && instr.trim().length > 0 && bible.phase !== "propagating";

  const propagate = async () => {
    if (!instr.trim() || !clipsReady) return;
    setLogLine(null);
    const t0 = Date.now();
    await api.masterEdit(runId, instr);
    // The log line resolves once propagation lands; useBible drives the rest.
    const poll = setInterval(async () => {
      const b = await api.bible(runId);
      const last = b.edits.filter((e) => e.scope === "master_clip").slice(-1)[0];
      if (last && Object.keys(last.applied).length >= b.markets.length) {
        const done = Object.values(last.applied).filter((v) => v === "done").length;
        setLogLine(`Applied "${instr}" and propagated to ${done}/${b.markets.length} clips · ${((Date.now() - t0) / 1000).toFixed(0)}s`);
        clearInterval(poll);
      }
    }, 1000);
  };

  return (
    <>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: 16, flexWrap: "wrap", gap: 12 }}>
        <div>
          <div className="eyebrow">Step 3 · Manage & export</div>
          <h1 className="h1" style={{ margin: "8px 0 0" }}>{bible.markets.length} markets · one product · one beat</h1>
        </div>
        <div style={{ textAlign: "right" }}>
          <div className="muted" style={{ fontSize: 12 }}>Pipeline time · phase {bible.phase}</div>
          <div className="timer">{fmtElapsed(elapsed)}</div>
        </div>
      </div>

      <div style={{ marginBottom: 14 }}><StagePills timings={bible.timings} /></div>
      <div style={{ marginBottom: 18 }}>
        <BibleStrip bible={bible} runId={runId} assetUrl={assetUrl} />
      </div>

      <div className="market-grid" style={{ marginBottom: 20 }}>
        {bible.markets.map((m) => {
          const clip = bible.clips.find((c) => c.market_id === m.id);
          const board = bible.boards.find((b) => b.market_id === m.id && b.image);
          const applied = lastMaster?.applied[m.id];
          return (
            <div key={m.id} className="card">
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                <div><b>{m.city}</b> <span className="muted">{m.country}</span></div>
                {clip && <StatusPill status={clip.status} />}
              </div>
              {clip?.final ? (
                <video src={assetUrl(runId, clip.final)} controls loop muted playsInline
                  key={`${clip.final}?v=${clip.version}`} />
              ) : board ? (
                <div className="frame"><img src={assetUrl(runId, board.image)} style={{ width: "100%", height: "100%", objectFit: "cover" }} /></div>
              ) : (
                <div className="frame"><span className="ph">waiting…</span></div>
              )}
              <div className="muted" style={{ fontSize: 12, marginTop: 8 }}>🎵 {m.music_style}</div>
              {applied && (
                <div className={`pill ${applied === "done" ? "done" : applied === "failed" ? "failed" : "running"}`} style={{ marginTop: 8 }}>
                  <span className="led" /> edit {applied}
                </div>
              )}
              <label style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 10, fontSize: 13, cursor: "pointer" }}>
                <input type="checkbox" checked={clip?.approved || false} style={{ width: "auto" }}
                  onChange={(e) => api.approve(runId, m.id, e.target.checked)} />
                Approve for export
              </label>
            </div>
          );
        })}
      </div>

      <div className="card">
        <div className="h2">Master edit — one instruction, every market</div>
        <p className="muted" style={{ marginTop: 0 }}>
          Omni replays the change across all clips at once; localization, product and beat are preserved.
        </p>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <input type="text" value={instr} onChange={(e) => setInstr(e.target.value)} style={{ flex: 1, minWidth: 240 }}
            onKeyDown={(e) => e.key === "Enter" && canPropagate && propagate()} />
          <button className="btn primary" onClick={propagate} disabled={!canPropagate}>
            {bible.phase === "propagating" ? <span className="spinner" /> : "⚡"} Apply to all markets
          </button>
        </div>
        {!clipsReady && (
          <p className="muted" style={{ fontSize: 12, marginTop: 8 }}>
            Render the clips first (on the Storyboard page) — a master edit replays across finished clips.
          </p>
        )}
        {logLine && (
          <div className="pill done" style={{ marginTop: 14 }}><span className="led" /> {logLine}</div>
        )}
        {bible.error && <p style={{ color: "var(--bad)" }}>Error: {bible.error}</p>}
      </div>
    </>
  );
}
