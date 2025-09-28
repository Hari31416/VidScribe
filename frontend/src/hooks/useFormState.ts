import { useCallback, useState } from "react";
import type { RunRequestBody, StreamConfig } from "../types";
import { DEFAULT_STREAM_FIELDS } from "../constants";

export interface FormState {
  video_id: string;
  video_path: string;
  num_chunks: number;
  provider: string;
  model: string;
}

export const DEFAULT_FORM: FormState = {
  video_id: "wjZofJX0v4M",
  video_path:
    "/home/hari/Desktop/VidScribe/backend/outputs/videos/wjZofJX0v4M/Transformers_the_tech_behind_LLMs_Deep_Learning_Chapter_5.mp4",
  num_chunks: 2,
  provider: "google",
  model: "gemini-2.0-flash",
};

export function useFormState() {
  const [form, setForm] = useState<FormState>(DEFAULT_FORM);

  // Advanced/stream preferences
  const [compactMode, setCompactMode] = useState(true);
  const [includeFields, setIncludeFields] = useState<string[]>([
    ...DEFAULT_STREAM_FIELDS,
  ]);
  const [maxItems, setMaxItems] = useState<number>(3);
  const [maxChars, setMaxChars] = useState<number>(2000);
  const [refreshNotes, setRefreshNotes] = useState<boolean>(true);
  const [advancedOpen, setAdvancedOpen] = useState<boolean>(false);

  const buildStreamConfig = useCallback((): StreamConfig | undefined => {
    if (!compactMode) return undefined;
    const normalizedFields = Array.from(
      new Set([
        ...(includeFields.length ? includeFields : []),
        "collected_notes_pdf_path",
        "summary_pdf_path",
      ])
    );
    const config: StreamConfig = {
      include_data: true,
      include_fields: normalizedFields,
    };
    if (Number.isFinite(maxItems) && maxItems >= 0)
      config.max_items_per_field = maxItems;
    if (Number.isFinite(maxChars) && maxChars >= 0)
      config.max_chars_per_field = maxChars;
    return config;
  }, [compactMode, includeFields, maxChars, maxItems]);

  const makeRunBody = useCallback(
    (opts?: { includeStreamConfig?: boolean }): RunRequestBody => {
      const base: RunRequestBody = {
        ...form,
        num_chunks: Number(form.num_chunks) || 1,
        refresh_notes: refreshNotes,
      };
      if (opts?.includeStreamConfig) {
        const sc = buildStreamConfig();
        if (sc) base.stream_config = sc;
      }
      return base;
    },
    [buildStreamConfig, form, refreshNotes]
  );

  return {
    // core form
    form,
    setForm,
    // advanced settings
    compactMode,
    setCompactMode,
    includeFields,
    setIncludeFields,
    maxItems,
    setMaxItems,
    maxChars,
    setMaxChars,
    refreshNotes,
    setRefreshNotes,
    advancedOpen,
    setAdvancedOpen,
    // helpers
    buildStreamConfig,
    makeRunBody,
  } as const;
}
