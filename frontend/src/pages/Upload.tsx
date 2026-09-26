import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { useRun } from "../run";

interface MarketOpt {
  id: string; city: string; country: string;
  language: string; music_style: string;
}

const CATEGORY_OPTIONS = [
  "premium canned coffee", "energy drink", "sparkling water", "craft beer",
  "skincare serum", "fragrance", "sneakers", "smartphone", "headphones",
  "chocolate bar", "artisan tea", "protein shake",
];
const STYLE_OPTIONS = [
  "warm cinematic product macro", "clean minimal studio", "bold neon night",
  "natural daylight lifestyle", "luxury dark and moody", "playful pop colour",
  "retro film grain", "high-gloss futuristic",
];
const DEFAULT_MARKETS = ["IN", "BR", "KR", "NG"];

function fmtDur(s: number): string {
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  const r = s % 60;
  return r ? `${m}m ${r}s` : `${m}m`;
}

// Mirrors the backend: each scene <= 10s, clamped to [3, 12].
function sceneCount(s: number): number {
  return Math.max(3, Math.min(12, Math.ceil(s / 10)));
}

// The browser's `accept` attribute is only a filter hint — many OS file
// pickers still let the user choose "All Files" and bypass it, so we also
// validate every selected file's actual MIME type before accepting it.
function isImageFile(f: File): boolean {
  return f.type.startsWith("image/");
}

/** A real dropdown with preset options plus an "Other (type your own)" escape. */
function DropdownField({ label, value, onChange, options }: {
  label: string; value: string; onChange: (v: string) => void; options: string[];
}) {
  const isCustom = value !== "" && !options.includes(value);
  const [custom, setCustom] = useState(isCustom);
  return (
    <label className="fld">
      <span>{label}</span>
      <select value={custom || isCustom ? "__custom__" : value}
        onChange={(e) => {
          if (e.target.value === "__custom__") { setCustom(true); onChange(""); }
          else { setCustom(false); onChange(e.target.value); }
        }}>
        {options.map((o) => <option key={o} value={o}>{o}</option>)}
        <option value="__custom__">Other (type your own)…</option>
      </select>
      {(custom || isCustom) && (
        <input type="text" placeholder="Type your own…" value={value} autoFocus
          onChange={(e) => onChange(e.target.value)} style={{ marginTop: 8 }} />
      )}
    </label>
  );
}

