import { CountersPanel } from "./CountersPanel";
import { ProgressCard } from "./ProgressCard";
import { DownloadProgressCard } from "./DownloadProgressCard";
import type { Counters, ProgressEventPayload, StateSnapshot } from "../types";

interface Props {
  latest?: ProgressEventPayload;
  streamMode?: string;
  isStreaming: boolean;
  counters?: Counters;
  snapshot?: StateSnapshot;
  error?: string | null;
  downloadProgress?: {
    percent: number;
    message: string;
    status?: string;
  } | null;
  downloadFilePath?: string | null;
  runId?: number;
}

export function MonitoringPanel({
  latest,
  streamMode,
  isStreaming,
  counters,
  snapshot,
  error,
  downloadProgress,
  downloadFilePath,
  runId,
}: Props) {
  return (
    <div className="space-y-6">
      {/* Download progress bar (separate from pipeline) */}
      {downloadProgress && (
        <section className="card">
          <DownloadProgressCard
            progress={downloadProgress}
            filePath={downloadFilePath}
          />
        </section>
      )}
      <section className="card">
        <ProgressCard
          key={runId}
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
      {error && (
        <section className="card border border-red-200">
          <h2 className="text-lg font-semibold text-red-700">Errors</h2>
          <p className="text-red-600">{error}</p>
        </section>
      )}
    </div>
  );
}
