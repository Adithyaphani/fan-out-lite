import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { useRun } from "../run";
import { useBible } from "../hooks/useBible";

const LABELS = ["TAGLINE", "CONCEPT", "HERO MOMENT", "WHY IT TRAVELS"];

function ConceptView({ text }: { text: string }) {
  // Render the plain-text concept, highlighting the section labels.
  const lines = text.split("\n").filter((l) => l.trim());
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      {lines.map((line, i) => {
        const m = LABELS.find((l) => line.toUpperCase().startsWith(l));
        if (m) {
          const body = line.slice(line.indexOf(":") + 1).trim();
          return (
            <div key={i}>
              <div className="eyebrow" style={{ marginBottom: 2 }}>{m}</div>
              <div style={{ fontSize: m === "TAGLINE" ? 22 : 14, fontWeight: m === "TAGLINE" ? 800 : 400, letterSpacing: m === "TAGLINE" ? "-0.02em" : 0 }}>{body}</div>
            </div>
          );
        }
        return <div key={i} className="muted">{line}</div>;
      })}
    </div>
  );
}

export default function Concept() {
  const nav = useNavigate();
  const { runId } = useRun();
  const { bible } = useBible(runId);
  const [instr, setInstr] = useState("");
  const [rec, setRec] = useState(false);
  const [voiceBusy, setVoiceBusy] = useState(false);
  const [voiceMsg, setVoiceMsg] = useState<string | null>(null);
  const [finalizing, setFinalizing] = useState(false);
  const mediaRef = useRef<MediaRecorder | null>(null);
  const chunks = useRef<Blob[]>([]);

  if (!runId) return (
    <div className="card" style={{ textAlign: "center", padding: 48 }}>
      <div className="h2">No active run</div>
      <button className="btn primary" onClick={() => nav("/upload")}>Go to Upload</button>
    </div>
  );
  if (!bible) return <div className="card">Loading run…</div>;

  const conceptEdits = bible.edits.filter((e) => e.scope === "concept");
  const generating = bible.phase === "concepting";
  const ready = !!bible.concept && !generating;

  const sendEdit = async (text: string, source = "text") => {
    if (!text.trim()) return;
    setInstr("");
    await api.conceptEdit(runId, text, source);
  };

  const startVoice = async () => {
    setVoiceMsg(null);
    if (!navigator.mediaDevices?.getUserMedia) {
      setVoiceMsg("Mic blocked here (needs https or localhost). Type instead."); return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mr = new MediaRecorder(stream);
      chunks.current = [];
      mr.ondataavailable = (e) => e.data.size && chunks.current.push(e.data);
      mr.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        setVoiceBusy(true); setVoiceMsg("Transcribing…");
        try {
          const blob = new Blob(chunks.current, { type: mr.mimeType || "audio/webm" });
          const { text } = await api.transcribe(runId, blob);
          if (text) { setVoiceMsg(null); await sendEdit(text, "voice"); }
          else setVoiceMsg("Didn't catch that — try again.");
        } catch (e: any) { setVoiceMsg("Voice failed: " + (e.message || "error")); }
        finally { setVoiceBusy(false); }
      };
      mr.start(); mediaRef.current = mr; setRec(true);
    } catch { setVoiceMsg("Microphone permission denied — type instead."); }
  };
  const stopVoice = () => { mediaRef.current?.stop(); setRec(false); };

  const regenerate = () => api.conceptRegenerate(runId);
  const finalize = async () => {
    setFinalizing(true);
    await api.conceptFinalize(runId);
    nav("/storyboard");
  };

  return (
    <>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: 18, flexWrap: "wrap", gap: 12 }}>
        <div>
          <div className="eyebrow">Step 2 · Concept</div>
          <h1 className="h1" style={{ margin: "8px 0 0" }}>Shape the idea before we shoot it</h1>
        </div>
        <div className="pill"><span className="led" style={{ background: "var(--primary)" }} />
          {bible.duration_s}s · {bible.markets.length} markets</div>
      </div>

      <div className="grid" style={{ gridTemplateColumns: "1.3fr 1fr", alignItems: "start" }}>
        <div className="card" style={{ minHeight: 260 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
            <div className="h2">Creative concept</div>
            <button className="btn sm ghost" onClick={regenerate} disabled={generating}>↻ Regenerate</button>
          </div>
          {generating || !bible.concept ? (
            <div className="card soft" style={{ display: "flex", gap: 12, alignItems: "center" }}>
              <span className="spinner" /> Generating a concept from your product, brief, palette and markets…
            </div>
          ) : (
            <ConceptView text={bible.concept} />
          )}
        </div>

        <div className="card">
          <div className="h2">Refine by chat or voice</div>
          <p className="muted" style={{ marginTop: 0 }}>
            e.g. "make it brighter", "focus on the morning ritual", "punchier tagline".
          </p>
          <div className="chat">
            {conceptEdits.length === 0 && <div className="msg sys">No edits yet. Tweak the concept, then finalize.</div>}
            {conceptEdits.map((e) => (
              <div key={e.id}>
                <div className="msg user">{e.source === "voice" ? "🎙 " : ""}{e.instruction}</div>
                <div className="msg sys">
                  {e.applied.concept === "done" ? "updated ✓" : e.applied.concept === "failed" ? "failed" : "applying…"}
                </div>
              </div>
            ))}
          </div>
          <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
            <input type="text" placeholder={rec ? "listening…" : "Refine the concept…"} value={instr}
              onChange={(e) => setInstr(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && sendEdit(instr)} disabled={!ready} />
            {!rec
              ? <button className="btn sm ghost" onClick={startVoice} disabled={voiceBusy || !ready} title="Voice edit">
                  {voiceBusy ? <span className="spinner" /> : "🎙"}</button>
              : <button className="btn sm" onClick={stopVoice} style={{ borderColor: "var(--bad)" }}>
                  <span className="rec-dot" /> stop</button>}
            <button className="btn sm primary" onClick={() => sendEdit(instr)} disabled={!ready}>Send</button>
          </div>
          {(rec || voiceMsg) && (
            <p className="muted" style={{ fontSize: 12, marginTop: 8, display: "flex", alignItems: "center", gap: 6 }}>
              {rec && <><span className="rec-dot" /> recording — tap stop to apply</>}
              {!rec && voiceMsg}
            </p>
          )}

          <hr style={{ border: "none", borderTop: "1px solid var(--border)", margin: "18px 0" }} />
          <button className="btn primary" style={{ width: "100%" }} onClick={finalize} disabled={!ready || finalizing}>
            {finalizing ? <span className="spinner" /> : null}
            {finalizing ? "Generating storyboards…" : "Finalize & generate storyboards →"}
          </button>
          <p className="muted" style={{ fontSize: 12 }}>
            The approved concept guides the brand sheet and all {bible.markets.length} localized storyboards.
          </p>
        </div>
      </div>
    </>
  );
}
