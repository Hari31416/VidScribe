import { useState } from "react";
import type { StateSnapshot } from "../types";
import { getFileDownloadUrl } from "../api/runGraph";

interface Props {
  snapshot?: StateSnapshot;
  events: {
    id: string;
    phase: string;
    progress: number;
    message: string;
    timestamp?: string;
  }[];
}

export function DetailedResults({ snapshot, events }: Props) {
  const [activeTab, setActiveTab] = useState<"notes" | "media" | "summary">(
    "notes"
  );

  return (
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
            activeTab === "summary"
              ? "border-violet-600 text-violet-700"
              : "border-transparent text-slate-500"
          }`}
          onClick={() => setActiveTab("summary")}
        >
          Summary
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
              {JSON.stringify(snapshot?.image_insertions_output ?? [], null, 2)}
            </pre>
          </div>
          <div>
            <div className="label mb-1">Extracted Images</div>
            <pre className="bg-slate-900 text-slate-100 p-3 rounded-xl overflow-auto text-sm">
              {JSON.stringify(snapshot?.extracted_images_output ?? [], null, 2)}
            </pre>
          </div>
        </div>
      )}

      {activeTab === "summary" && (
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
            className="input min-h-[320px]"
            readOnly
            value={snapshot?.summary || ""}
            placeholder="No summary yet."
          />
        </div>
      )}
    </section>
  );
}
