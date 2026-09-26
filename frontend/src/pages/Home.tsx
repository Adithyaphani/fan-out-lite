import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type Health } from "../api";
import { useRun } from "../run";

const FEATURES = [
  { t: "One brief, many markets", d: "Upload the product once. Get a finished, localized video ad for every market in a single loop." },
  { t: "Chained GenMedia pipeline", d: "NB2 Lite storyboards → Omni animation → Lyria scoring → ffmpeg mux, all locked to one scene bible." },
  { t: "Edit once, propagate everywhere", d: "Speak or type one change and watch every market's clip update at once." },
];

export default function Home() {
  const nav = useNavigate();
  const { setRunId } = useRun();
  const [health, setHealth] = useState<Health | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => { api.health().then(setHealth).catch(() => {}); }, []);

  const seeItInAction = async () => {
    setBusy(true); setErr(null);
    try {
      const { run_id } = await api.demo();
      setRunId(run_id);
      nav("/manage");
    } catch (e: any) {
      setErr("No pre-rendered fallback yet — run scripts/prerender.py in the backend.");
    } finally { setBusy(false); }
  };

  return (
    <>
      <div style={{ maxWidth: 720, margin: "40px auto 44px", textAlign: "center" }}>
        <div className="eyebrow">Multimodal creative pipelines · GenMedia</div>
        <h1 className="h1" style={{ fontSize: 44, marginTop: 14 }}>
          A localized ad engine that goes <span style={{ color: "var(--primary)" }}>wide</span> in one loop.
        </h1>
        <p className="muted" style={{ fontSize: 16 }}>
          Marketers need one campaign in many markets. Today that takes weeks.
          Fan-Out Lite does it in a single chained run — storyboard, animate, score and mux
          a finished ad for four markets at once.
        </p>
        <div style={{ display: "flex", gap: 12, justifyContent: "center", marginTop: 24, flexWrap: "wrap" }}>
          <button className="btn primary" onClick={() => nav("/upload")}>Start a new campaign →</button>
          <button className="btn ghost" onClick={seeItInAction} disabled={busy}>
            {busy ? <span className="spinner" /> : "▶"} See it in action
          </button>
        </div>
        {err && <p style={{ color: "var(--warn)", marginTop: 14 }}>{err}</p>}
      </div>

      <div className="grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))" }}>
        {FEATURES.map((f) => (
          <div key={f.t} className="card">
            <div className="h2">{f.t}</div>
            <p className="muted" style={{ margin: 0 }}>{f.d}</p>
          </div>
        ))}
      </div>

      {health && (
        <div className="card soft" style={{ marginTop: 22, display: "flex", gap: 20, flexWrap: "wrap", fontSize: 13 }}>
          <span className="pill"><span className="led" style={{ background: health.has_api_key ? "var(--good)" : "var(--bad)" }} />
            API key {health.has_api_key ? "loaded" : "missing"}</span>
          <span className="muted">image · <b>{health.models.image}</b></span>
          <span className="muted">video · <b>{health.models.video}</b></span>
          <span className="muted">music · <b>{health.models.music}</b></span>
          <span className="muted">{health.bpm} BPM · {health.duration_s}s</span>
          {health.has_fallback && <span className="pill"><span className="led" style={{ background: "var(--good)" }} />fallback ready</span>}
        </div>
      )}
    </>
  );
}
