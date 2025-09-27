import { FormEvent, useCallback, useMemo, useRef, useState } from "react";
import { CountersPanel } from "./components/CountersPanel";
import { Outputs } from "./components/Outputs";
import { ProgressCard } from "./components/ProgressCard";
import { DEFAULT_STREAM_FIELDS, STREAM_FIELDS } from "./constants";
import { runFinal, streamRun } from "./api/runGraph";
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
    if (!compactMode) {
      return undefined;
    }

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

    if (Number.isFinite(maxItems) && maxItems >= 0) {
      config.max_items_per_field = maxItems;
    }
    if (Number.isFinite(maxChars) && maxChars >= 0) {
      config.max_chars_per_field = maxChars;
    }

    return config;
  }, [compactMode, includeFields, maxChars, maxItems]);

  const handleStreamProgress = useCallback((event: ProgressEventPayload) => {
    setLatestEvent(event);
    setEvents((prev) => [...prev.slice(-98), event]);
    if (event.data) {
      setSnapshot(event.data);
    }
    if (event.counters) {
      setCounters(event.counters);
    }
    if (TERMINAL_PHASES.has(event.phase)) {
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
      if (streamConfig) {
        body.stream_config = streamConfig;
      }

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
      setLatestEvent(result);
      setSnapshot(result.data);
      setCounters(result.counters);
      setEvents((prev) => [...prev.slice(-98), result]);
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
      })),
    [events]
  );

  return (
    <div className="container">
      <header>
        <h1>VidScribe Orchestration Dashboard</h1>
        <p>
          Drive the LangGraph pipeline via the FastAPI backend, monitor progress
          in real time, and inspect the generated notes.
        </p>
      </header>

      <section>
        <form className="form-grid" onSubmit={handleSubmitStream}>
          <label>
            Video ID
            <input
              value={form.video_id}
              onChange={(e) =>
                setForm((prev) => ({ ...prev, video_id: e.target.value }))
              }
              placeholder="e.g., FOONnnq975k"
              disabled={disableControls}
              required
            />
          </label>

          <label>
            Video path
            <textarea
              value={form.video_path}
              onChange={(e) =>
                setForm((prev) => ({ ...prev, video_path: e.target.value }))
              }
              placeholder="Absolute path to the downloaded mp4"
              disabled={disableControls}
              required
            />
          </label>

          <label>
            Number of chunks
            <input
              type="number"
              min={1}
              value={form.num_chunks}
              onChange={(e) =>
                setForm((prev) => ({
                  ...prev,
                  num_chunks: Math.max(1, Number(e.target.value)),
                }))
              }
              disabled={disableControls}
              required
            />
          </label>

          <label>
            Provider
            <select
              value={form.provider}
              onChange={(e) =>
                setForm((prev) => ({ ...prev, provider: e.target.value }))
              }
              disabled={disableControls}
            >
              <option value="google">google</option>
              <option value="openai">openai</option>
              <option value="openrouter">openrouter</option>
              <option value="groq">groq</option>
            </select>
          </label>

          <label>
            Model
            <input
              value={form.model}
              onChange={(e) =>
                setForm((prev) => ({ ...prev, model: e.target.value }))
              }
              disabled={disableControls}
            />
          </label>

          <label>
            Refresh notes on rerun?
            <span>Force regeneration of downstream artifacts.</span>
            <input
              type="checkbox"
              checked={refreshNotes}
              onChange={(e) => setRefreshNotes(e.target.checked)}
              disabled={disableControls}
            />
          </label>

          <label>
            Compact streaming mode
            <span>Limit payload sizes for large runs.</span>
            <input
              type="checkbox"
              checked={compactMode}
              onChange={(e) => setCompactMode(e.target.checked)}
              disabled={disableControls}
            />
          </label>

          <div>
            <span>Include fields in stream</span>
            <div className="checkbox-group">
              {STREAM_FIELDS.map((field) => {
                const checked = includeFields.includes(field);
                return (
                  <label key={field} className="checkbox-chip">
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={(e) => {
                        setIncludeFields((prev) => {
                          if (e.target.checked) {
                            return Array.from(new Set([...prev, field]));
                          }
                          return prev.filter((item) => item !== field);
                        });
                      }}
                      disabled={disableControls || !compactMode}
                    />
                    {field}
                  </label>
                );
              })}
            </div>
            <small className="muted">
              PDF paths are always included in compact mode to match backend
              behavior.
            </small>
          </div>

          <label>
            Max items per field
            <input
              type="number"
              value={maxItems}
              onChange={(e) => {
                const next = Number(e.target.value);
                setMaxItems(Number.isNaN(next) ? -1 : next);
              }}
              disabled={disableControls || !compactMode}
            />
          </label>

          <label>
            Max characters per field
            <input
              type="number"
              value={maxChars}
              onChange={(e) => {
                const next = Number(e.target.value);
                setMaxChars(Number.isNaN(next) ? -1 : next);
              }}
              disabled={disableControls || !compactMode}
            />
          </label>

          <div className="actions">
            <button className="primary" type="submit" disabled={isStreaming}>
              {isStreaming ? "Streaming…" : "Start streaming"}
            </button>
            <button
              className="secondary"
              type="button"
              onClick={handleRunFinal}
              disabled={isStreaming || isSubmittingFinal}
            >
              {isSubmittingFinal ? "Running…" : "Run final only"}
            </button>
            <button
              className="secondary"
              type="button"
              onClick={handleCancel}
              disabled={!isStreaming}
            >
              Cancel
            </button>
          </div>
        </form>
      </section>

      <section>
        <ProgressCard
          latest={latestEvent}
          streamMode={streamMode}
          isStreaming={isStreaming}
        />
      </section>

      {error && (
        <section>
          <h2>Errors</h2>
          <p style={{ color: "#b91c1c" }}>{error}</p>
        </section>
      )}

      <section>
        <h2>Outputs</h2>
        <Outputs state={snapshot} />
      </section>

      <section>
        <h2>Statistics</h2>
        <CountersPanel counters={counters} />
      </section>

      <section>
        <h2>Event log</h2>
        {activeEvents.length === 0 ? (
          <small className="muted">No events yet.</small>
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Phase</th>
                  <th>Progress</th>
                  <th>Message</th>
                </tr>
              </thead>
              <tbody>
                {activeEvents.map((evt) => (
                  <tr key={evt.id}>
                    <td>{evt.phase}</td>
                    <td>{evt.progress}%</td>
                    <td>{evt.message}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
