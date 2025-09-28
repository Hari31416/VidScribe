import { useRef } from "react";
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
  // Prefer backend progress, but also derive a smooth fallback from counters/steps
  const reported = Number.isFinite(Number(latest?.progress))
    ? Number(latest?.progress)
    : 0;
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
    // Media in progress
    if (
      counters.extracted_images_created.current_items > 0 ||
      counters.timestamps_created.current_items > 0
    )
      return 2;
    // Notes in progress
    if (counters.notes_created.current > 0) return 1;
    return 0;
  })();

  const derivedFromCounters = (() => {
    if (!counters) return 0;
    const stepsCount = steps.length; // 5
    const segment = 100 / stepsCount; // 20
    const idx = Math.max(0, Math.min(stepIndex, stepsCount));

    // If finalize indicated done
    if (idx >= stepsCount) return 100;

    // Sub-progress within current segment (0..1)
    let sub = 0;
    // Map current phase heuristics: prefer formatting, then media, then notes
    if (idx >= 3 && counters.formatted_notes_created.total > 0) {
      // Formatting phase
      sub =
        counters.formatted_notes_created.current /
        Math.max(1, counters.formatted_notes_created.total);
    } else if (idx >= 2) {
      // Media phase: average across trackers with totals
      const fracs: number[] = [];
      if (counters.timestamps_created.total_chunks > 0) {
        fracs.push(
          counters.timestamps_created.chunks_completed /
            Math.max(1, counters.timestamps_created.total_chunks)
        );
      }
      if (counters.image_insertions_created.total_chunks > 0) {
        fracs.push(
          counters.image_insertions_created.chunks_completed /
            Math.max(1, counters.image_insertions_created.total_chunks)
        );
      }
      if (counters.extracted_images_created.total_chunks > 0) {
        fracs.push(
          counters.extracted_images_created.chunks_completed /
            Math.max(1, counters.extracted_images_created.total_chunks)
        );
      }
      if (fracs.length > 0)
        sub = fracs.reduce((a, b) => a + b, 0) / fracs.length;
    } else if (idx >= 1 && counters.notes_created.total >= 0) {
      // Notes phase: if total unknown (0), still advance using current
      const total = Math.max(1, counters.notes_created.total);
      sub = counters.notes_created.current / total;
    }

    sub = Math.max(0, Math.min(sub, 1));
    const baseStart = idx * segment;
    const derived = baseStart + sub * segment;
    return Math.round(Math.max(0, Math.min(100, derived)));
  })();

  // Choose the best progress and ensure monotonic increase per render
  const lastRef = useRef(0);
  const effective = Math.max(reported, derivedFromCounters);
  const progress = Math.max(
    lastRef.current,
    Math.min(Math.max(effective, 0), 100)
  );
  if (progress > lastRef.current) lastRef.current = progress;
  const displayProgress = Math.round(progress);

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
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">
            Progress ({displayProgress}%)
          </h2>
        </div>
        <p className="text-slate-700">{message}</p>
      </div>

      {/* Bar */}
      <div className="progress-track h-3 rounded-full bg-gray-200 overflow-hidden">
        <span
          className="progress-value block h-full bg-gradient-to-tr from-emerald-400 to-emerald-600 transition-[width]"
          style={{ width: `${Math.min(Math.max(progress, 0), 100)}%` }}
        />
      </div>
      {/* Removed the percentage/status chip to avoid '80% Streaming' display */}
    </div>
  );
}
