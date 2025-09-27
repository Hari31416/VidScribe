import { getFileDownloadUrl } from "../api/runGraph";
import type { StateSnapshot } from "../types";

interface Props {
  state?: StateSnapshot;
  includeFields?: string[];
}

function joinLines(lines?: string[]): string {
  if (!lines || lines.length === 0) return "";
  return lines.join("\n\n");
}

export function Outputs({ state, includeFields = [] }: Props) {
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
    <div className="grid-2">
      {/* PDF download buttons */}
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

      {/* Dynamically render only the selected fields */}
      {includeFields.includes("formatted_notes") && (
        <details open>
          <summary>Formatted notes</summary>
          <textarea readOnly value={joinLines(state.formatted_notes)} />
        </details>
      )}

      {includeFields.includes("summary") && (
        <details>
          <summary>Summary</summary>
          <textarea readOnly value={state.summary ?? ""} />
        </details>
      )}

      {includeFields.includes("chunk_notes") && (
        <details>
          <summary>Chunk notes</summary>
          <textarea readOnly value={joinLines(state.chunk_notes)} />
        </details>
      )}

      {includeFields.includes("image_integrated_notes") && (
        <details>
          <summary>Image integrated notes</summary>
          <textarea readOnly value={joinLines(state.image_integrated_notes)} />
        </details>
      )}

      {includeFields.includes("chunks") && (
        <details>
          <summary>Chunks</summary>
          <textarea readOnly value={joinLines(state.chunks)} />
        </details>
      )}

      {includeFields.includes("collected_notes") && (
        <details>
          <summary>Collected notes (final)</summary>
          <textarea readOnly value={state.collected_notes ?? ""} />
        </details>
      )}

      {includeFields.includes("timestamps_output") && (
        <details>
          <summary>Timestamps output</summary>
          <pre>{JSON.stringify(state.timestamps_output ?? [], null, 2)}</pre>
        </details>
      )}

      {includeFields.includes("image_insertions_output") && (
        <details>
          <summary>Image insertions</summary>
          <pre>
            {JSON.stringify(state.image_insertions_output ?? [], null, 2)}
          </pre>
        </details>
      )}

      {includeFields.includes("extracted_images_output") && (
        <details>
          <summary>Extracted images</summary>
          <pre>
            {JSON.stringify(state.extracted_images_output ?? [], null, 2)}
          </pre>
        </details>
      )}

      {includeFields.includes("integrates") && (
        <details>
          <summary>Integrations</summary>
          <pre>{JSON.stringify(state.integrates ?? [], null, 2)}</pre>
        </details>
      )}
    </div>
  );
}
