import type { SceneBible, Status, Timing } from "./types";

export function StatusPill({ status }: { status: Status }) {
  const label = status.replace("_", " ");
  return (
    <span className={`pill ${status}`}>
      <span className="led" />
      {label}
    </span>
  );
}

export function fmtElapsed(s: number): string {
  const m = Math.floor(s / 60);
  const sec = s % 60;
  return m > 0 ? `${m}m ${sec.toFixed(0).padStart(2, "0")}s` : `${sec.toFixed(1)}s`;
}

const STAGE_LABELS: Record<string, string> = {
  brand_sheet: "Brand sheet",
  master_board: "Master board",
  market_boards: "Market boards",
  video: "Video",
  music: "Music",
  mux: "Mux",
};

export function StagePills({ timings }: { timings: Timing[] }) {
  // Collapse duplicate stage names to their latest occurrence.
  const latest = new Map<string, Timing>();
  for (const t of timings) latest.set(t.stage, t);
  const order = ["brand_sheet", "master_board", "market_boards", "video", "music", "mux"];
  const items = order.filter((s) => latest.has(s)).map((s) => latest.get(s)!);
  return (
    <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
      {items.map((t) => {
        const running = t.ended === null;
        const dur = t.ended
          ? (new Date(t.ended).getTime() - new Date(t.started).getTime()) / 1000
          : null;
        return (
          <span key={t.stage} className={`pill ${running ? "running" : "done"}`}>
            <span className="led" />
            {STAGE_LABELS[t.stage] || t.stage}
            {dur !== null && <span className="muted">· {dur.toFixed(1)}s</span>}
          </span>
        );
      })}
    </div>
  );
}

/** The scene-bible strip: palette, product, style, beat — the shared bible
 *  every model reads, which is why continuity holds across markets. */
export function BibleStrip({ bible, runId, assetUrl }: {
  bible: SceneBible; runId: string; assetUrl: (id: string, p: string | null) => string;
}) {
  const b = bible.brand;
  return (
    <div className="card soft" style={{ display: "flex", gap: 18, alignItems: "center", flexWrap: "wrap" }}>
      {b.brand_sheet && (
        <img src={assetUrl(runId, b.brand_sheet)} alt="brand sheet"
          style={{ width: 120, borderRadius: 10, border: "1px solid var(--border)" }} />
      )}
      <div style={{ minWidth: 160 }}>
        <div className="eyebrow">Scene bible</div>
        <div className="h2" style={{ marginTop: 4 }}>{b.product_name}</div>
        <div className="muted">{b.category}</div>
      </div>
      <div>
        <div className="muted" style={{ fontSize: 12, marginBottom: 6 }}>Palette</div>
        <div style={{ display: "flex", gap: 6 }}>
          {b.palette.length
            ? b.palette.map((c) => <span key={c} className="swatch" style={{ background: c }} title={c} />)
            : <span className="muted">—</span>}
        </div>
      </div>
      <div><div className="muted" style={{ fontSize: 12 }}>Style</div><div>{b.style}</div></div>
      <div><div className="muted" style={{ fontSize: 12 }}>Beat</div><div>{bible.bpm} BPM · {bible.duration_s}s · {bible.aspect}</div></div>
    </div>
  );
}
