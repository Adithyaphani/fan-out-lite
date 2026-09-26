import type { SceneBible } from "./types";

const BASE = "";

async function j<T>(r: Response): Promise<T> {
  if (!r.ok) throw new Error((await r.text()) || r.statusText);
  return r.json();
}

export interface Health {
  ok: boolean; has_api_key: boolean; has_fallback: boolean;
  models: { image: string; video: string; music: string };
  duration_s: number; bpm: number;
}

export const api = {
  health: () => fetch(`${BASE}/api/health`).then(j<Health>),

  markets: () => fetch(`${BASE}/api/markets`).then(j<{ markets: any[] }>),

  createRun: (form: FormData) =>
    fetch(`${BASE}/api/runs`, { method: "POST", body: form }).then(j<{ run_id: string }>),

  bible: (id: string) => fetch(`${BASE}/api/runs/${id}/bible`).then(j<SceneBible>),

  conceptEdit: (id: string, instruction: string, source = "text") =>
    fetch(`${BASE}/api/runs/${id}/concept/edit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ instruction, source }),
    }).then(j),

  conceptRegenerate: (id: string) =>
    fetch(`${BASE}/api/runs/${id}/concept/regenerate`, { method: "POST" }).then(j),

  conceptFinalize: (id: string) =>
    fetch(`${BASE}/api/runs/${id}/concept/finalize`, { method: "POST" }).then(j),

  render: (id: string) =>
    fetch(`${BASE}/api/runs/${id}/render`, { method: "POST" }).then(j),

  storyboardEdit: (id: string, shot_id: string, instruction: string, source = "text") =>
    fetch(`${BASE}/api/runs/${id}/storyboard/edit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ shot_id, instruction, source }),
    }).then(j),

  masterEdit: (id: string, instruction: string, source = "text") =>
    fetch(`${BASE}/api/runs/${id}/master-edit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ instruction, source }),
    }).then(j),

  approve: (id: string, market_id: string, approved: boolean) =>
    fetch(`${BASE}/api/runs/${id}/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ market_id, approved }),
    }).then(j),

  transcribe: (id: string, blob: Blob) => {
    const fd = new FormData();
    fd.append("audio", blob, "voice.webm");
    return fetch(`${BASE}/api/runs/${id}/transcribe`, { method: "POST", body: fd }).then(
      j<{ text: string }>,
    );
  },

  demo: () => fetch(`${BASE}/api/demo`, { method: "POST" }).then(j<{ run_id: string }>),
};

export const assetUrl = (runId: string, path: string | null) =>
  path ? `${BASE}/api/runs/${runId}/assets/${path}` : "";
