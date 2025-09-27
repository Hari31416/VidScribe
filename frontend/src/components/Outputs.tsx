import { getFileDownloadUrl } from "../api/runGraph";
import type { StateSnapshot } from "../types";

interface Props {
  state?: StateSnapshot;
}

function joinLines(lines?: string[]): string {
  if (!lines || lines.length === 0) return "";
  return lines.join("\n\n");
}

export function Outputs({ state }: Props) {
  if (!state) {
    return <small className="muted">No output yet.</small>;
  }

  const pdfArtifacts: Array<{
    label: string;
    path?: string;
  }> = [
    { label: "Collected notes", path: state.collected_notes_pdf_path },
    { label: "Summary", path: state.summary_pdf_path },
  ];

  return (
    <div className="grid-2">
      <details open>
        <summary>Formatted notes</summary>
        <textarea readOnly value={joinLines(state.formatted_notes)} />
      </details>

      <details>
        <summary>Summary</summary>
        <textarea readOnly value={state.summary ?? ""} />
      </details>

      <details>
        <summary>Chunk notes</summary>
        <textarea readOnly value={joinLines(state.chunk_notes)} />
      </details>

      <details>
        <summary>Image integrated notes</summary>
        <textarea readOnly value={joinLines(state.image_integrated_notes)} />
      </details>

      <details>
        <summary>Chunks</summary>
        <textarea readOnly value={joinLines(state.chunks)} />
      </details>

      <details>
        <summary>Collected notes (final)</summary>
        <textarea readOnly value={state.collected_notes ?? ""} />
      </details>

      <details>
        <summary>Timestamps output</summary>
        <pre>{JSON.stringify(state.timestamps_output ?? [], null, 2)}</pre>
      </details>

      <details>
        <summary>Image insertions</summary>
        <pre>
          {JSON.stringify(state.image_insertions_output ?? [], null, 2)}
        </pre>
      </details>

      <details>
        <summary>Extracted images</summary>
        <pre>
          {JSON.stringify(state.extracted_images_output ?? [], null, 2)}
        </pre>
      </details>

      <details>
        <summary>PDF artifacts</summary>
        <ul>
          {pdfArtifacts.map(({ label, path }) => (
            <li key={label}>
              <strong>{label} PDF:</strong>{" "}
              {path ? (
                <span>
                  <a
                    href={getFileDownloadUrl(path)}
                    target="_blank"
                    rel="noopener noreferrer"
                    download
                  >
                    Download
                  </a>
                  {" · "}
                  <code>{path}</code>
                </span>
              ) : (
                <span>—</span>
              )}
            </li>
          ))}
        </ul>
        <small className="muted">
          Click a download link to retrieve the generated PDF directly from the
          backend.
        </small>
      </details>
    </div>
  );
}
