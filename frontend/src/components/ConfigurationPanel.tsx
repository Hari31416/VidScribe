import { FormEvent } from "react";
import { STREAM_FIELDS } from "../constants";
import type { FormState } from "../hooks/useFormState";
import { UploadPanel } from "./UploadPanel";
import { StorageManagement } from "./StorageManagement";

interface Props {
  form: FormState;
  setForm: React.Dispatch<React.SetStateAction<FormState>>;
  compactMode: boolean;
  setCompactMode: (v: boolean | ((p: boolean) => boolean)) => void;
  includeFields: string[];
  setIncludeFields: React.Dispatch<React.SetStateAction<string[]>>;
  maxItems: number;
  setMaxItems: (n: number) => void;
  maxChars: number;
  setMaxChars: (n: number) => void;
  refreshNotes: boolean;
  setRefreshNotes: (v: boolean | ((p: boolean) => boolean)) => void;
  advancedOpen: boolean;
  setAdvancedOpen: (v: boolean | ((p: boolean) => boolean)) => void;

  onSubmit: (e: FormEvent<HTMLFormElement>) => void;
  onRunFinal: () => void;
  onCancel: () => void;
  isStreaming: boolean;
  isSubmittingFinal: boolean;
}

export function ConfigurationPanel(props: Props) {
  const {
    form,
    setForm,
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
    onSubmit,
    onRunFinal,
    onCancel,
    isStreaming,
    isSubmittingFinal,
  } = props;

  const disableControls = isStreaming;

  const handleUploadSuccess = (videoId: string, videoPath: string) => {
    setForm((p) => ({ ...p, video_id: videoId }));
  };

  return (
    <section className="card h-fit">
      <h2 className="text-xl font-semibold mb-4">Configuration & Controls</h2>
      <form className="space-y-4" onSubmit={onSubmit}>
        {/* Upload Panel */}
        <UploadPanel
          onUploadSuccess={handleUploadSuccess}
          disabled={disableControls}
        />

        {/* Storage Management Panel */}
        <StorageManagement disabled={disableControls} />

        <div className="space-y-2">
          <label className="label">Video ID</label>
          <input
            className="input"
            value={form.video_id}
            onChange={(e) =>
              setForm((p) => ({ ...p, video_id: e.target.value }))
            }
            placeholder="e.g., FOONnnq975k or upload_xyz123"
            disabled={disableControls}
            required
          />
          <p className="text-xs text-slate-500">
            Use a YouTube video ID or an uploaded video ID (from above)
          </p>
        </div>
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <label className="label">Number of Chunks</label>
            <span className="text-sm text-slate-500 font-medium">
              {form.num_chunks}
            </span>
          </div>
          <input
            type="range"
            min={1}
            max={10}
            step={1}
            value={form.num_chunks}
            disabled={disableControls}
            onChange={(e) =>
              setForm((p) => ({
                ...p,
                num_chunks: Math.max(1, Number(e.target.value)),
              }))
            }
            className="w-full accent-violet-600"
          />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-2">
            <label className="label">Provider</label>
            <select
              className="input"
              value={form.provider}
              onChange={(e) =>
                setForm((p) => ({ ...p, provider: e.target.value }))
              }
              disabled={disableControls}
            >
              <option value="google">Google</option>
              <option value="openai">OpenAI</option>
              <option value="openrouter">OpenRouter</option>
              <option value="groq">Groq</option>
            </select>
          </div>
          <div className="space-y-2">
            <label className="label">Model</label>
            <input
              className="input"
              type="text"
              value={form.model}
              onChange={(e) =>
                setForm((p) => ({ ...p, model: e.target.value }))
              }
              placeholder="Enter model name, e.g., gemini-2.0-flash"
              disabled={disableControls}
              required
            />
          </div>
        </div>
        <div className="border border-slate-200 rounded-xl">
          <button
            type="button"
            className="w-full flex items-center justify-between px-4 py-3"
            onClick={() => setAdvancedOpen((v) => !v)}
          >
            <span className="font-semibold">Advanced Settings</span>
            <span className="text-slate-500 text-sm">
              {advancedOpen ? "Hide" : "Show"}
            </span>
          </button>
          {advancedOpen && (
            <div className="px-4 pb-4 space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <div className="label">Refresh Notes</div>
                  <div className="label-desc">
                    Force regeneration of downstream artifacts
                  </div>
                </div>
                <button
                  type="button"
                  role="switch"
                  aria-checked={refreshNotes}
                  onClick={() =>
                    setRefreshNotes((v: any) =>
                      typeof v === "function" ? v : !refreshNotes
                    )
                  }
                  disabled={disableControls}
                  className={`relative inline-flex h-6 w-11 items-center rounded-full transition ${
                    refreshNotes ? "bg-violet-600" : "bg-slate-300"
                  }`}
                >
                  <span
                    className={`inline-block h-5 w-5 transform rounded-full bg-white transition ${
                      refreshNotes ? "translate-x-5" : "translate-x-1"
                    }`}
                  />
                </button>
              </div>
              <div className="flex items-center justify-between">
                <div>
                  <div className="label">Compact Streaming Mode</div>
                  <div className="label-desc">
                    Limit payload sizes for large runs
                  </div>
                </div>
                <button
                  type="button"
                  role="switch"
                  aria-checked={compactMode}
                  onClick={() =>
                    setCompactMode((v: any) =>
                      typeof v === "function" ? v : !compactMode
                    )
                  }
                  disabled={disableControls}
                  className={`relative inline-flex h-6 w-11 items-center rounded-full transition ${
                    compactMode ? "bg-violet-600" : "bg-slate-300"
                  }`}
                >
                  <span
                    className={`inline-block h-5 w-5 transform rounded-full bg-white transition ${
                      compactMode ? "translate-x-5" : "translate-x-1"
                    }`}
                  />
                </button>
              </div>
              <div>
                <div className="label mb-2">Include Fields in Stream</div>
                <div className="flex flex-wrap gap-2">
                  {STREAM_FIELDS.map((field) => {
                    const checked = includeFields.includes(field);
                    return (
                      <label
                        key={field}
                        className={`chip ${
                          checked ? "bg-indigo-100" : "opacity-70"
                        }`}
                      >
                        <input
                          className="mr-1 accent-indigo-600"
                          type="checkbox"
                          checked={checked}
                          onChange={(e) =>
                            setIncludeFields((prev) =>
                              e.target.checked
                                ? Array.from(
                                    new Set([...(prev as string[]), field])
                                  )
                                : (prev as string[]).filter((i) => i !== field)
                            )
                          }
                          disabled={!compactMode || disableControls}
                        />
                        {field}
                      </label>
                    );
                  })}
                </div>
                <p className="text-xs muted mt-1">
                  PDF paths are always included in compact mode.
                </p>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="label">Max Items per Field</label>
                  <input
                    className="input"
                    type="number"
                    value={maxItems}
                    onChange={(e) =>
                      setMaxItems(
                        Number.isNaN(Number(e.target.value))
                          ? -1
                          : Number(e.target.value)
                      )
                    }
                    disabled={!compactMode || disableControls}
                  />
                </div>
                <div className="space-y-1">
                  <label className="label">Max Characters per Field</label>
                  <input
                    className="input"
                    type="number"
                    value={maxChars}
                    onChange={(e) =>
                      setMaxChars(
                        Number.isNaN(Number(e.target.value))
                          ? -1
                          : Number(e.target.value)
                      )
                    }
                    disabled={!compactMode || disableControls}
                  />
                </div>
              </div>
            </div>
          )}
        </div>
        <div className="flex flex-wrap gap-3 pt-2">
          <button
            className="btn btn-primary"
            type="submit"
            disabled={isStreaming}
          >
            {isStreaming ? "Streaming…" : "Run Pipeline"}
          </button>
          <button
            className="btn btn-secondary"
            type="button"
            onClick={onRunFinal}
            disabled={isStreaming || isSubmittingFinal}
          >
            {isSubmittingFinal ? "Running…" : "Run Final Stage Only"}
          </button>
          <button
            className="btn btn-secondary"
            type="button"
            onClick={onCancel}
            disabled={!isStreaming}
          >
            Cancel
          </button>
        </div>
      </form>
    </section>
  );
}
