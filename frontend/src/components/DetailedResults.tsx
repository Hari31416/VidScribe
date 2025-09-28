import { useState } from "react";
import type { StateSnapshot } from "../types";
import { getFileDownloadUrl } from "../api/runGraph";
import { EventLog } from "./EventLog";
import { Outputs } from "./Outputs";
import { STREAM_FIELDS } from "../constants";

interface Props {
  snapshot?: StateSnapshot;
  includeFields?: string[];
  compactMode?: boolean;
  events: {
    id: string;
    phase: string;
    progress: number;
    message: string;
    timestamp?: string;
  }[];
}

export function DetailedResults({
  snapshot,
  includeFields = [],
  compactMode = true,
  events,
}: Props) {
  const [activeTab, setActiveTab] = useState<"content" | "selected" | "logs">(
    "content"
  );

  return (
    <section className="card h-fit min-w-0 overflow-x-hidden">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-semibold">Detailed Results</h2>
      </div>
      <div className="flex border-b border-slate-200 mb-4">
        <button
          className={`px-3 py-2 text-sm font-semibold border-b-2 -mb-px ${
            activeTab === "content"
              ? "border-violet-600 text-violet-700"
              : "border-transparent text-slate-500"
          }`}
          onClick={() => setActiveTab("content")}
        >
          Notes & Summary
        </button>
        <button
          className={`px-3 py-2 text-sm font-semibold border-b-2 -mb-px ${
            activeTab === "selected"
              ? "border-violet-600 text-violet-700"
              : "border-transparent text-slate-500"
          }`}
          onClick={() => setActiveTab("selected")}
        >
          Selected Fields
        </button>
        <button
          className={`px-3 py-2 text-sm font-semibold border-b-2 -mb-px ${
            activeTab === "logs"
              ? "border-violet-600 text-violet-700"
              : "border-transparent text-slate-500"
          }`}
          onClick={() => setActiveTab("logs")}
        >
          Logs
        </button>
      </div>

      {activeTab === "content" && (
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

          <label className="label">Summary</label>
          <textarea
            className="input min-h-[180px] resize-y max-w-full overflow-x-auto"
            readOnly
            value={snapshot?.summary || ""}
            placeholder="No summary yet."
          />

          <label className="label">Formatted Notes</label>
          <textarea
            className="input min-h-[320px] resize-y max-w-full overflow-x-auto"
            readOnly
            value={(snapshot?.formatted_notes || []).join("\n\n")}
            placeholder="No formatted notes yet."
          />
        </div>
      )}

      {activeTab === "logs" && (
        <div className="space-y-2 min-w-0">
          <EventLog events={events} />
        </div>
      )}

      {activeTab === "selected" &&
        (() => {
          const hidden = new Set([
            "summary",
            "collected_notes_pdf_path",
            "summary_pdf_path",
          ]);
          const computed = (
            compactMode ? includeFields : Array.from(STREAM_FIELDS)
          ).filter((f) => !hidden.has(f));

          return (
            <div className="space-y-2 min-w-0">
              {computed.length === 0 ? (
                <small className="muted">
                  No selected fields to display. Adjust Advanced settings to
                  pick more fields.
                </small>
              ) : (
                <Outputs
                  state={snapshot}
                  includeFields={computed}
                  showPdfButtons={false}
                  defaultOpen
                />
              )}
            </div>
          );
        })()}
    </section>
  );
}
