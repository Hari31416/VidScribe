import { CountersPanel } from "./CountersPanel";
import { ProgressCard } from "./ProgressCard";
import type { Counters, ProgressEventPayload, StateSnapshot } from "../types";

interface Props {
  latest?: ProgressEventPayload;
  streamMode?: string;
  isStreaming: boolean;
  counters?: Counters;
  snapshot?: StateSnapshot;
  error?: string | null;
}

export function MonitoringPanel({
  latest,
  streamMode,
  isStreaming,
  counters,
  snapshot,
  error,
}: Props) {
  return (
    <div className="space-y-6">
      <section className="card">
        <ProgressCard
          latest={latest}
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
  );
}
