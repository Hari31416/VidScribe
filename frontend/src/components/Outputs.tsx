import { getFileDownloadUrl } from "../api/runGraph";
import type { StateSnapshot } from "../types";

interface Props {
  state?: StateSnapshot;
  includeFields?: string[];
  showPdfButtons?: boolean;
  defaultOpen?: boolean;
}

function joinLines(lines?: string[]): string {
  if (!lines || lines.length === 0) return "";
  return lines.join("\n\n");
}

export function Outputs({
  state,
  includeFields = [],
  showPdfButtons = true,
  defaultOpen = false,
}: Props) {
  if (!state) {
    return <small className="muted">No output yet.</small>;
  }

  const collectedPdf = {
    label: "Download Collected Notes PDF",
    path: state.collected_notes_pdf_path,
  };
  const summaryPdf = {
    label: "Download Summary PDF",
    path: state.summary_pdf_path,
  };

  return (
    <div className="grid-2 min-w-0">
      {/* PDF download buttons */}
      {showPdfButtons && (
        <div className="actions" style={{ gridColumn: "1 / -1" }}>
          <button
            className="secondary"
            type="button"
            disabled={!collectedPdf.path}
            onClick={() => {
              if (collectedPdf.path) {
                window.open(getFileDownloadUrl(collectedPdf.path), "_blank");
              }
            }}
          >
            {collectedPdf.label}
          </button>
          <button
            className="secondary"
            type="button"
            disabled={!summaryPdf.path}
            onClick={() => {
              if (summaryPdf.path) {
                window.open(getFileDownloadUrl(summaryPdf.path), "_blank");
              }
            }}
          >
            {summaryPdf.label}
          </button>
        </div>
      )}

      {/* Dynamically render only the selected fields */}
      {includeFields.includes("formatted_notes") && (
        <details className="min-w-0" {...(defaultOpen ? { open: true } : {})}>
          <summary className="text-sm">Formatted notes</summary>
          <textarea
            className="input text-sm min-h-[200px] resize-y max-w-full overflow-x-auto whitespace-pre-wrap break-words"
            readOnly
            value={joinLines(state.formatted_notes)}
          />
        </details>
      )}

      {includeFields.includes("summary") && (
        <details className="min-w-0" {...(defaultOpen ? { open: true } : {})}>
          <summary className="text-sm">Summary</summary>
          <textarea
            className="input text-sm min-h-[160px] resize-y max-w-full overflow-x-auto whitespace-pre-wrap break-words"
            readOnly
            value={state.summary ?? ""}
          />
        </details>
      )}

      {includeFields.includes("chunk_notes") && (
        <details className="min-w-0" {...(defaultOpen ? { open: true } : {})}>
          <summary className="text-sm">Chunk notes</summary>
          <textarea
            className="input text-sm min-h-[160px] resize-y max-w-full overflow-x-auto whitespace-pre-wrap break-words"
            readOnly
            value={joinLines(state.chunk_notes)}
          />
        </details>
      )}

      {includeFields.includes("image_integrated_notes") && (
        <details className="min-w-0" {...(defaultOpen ? { open: true } : {})}>
          <summary className="text-sm">Image integrated notes</summary>
          <textarea
            className="input text-sm min-h-[160px] resize-y max-w-full overflow-x-auto whitespace-pre-wrap break-words"
            readOnly
            value={joinLines(state.image_integrated_notes)}
          />
        </details>
      )}

      {includeFields.includes("chunks") && (
        <details className="min-w-0" {...(defaultOpen ? { open: true } : {})}>
          <summary className="text-sm">Chunks</summary>
          <textarea
            className="input text-sm min-h-[160px] resize-y max-w-full overflow-x-auto whitespace-pre-wrap break-words"
            readOnly
            value={joinLines(state.chunks)}
          />
        </details>
      )}

      {includeFields.includes("collected_notes") && (
        <details className="min-w-0" {...(defaultOpen ? { open: true } : {})}>
          <summary className="text-sm">Collected notes (final)</summary>
          <textarea
            className="input text-sm min-h-[160px] resize-y max-w-full overflow-x-auto whitespace-pre-wrap break-words"
            readOnly
            value={state.collected_notes ?? ""}
          />
        </details>
      )}

      {includeFields.includes("timestamps_output") && (
        <details {...(defaultOpen ? { open: true } : {})}>
          <summary className="text-sm">Timestamps output</summary>
          <pre className="bg-slate-900 text-slate-100 p-2 rounded-lg text-xs overflow-x-auto overflow-y-auto max-w-full">
            {JSON.stringify(state.timestamps_output ?? [], null, 2)}
          </pre>
        </details>
      )}

      {includeFields.includes("image_insertions_output") && (
        <details {...(defaultOpen ? { open: true } : {})}>
          <summary className="text-sm">Image insertions</summary>
          <pre className="bg-slate-900 text-slate-100 p-2 rounded-lg text-xs overflow-x-auto overflow-y-auto max-w-full">
            {JSON.stringify(state.image_insertions_output ?? [], null, 2)}
          </pre>
        </details>
      )}

      {includeFields.includes("extracted_images_output") && (
        <details {...(defaultOpen ? { open: true } : {})}>
          <summary className="text-sm">Extracted images</summary>
          <pre className="bg-slate-900 text-slate-100 p-2 rounded-lg text-xs overflow-x-auto overflow-y-auto max-w-full">
            {JSON.stringify(state.extracted_images_output ?? [], null, 2)}
          </pre>
        </details>
      )}

      {includeFields.includes("integrates") && (
        <details {...(defaultOpen ? { open: true } : {})}>
          <summary className="text-sm">Integrations</summary>
          <pre className="bg-slate-900 text-slate-100 p-2 rounded-lg text-xs overflow-x-auto overflow-y-auto max-w-full">
            {JSON.stringify(state.integrates ?? [], null, 2)}
          </pre>
        </details>
      )}
    </div>
  );
}
