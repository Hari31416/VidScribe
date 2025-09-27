import { FormEvent, useCallback, useMemo, useRef, useState } from "react";
import { CountersPanel } from "./components/CountersPanel";
import { ProgressCard } from "./components/ProgressCard";
import { DEFAULT_STREAM_FIELDS, STREAM_FIELDS } from "./constants";
import { getFileDownloadUrl, runFinal, streamRun } from "./api/runGraph";
import type {
  Counters,
  ProgressEventPayload,
  RunRequestBody,
  StateSnapshot,
  StreamConfig,
} from "./types";

interface FormState {
  video_id: string;
  video_path: string;
  num_chunks: number;
  provider: string;
  model: string;
}

const DEFAULT_FORM: FormState = {
  video_id: "wjZofJX0v4M",
  video_path:
    "/home/hari/Desktop/VidScribe/backend/outputs/videos/wjZofJX0v4M/Transformers_the_tech_behind_LLMs_Deep_Learning_Chapter_5.mp4",
  num_chunks: 2,
  provider: "google",
  model: "gemini-2.0-flash",
};

const TERMINAL_PHASES = new Set(["done", "error", "cancelled"]);

type StreamHandle = { abort: () => void } | null;

export default function App() {
  const [form, setForm] = useState<FormState>(DEFAULT_FORM);
  const [compactMode, setCompactMode] = useState(true);
  const [includeFields, setIncludeFields] = useState<string[]>([
    ...DEFAULT_STREAM_FIELDS,
  ]);
  const [maxItems, setMaxItems] = useState<number>(3);
  const [maxChars, setMaxChars] = useState<number>(2000);
  const [refreshNotes, setRefreshNotes] = useState<boolean>(true);
  const [advancedOpen, setAdvancedOpen] = useState<boolean>(false);
  const [activeTab, setActiveTab] = useState<"notes" | "media" | "log">(
    "notes"
  );

  const [latestEvent, setLatestEvent] = useState<ProgressEventPayload>();
  const [events, setEvents] = useState<ProgressEventPayload[]>([]);
  const [snapshot, setSnapshot] = useState<StateSnapshot>();
  const [counters, setCounters] = useState<Counters>();
  const [error, setError] = useState<string | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [isSubmittingFinal, setIsSubmittingFinal] = useState(false);

  const streamHandleRef = useRef<StreamHandle>(null);
  const streamMode = latestEvent?.stream?.mode;

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

  const handleStreamProgress = useCallback((event: ProgressEventPayload) => {
    const stamped: ProgressEventPayload = {
      ...event,
      timestamp: event.timestamp ?? new Date().toISOString(),
    };
    setLatestEvent(stamped);
    setEvents((prev) => [...prev.slice(-98), stamped]);
    if (stamped.data) setSnapshot(stamped.data);
    if (stamped.counters) setCounters(stamped.counters);
    if (TERMINAL_PHASES.has(stamped.phase)) {
      setIsStreaming(false);
      streamHandleRef.current = null;
    }
  }, []);

  const handleStreamError = useCallback((err: unknown) => {
    setError(err instanceof Error ? err.message : String(err));
    setIsStreaming(false);
    streamHandleRef.current = null;
  }, []);

  const handleSubmitStream = useCallback(
    async (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      setError(null);
      if (streamHandleRef.current) {
        streamHandleRef.current.abort();
        streamHandleRef.current = null;
      }
      const body: RunRequestBody = {
        ...form,
        num_chunks: Number(form.num_chunks) || 1,
        refresh_notes: refreshNotes,
      };
      const streamConfig = buildStreamConfig();
      if (streamConfig) body.stream_config = streamConfig;
      setEvents([]);
      setLatestEvent(undefined);
      setSnapshot(undefined);
      setCounters(undefined);
      setIsStreaming(true);
      try {
        const handle = await streamRun(
          body,
          handleStreamProgress,
          handleStreamError
        );
        streamHandleRef.current = handle;
      } catch (err) {
        handleStreamError(err);
      }
    },
    [
      buildStreamConfig,
      form,
      handleStreamError,
      handleStreamProgress,
      refreshNotes,
    ]
  );

  const handleCancel = useCallback(() => {
    streamHandleRef.current?.abort();
    streamHandleRef.current = null;
    setIsStreaming(false);
  }, []);

  const handleRunFinal = useCallback(async () => {
    setIsSubmittingFinal(true);
    setError(null);
    try {
      const body: RunRequestBody = {
        ...form,
        num_chunks: Number(form.num_chunks) || 1,
        refresh_notes: refreshNotes,
        stream_config: buildStreamConfig(),
      };
      const result = await runFinal(body);
      const stamped: ProgressEventPayload = {
        ...result,
        timestamp: result.timestamp ?? new Date().toISOString(),
      };
      setLatestEvent(stamped);
      setSnapshot(stamped.data);
      setCounters(stamped.counters);
      setEvents((prev) => [...prev.slice(-98), stamped]);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setIsSubmittingFinal(false);
    }
  }, [buildStreamConfig, form, refreshNotes]);

  const disableControls = isStreaming;
  const activeEvents = useMemo(
    () =>
      events.map((evt, index) => ({
        id: `${index}-${evt.phase}-${evt.progress}`,
        phase: evt.phase,
        progress: evt.progress,
        message: evt.message,
        timestamp: evt.timestamp,
      })),
    [events]
  );

  return (
    <div className="max-w-[1400px] mx-auto px-4 py-8 space-y-6">
      <header className="space-y-1">
        <h1 className="text-3xl font-extrabold">
          VidScribe Orchestration Dashboard
        </h1>
        <p className="text-slate-600">
          Drive the LangGraph pipeline via the FastAPI backend, monitor progress
          in real time, and inspect the generated notes.
        </p>
      </header>

      <div className="grid grid-cols-1 lg:[grid-template-columns:1fr_1.8fr_1.2fr] gap-6">
        {/* Left: Configuration */}
        <section className="card h-fit">
          <h2 className="text-xl font-semibold mb-4">
            Configuration & Controls
          </h2>
          <form className="space-y-4" onSubmit={handleSubmitStream}>
            <div className="space-y-2">
              <label className="label">Video ID</label>
              <input
                className="input"
                value={form.video_id}
                onChange={(e) =>
                  setForm((p) => ({ ...p, video_id: e.target.value }))
                }
                placeholder="e.g., FOONnnq975k"
                disabled={disableControls}
                required
              />
            </div>
            <div className="space-y-2">
              <label className="label">Video Path</label>
              <textarea
                className="input min-h-36"
                value={form.video_path}
                onChange={(e) =>
                  setForm((p) => ({ ...p, video_path: e.target.value }))
                }
                placeholder="Absolute path to the downloaded mp4"
                disabled={disableControls}
                required
              />
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
                <select
                  className="input"
                  value={form.model}
                  onChange={(e) =>
                    setForm((p) => ({ ...p, model: e.target.value }))
                  }
                  disabled={disableControls}
                >
                  {[
                    "gemini-2.0-flash",
                    "gpt-4o-mini",
                    "llama-3.1-8b",
                    "mixtral-8x7b",
                    form.model,
                  ]
                    .filter((v, i, a) => a.indexOf(v) === i)
                    .map((opt) => (
                      <option key={opt} value={opt}>
                        {opt}
                      </option>
                    ))}
                </select>
              </div>
            </div>
            {/* Advanced settings */}
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
                      onClick={() => setRefreshNotes((v) => !v)}
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
                      onClick={() => setCompactMode((v) => !v)}
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
                                    ? Array.from(new Set([...prev, field]))
                                    : prev.filter((i) => i !== field)
                                )
                              }
                              disabled={disableControls || !compactMode}
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
                        disabled={disableControls || !compactMode}
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
                        disabled={disableControls || !compactMode}
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
                onClick={handleRunFinal}
                disabled={isStreaming || isSubmittingFinal}
              >
                {isSubmittingFinal ? "Running…" : "Run Final Stage Only"}
              </button>
              <button
                className="btn btn-secondary"
                type="button"
                onClick={handleCancel}
                disabled={!isStreaming}
              >
                Cancel
              </button>
            </div>
          </form>
        </section>

        {/* Center: Monitoring & Key Output */}
        <div className="space-y-6">
          <section className="card">
            <ProgressCard
              latest={latestEvent}
              streamMode={streamMode}
              isStreaming={isStreaming}
              counters={counters}
            />
          </section>
          <section className="card">
            <h2 className="text-lg font-semibold mb-4">Statistics</h2>
            <CountersPanel counters={counters} />
          </section>
          <section className="card">
            <h2 className="text-lg font-semibold mb-2">Summary</h2>
            <textarea
              className="input min-h-48"
              placeholder="Generated summary will appear here"
              readOnly
              value={snapshot?.summary ?? ""}
            />
          </section>
          {error && (
            <section className="card border border-red-200">
              <h2 className="text-lg font-semibold text-red-700">Errors</h2>
              <p className="text-red-600">{error}</p>
            </section>
          )}
        </div>

        {/* Right: Detailed Results & Logs */}
        <section className="card h-fit">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-semibold">Detailed Results</h2>
          </div>
          <div className="flex border-b border-slate-200 mb-4">
            <button
              className={`px-3 py-2 text-sm font-semibold border-b-2 -mb-px ${
                activeTab === "notes"
                  ? "border-violet-600 text-violet-700"
                  : "border-transparent text-slate-500"
              }`}
              onClick={() => setActiveTab("notes")}
            >
              Formatted Notes
            </button>
            <button
              className={`px-3 py-2 text-sm font-semibold border-b-2 -mb-px ${
                activeTab === "media"
                  ? "border-violet-600 text-violet-700"
                  : "border-transparent text-slate-500"
              }`}
              onClick={() => setActiveTab("media")}
            >
              Media & Timestamps
            </button>
            <button
              className={`px-3 py-2 text-sm font-semibold border-b-2 -mb-px ${
                activeTab === "log"
                  ? "border-violet-600 text-violet-700"
                  : "border-transparent text-slate-500"
              }`}
              onClick={() => setActiveTab("log")}
            >
              Event Log
            </button>
          </div>
          {activeTab === "notes" && (
            <div className="space-y-4">
              <div className="flex flex-wrap gap-3">
                <button
                  className="btn btn-secondary"
                  type="button"
                  disabled={!snapshot?.collected_notes_pdf_path}
                  onClick={() => {
                    const p = snapshot?.collected_notes_pdf_path;
                    if (p) window.open(getFileDownloadUrl(p), "_blank");
                  }}
                >
                  Download Collected Notes PDF
                </button>
                <button
                  className="btn btn-secondary"
                  type="button"
                  disabled={!snapshot?.summary_pdf_path}
                  onClick={() => {
                    const p = snapshot?.summary_pdf_path;
                    if (p) window.open(getFileDownloadUrl(p), "_blank");
                  }}
                >
                  Download Summary PDF
                </button>
              </div>
              <label className="label">Formatted Notes</label>
              <textarea
                className="input min-h-[320px]"
                readOnly
                value={(snapshot?.formatted_notes || []).join("\n\n")}
                placeholder="No formatted notes yet."
              />
            </div>
          )}
          {activeTab === "media" && (
            <div className="space-y-4">
              <div>
                <div className="label mb-1">Timestamps</div>
                <pre className="bg-slate-900 text-slate-100 p-3 rounded-xl overflow-auto text-sm">
                  {JSON.stringify(snapshot?.timestamps_output ?? [], null, 2)}
                </pre>
              </div>
              <div>
                <div className="label mb-1">Image Insertions</div>
                <pre className="bg-slate-900 text-slate-100 p-3 rounded-xl overflow-auto text-sm">
                  {JSON.stringify(
                    snapshot?.image_insertions_output ?? [],
                    null,
                    2
                  )}
                </pre>
              </div>
              <div>
                <div className="label mb-1">Extracted Images</div>
                <pre className="bg-slate-900 text-slate-100 p-3 rounded-xl overflow-auto text-sm">
                  {JSON.stringify(
                    snapshot?.extracted_images_output ?? [],
                    null,
                    2
                  )}
                </pre>
              </div>
            </div>
          )}
          {activeTab === "log" && (
            <div className="space-y-2">
              {activeEvents.length === 0 ? (
                <small className="muted">No events yet.</small>
              ) : (
                <ul className="space-y-1 max-h-[420px] overflow-auto pr-2">
                  {activeEvents.map((evt) => {
                    const tone =
                      evt.phase === "error"
                        ? "text-red-600"
                        : evt.phase === "done"
                        ? "text-emerald-600"
                        : /warn|slow/i.test(evt.message)
                        ? "text-amber-600"
                        : "text-slate-700";
                    const ts = (() => {
                      try {
                        const d = new Date((evt as any).timestamp as string);
                        if (Number.isNaN(d.getTime())) return null;
                        return d.toLocaleTimeString(undefined, {
                          hour12: false,
                        });
                      } catch {
                        return null;
                      }
                    })();
                    return (
                      <li key={evt.id} className={`text-sm ${tone}`}>
                        {ts && <span className="opacity-60 mr-1">[{ts}]</span>}
                        <span className="font-semibold">
                          [{evt.phase}]
                        </span>{" "}
                        <span className="opacity-70">{evt.progress}%</span> –{" "}
                        {evt.message}
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
