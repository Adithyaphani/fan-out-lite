import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, assetUrl } from "../api";
import { useRun } from "../run";
import { useBible, usePipelineElapsed } from "../hooks/useBible";
import { BibleStrip, StagePills, StatusPill, fmtElapsed } from "../components";

type Mode = "master" | "location";

export default function Manage() {
  const nav = useNavigate();
  const { runId } = useRun();
  const { bible } = useBible(runId);
  const elapsed = usePipelineElapsed(bible);
  const [mode, setMode] = useState<Mode>("master");
  const [selected, setSelected] = useState<string | null>(null);
  const [instr, setInstr] = useState("slow down the hero moment and add gentle rising steam");
  const [logLine, setLogLine] = useState<string | null>(null);

  const lastEdit = useMemo(
    () => bible?.edits.filter((e) => e.scope === "master_clip" || e.scope === "market_clip").slice(-1)[0] || null,
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
  const busy = bible.phase === "propagating";
  const needMarket = mode === "location" && !selected;
  const canApply = clipsReady && instr.trim().length > 0 && !busy && !needMarket;

  const apply = async () => {
    if (!canApply) return;
    setLogLine(null);
    const t0 = Date.now();
    const scope = mode === "master" ? "master_clip" : "market_clip";
    if (mode === "master") await api.masterEdit(runId, instr);
    else await api.marketEdit(runId, selected!, instr);

    const poll = setInterval(async () => {
      const b = await api.bible(runId);
      const last = b.edits.filter((e) => e.scope === scope).slice(-1)[0];
      if (!last) return;
      const need = mode === "master" ? b.markets.length : 1;
      if (Object.keys(last.applied).length >= need) {
        const done = Object.values(last.applied).filter((v) => v === "done").length;
        const secs = ((Date.now() - t0) / 1000).toFixed(0);
        setLogLine(
          mode === "master"
            ? `Applied "${instr}" to ${done}/${b.markets.length} markets · ${secs}s`
            : `Applied "${instr}" to ${cityOf(selected!)} only · ${secs}s`,
        );
        clearInterval(poll);
      }
    }, 1000);
  };

  const cityOf = (id: string) => bible.markets.find((m) => m.id === id)?.city || id;

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

      {mode === "location" && (
        <p className="muted" style={{ fontSize: 13, marginBottom: 10 }}>
          Location edit — click a market's video to select it, then apply a change to that market only.
        </p>
      )}

      <div className="market-grid" style={{ marginBottom: 20 }}>
        {bible.markets.map((m) => {
          const clip = bible.clips.find((c) => c.market_id === m.id);
          const board = bible.boards.find((b) => b.market_id === m.id && b.image);
          const applied = lastEdit?.applied[m.id];
          const isSel = mode === "location" && selected === m.id;
          const selectable = mode === "location";
          return (
            <div key={m.id}
              className="card"
              onClick={selectable ? () => setSelected(m.id) : undefined}
              style={{
                cursor: selectable ? "pointer" : "default",
                borderColor: isSel ? "var(--primary)" : undefined,
                boxShadow: isSel ? "0 0 0 2px var(--primary-soft)" : undefined,
              }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                <div><b>{m.city}</b> <span className="muted">{m.country}</span></div>
                {isSel ? <span className="pill done"><span className="led" /> selected</span>
                  : clip && <StatusPill status={clip.status} />}
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
              <label style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 10, fontSize: 13, cursor: "pointer" }}
                onClick={(e) => e.stopPropagation()}>
                <input type="checkbox" checked={clip?.approved || false} style={{ width: "auto" }}
                  onChange={(e) => api.approve(runId, m.id, e.target.checked)} />
                Approve for export
              </label>
            </div>
          );
        })}
      </div>

      <div className="card">
        {/* Mode switch */}
        <div style={{ display: "flex", gap: 6, marginBottom: 14 }}>
          <button className={`btn sm ${mode === "master" ? "primary" : "ghost"}`} onClick={() => setMode("master")}>
            Master edit — all markets
          </button>
          <button className={`btn sm ${mode === "location" ? "primary" : "ghost"}`} onClick={() => setMode("location")}>
            Location edit — one market
          </button>
        </div>

        <div className="h2">
          {mode === "master"
            ? "One instruction, every market"
            : selected ? `Edit ${cityOf(selected)} only` : "Select a market above"}
        </div>
        <p className="muted" style={{ marginTop: 0 }}>
          {mode === "master"
            ? "Omni replays the change across all clips at once; each market's localization, product and beat are preserved."
            : "The change is applied to the selected market's ad only; every other market is untouched."}
        </p>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <input type="text" value={instr} onChange={(e) => setInstr(e.target.value)} style={{ flex: 1, minWidth: 240 }}
            placeholder={needMarket ? "Pick a market first…" : "Describe the change…"}
            onKeyDown={(e) => e.key === "Enter" && canApply && apply()} />
          <button className="btn primary" onClick={apply} disabled={!canApply}>
            {busy ? <span className="spinner" /> : "⚡"}
            {mode === "master" ? " Apply to all markets" : ` Apply to ${selected ? cityOf(selected) : "…"}`}
          </button>
        </div>
        {!clipsReady && (
          <p className="muted" style={{ fontSize: 12, marginTop: 8 }}>
            Render the clips first (on the Storyboard page) — edits replay across finished clips.
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
