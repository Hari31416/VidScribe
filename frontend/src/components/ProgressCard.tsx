import type { Counters, ProgressEventPayload } from "../types";

interface Props {
  latest?: ProgressEventPayload;
  streamMode?: string;
  isStreaming: boolean;
  counters?: Counters;
}

export function ProgressCard({
  latest,
  streamMode,
  isStreaming,
  counters,
}: Props) {
  const progress = latest?.progress ?? 0;
  const message = latest?.message ?? "Waiting for updates…";

  const steps = [
    { key: "transcript", label: "Transcript" },
    { key: "notes", label: "Notes" },
    { key: "media", label: "Media" },
    { key: "format", label: "Formatting" },
    { key: "final", label: "Finalize" },
  ];

  const stepIndex = (() => {
    if (!counters) return 0;
    // Finalization is considered done if any finalize signals are true
    if (
      counters.finalization.summary_pdf ||
      counters.finalization.collected_notes_pdf ||
      counters.finalization.summary ||
      counters.finalization.collected
    )
      return 5;

    // Formatting is considered complete (green) when all formatted notes are created
    const formattingComplete =
      counters.formatted_notes_created.total > 0 &&
      counters.formatted_notes_created.current >=
        counters.formatted_notes_created.total;
    if (formattingComplete) return 4; // Mark Formatting as completed (green)

    // Formatting in progress
    if (counters.formatted_notes_created.current > 0) return 3;
    if (
      counters.extracted_images_created.current_items > 0 ||
      counters.timestamps_created.current_items > 0
    )
      return 2;
    if (counters.notes_created.current > 0) return 1;
    return 0;
  })();

  return (
    <div className="space-y-4">
      {/* Stepper */}
      <ol className="flex items-center justify-between">
        {steps.map((s, i) => {
          const active = i < stepIndex;
          const current = i === stepIndex - 1 || (stepIndex === 0 && i === 0);
          return (
            <li key={s.key} className="flex-1 flex items-center">
              <div
                className={`flex items-center gap-2 ${
                  active
                    ? "text-emerald-600"
                    : current
                    ? "text-violet-700"
                    : "text-slate-500"
                }`}
              >
                <span
                  className={`inline-flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold border ${
                    active
                      ? "bg-emerald-100 border-emerald-300"
                      : current
                      ? "bg-violet-100 border-violet-300"
                      : "bg-slate-100 border-slate-300"
                  }`}
                >
                  {i + 1}
                </span>
                <span className="text-sm font-semibold">{s.label}</span>
              </div>
              {i < steps.length - 1 && (
                <div className="flex-1 h-px bg-slate-200 mx-2" />
              )}
            </li>
          );
        })}
      </ol>

      {/* Message */}
      <div>
        <h2 className="text-lg font-semibold">Progress</h2>
        <p className="text-slate-700">{message}</p>
      </div>

      {/* Bar */}
      <div className="progress-track">
        <span
          className="progress-value"
          style={{ width: `${Math.min(Math.max(progress, 0), 100)}%` }}
        />
      </div>
      <div className="inline-flex items-center gap-1 text-sm bg-sky-100 text-sky-700 px-2 py-1 rounded-full">
        <span>{progress}%</span>
        <span>·</span>
        <span>{isStreaming ? "Streaming" : "Idle"}</span>
        {streamMode && streamMode !== "values" && <span>({streamMode})</span>}
      </div>
    </div>
  );
}
