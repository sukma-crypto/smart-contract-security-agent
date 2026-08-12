/** Bentuk data yang dikembalikan API Recens. */

export interface StepInfo {
  number: number;
  key: string;
  title: string;
  summary: string;
  mode: string;
  active: boolean;
  /** Termasuk yang ingin dikerjakan pengguna. Tidak pernah mengunci apa pun. */
  focused: boolean;
  note: string | null;
}

export interface FocusPreset {
  key: string;
  label: string;
  summary: string;
  steps: string[];
}

export interface WorkTypeCatalog {
  key: string;
  label: string;
  family: string;
  ciri_khas: string;
  fitur_utama: string[];
  default_target_words: number;
  hard_word_limit: number | null;
  citation_style: string;
  export_formats: string[];
  supervision_tracking: boolean;
  defense_mode: boolean;
  submission_kit: boolean;
  structure: string[];
}

export interface Catalog {
  work_types: WorkTypeCatalog[];
  research_types: { key: string; label: string; needs: string }[];
  steps: { number: number; key: string; title: string; summary: string }[];
  focus_presets: FocusPreset[];
  treatment: Record<string, Record<string, string>>;
  plans: Plan[];
  product_limits: { does: string; does_not: string; rule: string }[];
  credit_costs: Record<string, number>;
}

export interface Plan {
  key: string;
  label: string;
  suitable_for: string;
  credits: number;
  duration_days: number | null;
  project_limit: number | null;
  watermark: boolean;
  feature_access: string;
}

export interface Project {
  id: number;
  name: string;
  work_type: string;
  work_type_label: string;
  research_type: string;
  research_type_label: string;
  research_needs: string;
  field_of_study: string | null;
  target_words: number;
  word_count: number;
  deadline: string | null;
  citation_style: string;
  steps: StepInfo[];
  focus: string[];
  focus_key: string;
  focus_label: string;
  treatment: Record<string, string>;
  work_type_detail: {
    family: string;
    ciri_khas: string;
    fitur_utama: string[];
    hard_word_limit: number | null;
    export_formats: string[];
    supervision_tracking: boolean;
    defense_mode: boolean;
    submission_kit: boolean;
  };
  counts: {
    references: number;
    references_verified: number;
    datasets: number;
    analyses: number;
    revisions_open: number;
    versions: number;
  };
  active_ruleset: { id: number; name: string; kind: string } | null;
}

export interface ProjectSummary {
  id: number;
  name: string;
  work_type_label: string;
  word_count: number;
  target_words: number;
}

export interface Block {
  id: number;
  kind: string;
  position: number;
  content: string;
  meta: Record<string, unknown> & {
    caption?: string;
    columns?: string[];
    rows?: unknown[][];
    note?: string;
  };
  word_count: number;
}

export interface Section {
  id: number;
  number: string;
  level: number;
  title: string;
  role: string | null;
  status: string;
  target_words: number;
  word_count: number;
  blocks: Block[];
  children: Section[];
}

export interface Manuscript {
  project_id: number;
  sections: Section[];
  citekeys: string[];
  word_count: number;
}

export interface OutlineRow {
  id: number;
  number: string;
  level: number;
  title: string;
  role: string | null;
  status: string;
  word_count: number;
  target_words: number;
  progress: number;
  block_count: number;
}

export interface RuleSet {
  name: string;
  kind: string;
  page_size: string;
  margins: { top_cm: number; right_cm: number; bottom_cm: number; left_cm: number };
  font_family: string;
  font_size_pt: number;
  line_spacing: number;
  citation_style: string;
  citation_options: Record<string, string>;
  front_matter_numbering: string;
  body_numbering: string;
  table_caption_position: string;
  figure_caption_position: string;
  caption_numbering: string;
  max_words: number | null;
  max_pages: number | null;
  abstract_max_words: number | null;
  required_sections: string[];
  evidence: Record<string, string>;
  assumed: string[];
  include_toc: boolean;
}

export interface CslEntry {
  id?: string;
  title?: string | string[];
  author?: { family?: string; given?: string; literal?: string }[];
  issued?: { "date-parts": number[][] };
  "container-title"?: string | string[];
  DOI?: string;
  volume?: string;
  issue?: string;
  page?: string;
}

export interface Reference {
  id: number;
  citekey: string;
  source_db: string;
  verified: number;
  abstract: string | null;
  csl_json: CslEntry;
}

export interface SearchResultItem {
  entry: CslEntry;
  source_db: string;
  external_id: string;
  abstract: string;
  verified: boolean;
  citekey: string;
}

export interface AnalysisTable {
  title: string;
  columns: string[];
  rows: unknown[][];
  note: string;
}

export interface AnalysisResult {
  method: string;
  label: string;
  params: Record<string, unknown>;
  tables: AnalysisTable[];
  values: Record<string, unknown>;
  findings: string[];
  assumptions: string[];
  warnings: string[];
}

export interface AnalysisResponse {
  id: number;
  result: AnalysisResult;
  narrative: string;
  narrative_source: string;
  guardrail: { allowed: boolean; rule: string; reason: string } | null;
}

export interface Dataset {
  id: number;
  filename: string;
  kind: string;
  meta_json: { columns: string[]; n_rows: number; notes: string[] };
}

export interface Revision {
  id: number;
  text: string;
  source: string;
  author: string | null;
  status: string;
  section_title: string | null;
  created_at: string;
}

export interface Health {
  status: string;
  version: string;
  language_model: {
    available: boolean;
    provider: string;
    /** Penyedia mana yang kuncinya benar-benar terpasang. */
    providers: Record<string, boolean>;
    /** Model yang akan dipakai tiap jenjang hari ini, termurah lebih dulu. */
    tiers: Record<string, string[]>;
    budget: { harian_usd: number; bulanan_usd: number };
    note: string;
  };
  network: boolean;
}
