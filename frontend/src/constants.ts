export const STREAM_FIELDS = [
  "chunks",
  "chunk_notes",
  "image_integrated_notes",
  "formatted_notes",
  "collected_notes",
  "summary",
  "collected_notes_pdf_path",
  "summary_pdf_path",
  "timestamps_output",
  "image_insertions_output",
  "extracted_images_output",
  "integrates",
] as const;

export const DEFAULT_STREAM_FIELDS = [
  "formatted_notes",
  "summary",
  "collected_notes_pdf_path",
  "summary_pdf_path",
] as const;
