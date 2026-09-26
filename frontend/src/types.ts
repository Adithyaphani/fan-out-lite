export type Status =
  | "queued" | "running" | "done" | "failed" | "needs_review" | "approved";

export interface Market {
  id: string; city: string; country: string;
  language: string; script: string;
  cultural_cues: string[]; music_style: string;
}
export interface Brand {
  product_name: string; category: string; palette: string[];
  style: string; product_refs: string[]; spec_notes: string;
  brand_sheet: string | null;
}
export interface Shot {
  id: string; role: string; description: string;
  start_s: number; end_s: number;
  master_image: string | null; status: Status;
}
export interface MarketBoard {
  market_id: string; shot_id: string; image: string | null;
  brand_score: number | null; status: Status;
}
export interface Clip {
  market_id: string; version: number;
  raw_video: string | null; track: string | null; final: string | null;
  approved: boolean; status: Status;
}
export interface EditOp {
  id: string; scope: string; target: string | null;
  instruction: string; source: string; created_at: string;
  applied: Record<string, string>;
}
export interface Timing { stage: string; started: string; ended: string | null; }

export interface SceneBible {
  run_id: string; brief: string; brand: Brand; markets: Market[];
  bpm: number; duration_s: number; aspect: string;
  concept: string; concept_approved: boolean;
  shots: Shot[]; boards: MarketBoard[]; clips: Clip[];
  edits: EditOp[]; timings: Timing[];
  phase: string; error: string | null; version: number; created_at: string;
}