export default function Upload() {
  const nav = useNavigate();
  const { setRunId } = useRun();
  const [files, setFiles] = useState<File[]>([]);
  const [fileError, setFileError] = useState<string | null>(null);
  const [name, setName] = useState("Aura Cold Brew");
  const [category, setCategory] = useState("premium canned coffee");
  const [brief, setBrief] = useState("Launch a single hero concept, localized to many markets, premium and cinematic.");
  const [style, setStyle] = useState("warm cinematic product macro");
  const [duration, setDuration] = useState(6);
  const [palette, setPalette] = useState<string[]>(["#0B0D10", "#FF6B35", "#F4E9DD"]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const [catalog, setCatalog] = useState<MarketOpt[]>([]);
  const [selected, setSelected] = useState<string[]>(DEFAULT_MARKETS);
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);

  useEffect(() => {
    api.markets().then((r) => setCatalog(r.markets as MarketOpt[])).catch(() => {});
  }, []);

  const addFiles = (picked: File[]) => {
    const images = picked.filter(isImageFile);
    const rejected = picked.length - images.length;
    setFileError(rejected > 0
      ? `${rejected} file${rejected > 1 ? "s" : ""} skipped — only image files are accepted.`
      : null);
    if (images.length) setFiles((prev) => [...prev, ...images]);
  };
  const removeFile = (index: number) =>
    setFiles((prev) => prev.filter((_, i) => i !== index));

  // Memoized so object URLs are created once per file set and revoked on change/unmount.
  const previews = useMemo(() => files.map((f) => URL.createObjectURL(f)), [files]);
  useEffect(() => () => previews.forEach(URL.revokeObjectURL), [previews]);

  const grouped = useMemo(() => {
    const q = query.trim().toLowerCase();
    const hits = catalog.filter(
      (m) => !q || m.city.toLowerCase().includes(q) || m.country.toLowerCase().includes(q),
    );
    const by: Record<string, MarketOpt[]> = {};
    for (const m of hits) (by[m.country] ||= []).push(m);
    return by;
  }, [catalog, query]);

  const toggle = (id: string) =>
    setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));
  const remove = (id: string) => setSelected((s) => s.filter((x) => x !== id));
  const cityById = (id: string) => catalog.find((m) => m.id === id);

  const submit = async () => {
    if (!name.trim()) { setErr("Product name is required."); return; }
    if (selected.length === 0) { setErr("Pick at least one city."); return; }
    setBusy(true); setErr(null);
    try {
      const fd = new FormData();
      fd.append("product_name", name);
      fd.append("category", category);
      fd.append("brief", brief);
      fd.append("style", style);
      fd.append("duration_s", String(duration));
      fd.append("markets", selected.join(","));
      fd.append("palette", palette.join(","));
      files.forEach((f) => fd.append("images", f));
      const { run_id } = await api.createRun(fd);
      setRunId(run_id);
      nav("/concept");
    } catch (e: any) {
      setErr(e.message || "Failed to create run");
    } finally { setBusy(false); }
  };

  return (
    <div className="grid" style={{ gridTemplateColumns: "1.3fr 1fr", alignItems: "start" }}>
      <div className="card">
        <div className="eyebrow">Step 1 · Campaign brief</div>
        <h1 className="h1" style={{ marginTop: 10 }}>Upload product & brief</h1>

        <label className="fld">
          <span>Product photos (attached to every model call for brand fidelity)</span>
          <input type="file" accept="image/*" multiple
            onChange={(e) => {
              addFiles(Array.from(e.target.files || []));
              e.target.value = ""; // allow re-selecting the same file after removal
            }} />
        </label>
        {fileError && (
          <p style={{ color: "var(--bad)", fontSize: 13, marginTop: -8 }}>{fileError}</p>
        )}
        {previews.length > 0 && (
          <div style={{ display: "flex", gap: 8, marginBottom: 16, flexWrap: "wrap" }}>
            {previews.map((p, i) => (
              <div key={i} style={{ position: "relative" }}>
                <img src={p} style={{ width: 84, height: 84, objectFit: "cover", borderRadius: 8, border: "1px solid var(--border)" }} />
                <button type="button" onClick={() => removeFile(i)} aria-label="Remove image"
                  style={{
                    position: "absolute", top: -6, right: -6, width: 20, height: 20,
                    borderRadius: "50%", border: "1px solid var(--border)", background: "var(--bg-elev2)",
                    color: "var(--text)", cursor: "pointer", display: "flex", alignItems: "center",
                    justifyContent: "center", fontSize: 12, lineHeight: 1, padding: 0,
                  }}>
                  ×
                </button>
              </div>
            ))}
          </div>
        )}

        <label className="fld">
          <span>Product name</span>
          <input type="text" value={name} onChange={(e) => setName(e.target.value)} />
        </label>

        <div className="row" style={{ flexWrap: "wrap" }}>
          <div style={{ flex: 1, minWidth: 200 }}>
            <DropdownField label="Category" value={category} onChange={setCategory} options={CATEGORY_OPTIONS} />
          </div>
          <div style={{ flex: 1, minWidth: 200 }}>
            <DropdownField label="Visual style" value={style} onChange={setStyle} options={STYLE_OPTIONS} />
          </div>
        </div>

        <label className="fld">
          <span>Creative brief</span>
          <textarea rows={3} value={brief} onChange={(e) => setBrief(e.target.value)} />
        </label>

        {/* Timeline duration bar — up to 2 minutes */}
        <label className="fld">
          <span style={{ display: "flex", justifyContent: "space-between" }}>
            <span>Ad duration (timeline)</span>
            <b style={{ color: "var(--primary)" }}>{fmtDur(duration)}</b>
          </span>
          <input type="range" min={3} max={120} step={1} value={duration}
            onChange={(e) => setDuration(Number(e.target.value))} className="range" />
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "var(--text-dim)", marginTop: 4 }}>
            <span>3s</span><span>30s</span><span>60s</span><span>90s</span><span>2m</span>
          </div>
          <p className="muted" style={{ fontSize: 12, marginTop: 6 }}>
            The ad is split into {sceneCount(duration)} timed scenes; each is animated as its own
            clip (≤10s, the model's cap) and stitched into the full {fmtDur(duration)}.
            {duration > 30 && " Longer ads mean more clips and slower renders."}
          </p>
        </label>
      </div>

      <div className="grid">
        <div className="card">
          <div className="h2">Markets & cities</div>
          <p className="muted" style={{ marginTop: 0 }}>
            Search a city or country and add as many as you like — the master concept fans out to each.
          </p>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 10 }}>
            {selected.length === 0 && <span className="muted" style={{ fontSize: 13 }}>No cities selected.</span>}
            {selected.map((id) => {
              const m = cityById(id);
              return (
                <span key={id} className="chip">
                  {m ? m.city : id}
                  <button className="chip-x" onClick={() => remove(id)} aria-label={`remove ${id}`}>×</button>
                </span>
              );
            })}
          </div>
          <div className="combo">
            <input type="text" placeholder="Search cities or countries…" value={query}
              onFocus={() => setOpen(true)}
              onChange={(e) => { setQuery(e.target.value); setOpen(true); }} />
            {open && (
              <div className="combo-menu">
                {Object.keys(grouped).length === 0 && <div className="combo-empty">No matches</div>}
                {Object.entries(grouped).map(([country, cities]) => (
                  <div key={country}>
                    <div className="combo-group">{country}</div>
                    {cities.map((m) => {
                      const on = selected.includes(m.id);
                      return (
                        <button key={m.id} className={`combo-item ${on ? "on" : ""}`} onClick={() => toggle(m.id)}>
                          <span>{m.city}</span>
                          <span className="muted" style={{ fontSize: 11 }}>{m.music_style}</span>
                          {on && <span className="combo-check">✓</span>}
                        </button>
                      );
                    })}
                  </div>
                ))}
                <button className="combo-close" onClick={() => setOpen(false)}>Done</button>
              </div>
            )}
          </div>
          <p className="muted" style={{ fontSize: 12, marginTop: 8 }}>
            {selected.length} {selected.length === 1 ? "city" : "cities"} · more cities = longer render.
          </p>
        </div>

        <div className="card">
          <div className="h2">Palette</div>
          <p className="muted" style={{ marginTop: 0 }}>Enforced across every market. Hover a swatch to remove it.</p>
          <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
            {palette.map((c, i) => (
              <div key={i} className="swatch-edit">
                <input type="color" value={c}
                  onChange={(e) => setPalette((p) => p.map((x, j) => (j === i ? e.target.value : x)))} />
                <button className="swatch-x" onClick={() => setPalette((p) => p.filter((_, j) => j !== i))}
                  aria-label="remove colour" title="Remove colour">×</button>
              </div>
            ))}
            <button className="btn sm ghost" onClick={() => setPalette((p) => [...p, "#888888"])}>+ add</button>
          </div>
        </div>

        <button className="btn primary" style={{ padding: "14px" }} onClick={submit} disabled={busy}>
          {busy ? <span className="spinner" /> : null}
          {busy ? "Creating run…" : "Generate concept →"}
        </button>
        {err && <p style={{ color: "var(--bad)" }}>{err}</p>}
        <p className="muted" style={{ fontSize: 12, marginTop: -4 }}>
          Next: we generate an editable creative concept from your inputs, then storyboards.
        </p>
      </div>
    </div>
  );
}
