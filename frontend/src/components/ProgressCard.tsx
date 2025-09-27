import type { ProgressEventPayload } from "../types";

interface Props {
  latest?: ProgressEventPayload;
  streamMode?: string;
  isStreaming: boolean;
}

export function ProgressCard({ latest, streamMode, isStreaming }: Props) {
  const progress = latest?.progress ?? 0;
  const message = latest?.message ?? "Waiting for updates…";
  const phase = latest?.phase ?? "initializing";

  return (
    <div className="progress-card">
      <div>
        <h2>Progress</h2>
        <p>{message}</p>
        <small className="muted">Phase: {phase}</small>
      </div>
      <div className="progress-bar">
        <span style={{ width: `${Math.min(Math.max(progress, 0), 100)}%` }} />
      </div>
      <div className="badge">
        <span>{progress}%</span>
        <span>·</span>
        <span>{isStreaming ? "Streaming" : "Idle"}</span>
        {streamMode && streamMode !== "values" && <span>({streamMode})</span>}
      </div>
    </div>
  );
}
