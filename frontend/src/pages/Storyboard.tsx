import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, assetUrl } from "../api";
import { useRun } from "../run";
import { useBible, usePipelineElapsed } from "../hooks/useBible";
import { StatusPill, fmtElapsed } from "../components";

export default function Storyboard() {
  const nav = useNavigate();
  const { runId } = useRun();
  const { bible } = useBible(runId);
  const elapsed = usePipelineElapsed(bible);
  const [sel, setSel] = useState<string>("s1");
  const [instr, setInstr] = useState("");
  const [rec, setRec] = useState(false);
  const [voiceBusy, setVoiceBusy] = useState(false);
  const [voiceMsg, setVoiceMsg] = useState<string | null>(null);
  const mediaRef = useRef<MediaRecorder | null>(null);
  const chunks = useRef<Blob[]>([]);

  if (!runId) return <Empty nav={nav} />;
  if (!bible) return <div className="card">Loading run…</div>;

  const shot = bible.shots.find((s) => s.id === sel) || bible.shots[0];
  const marketBoards = bible.boards.filter((b) => b.shot_id === sel);
  const storyEdits = bible.edits.filter((e) => e.scope === "storyboard_shot");
  const boardsReady = bible.shots.some((s) => s.master_image);

  const sendEdit = async (text: string, source = "text") => {
    if (!text.trim()) return;
    setInstr("");
    await api.storyboardEdit(runId, sel, text, source);
  };

  // Voice edit: non-blocking. Recording toggles live; on stop we transcribe and
  // fire the edit, which propagates across markets in the background (live).
  const startVoice = async () => {
    setVoiceMsg(null);
    if (!navigator.mediaDevices?.getUserMedia) {
      setVoiceMsg("This browser blocks mic capture (needs https or localhost). Type the edit instead.");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mr = new MediaRecorder(stream);
      chunks.current = [];
      mr.ondataavailable = (e) => e.data.size && chunks.current.push(e.data);
      mr.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        setVoiceBusy(true);
        setVoiceMsg("Transcribing…");
        try {
          const blob = new Blob(chunks.current, { type: mr.mimeType || "audio/webm" });
          const { text } = await api.transcribe(runId, blob);
          if (text) { setVoiceMsg(null); await sendEdit(text, "voice"); }
          else setVoiceMsg("Didn't catch that — try again.");
        } catch (e: any) {
          setVoiceMsg("Voice failed: " + (e.message || "transcription error"));
        } finally { setVoiceBusy(false); }
      };
      mr.start();
      mediaRef.current = mr;
      setRec(true);
    } catch {
      setVoiceMsg("Microphone permission denied — type the edit instead.");
    }
  };
  const stopVoice = () => { mediaRef.current?.stop(); setRec(false); };

  const render = async () => { await api.render(runId); nav("/manage"); };

  return (
    <>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: 18, flexWrap: "wrap", gap: 12 }}>
        <div>
          <div className="eyebrow">Step 2 · Storyboard</div>
          <h1 className="h1" style={{ margin: "8px 0 0" }}>6-shot master, localized {bible.markets.length}×</h1>
        </div>
        <div style={{ textAlign: "right" }}>
          <div className="muted" style={{ fontSize: 12 }}>Pipeline time</div>
          <div className="timer">{fmtElapsed(elapsed)}</div>
        </div>
      </div>

      {!boardsReady && (
        <div className="card soft" style={{ display: "flex", gap: 12, alignItems: "center", marginBottom: 16 }}>
          <span className="spinner" /> Generating the brand sheet and master storyboard…
        </div>
      )}

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="filmstrip">
          {bible.shots.map((s, i) => (
            <div key={s.id}>
              <button className={`frame ${s.id === sel ? "sel" : ""}`}
                onClick={() => setSel(s.id)} style={{ padding: 0, background: "var(--bg)", width: "100%" }}>
                <span className="idx">{i + 1} · {s.role}</span>
                {s.master_image
                  ? <img src={assetUrl(runId, s.master_image)} alt={s.role} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
                  : <span className="ph">{s.status === "running" ? "rendering…" : "queued"}</span>}
              </button>
              {s.end_s > s.start_s && (
                <div style={{ textAlign: "center", fontSize: 11, color: "var(--text-dim)", marginTop: 4, fontVariantNumeric: "tabular-nums" }}>
                  {s.start_s.toFixed(1)}–{s.end_s.toFixed(1)}s
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Timed scene bar — each segment's width is its share of the timeline */}
        <TimelineBar shots={bible.shots} duration={bible.duration_s} sel={sel} onSel={setSel} />
      </div>

      <div className="grid" style={{ gridTemplateColumns: "1.3fr 1fr", alignItems: "start" }}>
        <div className="card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div className="h2">
              Shot {shot.id} · {shot.role}
              {shot.end_s > shot.start_s && (
                <span className="muted" style={{ fontWeight: 400, fontSize: 14 }}> · {shot.start_s.toFixed(1)}–{shot.end_s.toFixed(1)}s</span>
              )} <StatusPill status={shot.status} />
            </div>
          </div>
          <p className="muted" style={{ marginTop: 4 }}>{shot.description}</p>
          <div className="grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(150px,1fr))", marginTop: 10 }}>
            {marketBoards.map((b) => {
              const m = bible.markets.find((x) => x.id === b.market_id);
              return (
                <div key={b.market_id}>
                  <div className="frame">
                    {b.image
                      ? <img src={assetUrl(runId, b.image)} alt={b.market_id} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
                      : <span className="ph">{b.status}</span>}
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", marginTop: 5, fontSize: 12 }}>
                    <b>{m?.city || b.market_id}</b>
                    {b.brand_score != null && <span className="muted">{b.brand_score.toFixed(0)}</span>}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="card">
          <div className="h2">Conversational edit</div>
          <p className="muted" style={{ marginTop: 0 }}>
            Edit shot <b>{sel}</b>; the change re-localizes across all {bible.markets.length} markets in seconds.
          </p>
          <div className="chat">
            {storyEdits.length === 0 && <div className="msg sys">No edits yet. Try "make the packaging pop more".</div>}
            {storyEdits.map((e) => (
              <div key={e.id}>
                <div className="msg user">{e.source === "voice" ? "🎙 " : ""}{e.instruction} <span className="muted">· {e.target}</span></div>
                <div className="msg sys">
                  {Object.keys(e.applied).length
                    ? `propagated → ${Object.entries(e.applied).map(([k, v]) => `${k}:${v}`).join("  ")}`
                    : "applying…"}
                </div>
              </div>
            ))}
          </div>
          <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
            <input type="text" placeholder={rec ? "listening…" : `Edit shot ${sel}…`} value={instr}
              onChange={(e) => setInstr(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && sendEdit(instr)} />
            {!rec
              ? <button className="btn sm ghost" onClick={startVoice} disabled={voiceBusy} title="Voice edit">
                  {voiceBusy ? <span className="spinner" /> : "🎙"}</button>
              : <button className="btn sm" onClick={stopVoice} title="Stop & apply"
                  style={{ borderColor: "var(--bad)" }}>
                  <span className="rec-dot" /> stop</button>}
            <button className="btn sm primary" onClick={() => sendEdit(instr)}>Send</button>
          </div>
          {(rec || voiceMsg) && (
            <p className="muted" style={{ fontSize: 12, marginTop: 8, display: "flex", alignItems: "center", gap: 6 }}>
              {rec && <><span className="rec-dot" /> recording — tap stop to apply</>}
              {!rec && voiceMsg}
            </p>
          )}

          <hr style={{ border: "none", borderTop: "1px solid var(--border)", margin: "18px 0" }} />
          <button className="btn primary" style={{ width: "100%" }} onClick={render} disabled={!boardsReady}>
            Render video & audio →
          </button>
          <p className="muted" style={{ fontSize: 12 }}>Omni animation + Lyria scoring run in parallel per market.</p>
        </div>
      </div>
    </>
  );
}

function TimelineBar({ shots, duration, sel, onSel }: {
  shots: { id: string; role: string; start_s: number; end_s: number; description: string }[];
  duration: number; sel: string; onSel: (id: string) => void;
}) {
  const timed = shots.filter((s) => s.end_s > s.start_s);
  if (timed.length === 0 || duration <= 0) return null;
  return (
    <div style={{ marginTop: 14 }}>
      <div className="muted" style={{ fontSize: 12, marginBottom: 6 }}>
        Timed scene breakdown · {duration}s
      </div>
      <div className="timeline">
        {timed.map((s, i) => {
          const pct = ((s.end_s - s.start_s) / duration) * 100;
          return (
            <button key={s.id} className={`tl-seg ${s.id === sel ? "sel" : ""}`}
              style={{ width: `${pct}%` }} onClick={() => onSel(s.id)}
              title={`${s.start_s.toFixed(1)}–${s.end_s.toFixed(1)}s · ${s.role}: ${s.description}`}>
              <span className="tl-role">{s.role}</span>
              <span className="tl-time">{s.start_s.toFixed(1)}s</span>
              {i === timed.length - 1 && <span className="tl-end">{s.end_s.toFixed(1)}s</span>}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function Empty({ nav }: { nav: (p: string) => void }) {
  return (
    <div className="card" style={{ textAlign: "center", padding: 48 }}>
      <div className="h2">No active run</div>
      <p className="muted">Start a campaign to generate storyboards.</p>
      <button className="btn primary" onClick={() => nav("/upload")}>Go to Upload</button>
    </div>
  );
}
