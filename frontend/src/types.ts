export interface StreamInfo {
  mode?: "values" | "updates" | string;
  update?: unknown;
}

export interface Counters {
  expected_chunks: number;
  notes_created: { current: number; total: number };
  integrated_image_notes_created: { current: number; total: number };
  formatted_notes_created: { current: number; total: number };
  timestamps_created: {
    current_items: number;
    chunks_completed: number;
    total_chunks: number;
  };
  image_insertions_created: {
    current_items: number;
    chunks_completed: number;
    total_chunks: number;
  };
  extracted_images_created: {
    current_items: number;
    chunks_completed: number;
    total_chunks: number;
  };
  finalization: {
    collected: boolean;
    summary: boolean;
    collected_notes_pdf: boolean;
    summary_pdf: boolean;
  };
  notes_by_type: {
    raw: number;
    integrated: number;
    formatted: number;
    collected: number;
    summary: number;
    exported_pdfs: number;
  };
}

export interface StateSnapshot {
  chunks?: string[];
  chunk_notes?: string[];
  image_integrated_notes?: string[];
  formatted_notes?: string[];
  collected_notes?: string;
  summary?: string;
  integrates?: unknown[];
  timestamps_output?: unknown[];
  image_insertions_output?: unknown[];
  extracted_images_output?: unknown[];
  collected_notes_pdf_path?: string;
  summary_pdf_path?: string;
}

export interface ProgressEventPayload {
  phase: string;
  progress: number;
  message: string;
  // Optional ISO timestamp from backend; if absent, frontend can synthesize
  timestamp?: string;
  data?: StateSnapshot;
  counters?: Counters;
  stream?: StreamInfo;
}

export interface RunRequestBody {
  video_id: string;
  video_path: string;
  num_chunks: number;
  provider: string;
  model: string;
  show_graph?: boolean;
  refresh_notes?: boolean;
  stream_config?: StreamConfig;
}

export interface StreamConfig {
  include_data?: boolean;
  include_fields?: string[];
  max_items_per_field?: number;
  max_chars_per_field?: number;
}

export interface FinalRunResponse extends ProgressEventPayload {}
