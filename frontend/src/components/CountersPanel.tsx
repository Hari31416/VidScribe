import type { Counters } from "../types";

interface Props {
  counters?: Counters;
}

function percent(current: number, total: number): string {
  if (!total) return "0%";
  return `${Math.round((current / total) * 100)}%`;
}

function formatCount(current: number, total: number): string {
  return `${current}/${total}`;
}

export function CountersPanel({ counters }: Props) {
  if (!counters) {
    return <small className="muted">No counters yet.</small>;
  }

  return (
    <div className="grid-2">
      <section>
        <h3>Notes Progress</h3>
        <div className="table-scroll">
          <table>
            <tbody>
              <tr>
                <th scope="row">Raw notes</th>
                <td>
                  {formatCount(
                    counters.notes_created.current,
                    counters.notes_created.total
                  )}
                </td>
                <td>
                  {percent(
                    counters.notes_created.current,
                    counters.notes_created.total
                  )}
                </td>
              </tr>
              <tr>
                <th scope="row">Integrated notes</th>
                <td>
                  {formatCount(
                    counters.integrated_image_notes_created.current,
                    counters.integrated_image_notes_created.total
                  )}
                </td>
                <td>
                  {percent(
                    counters.integrated_image_notes_created.current,
                    counters.integrated_image_notes_created.total
                  )}
                </td>
              </tr>
              <tr>
                <th scope="row">Formatted notes</th>
                <td>
                  {formatCount(
                    counters.formatted_notes_created.current,
                    counters.formatted_notes_created.total
                  )}
                </td>
                <td>
                  {percent(
                    counters.formatted_notes_created.current,
                    counters.formatted_notes_created.total
                  )}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section>
        <h3>Media & timestamps</h3>
        <div className="table-scroll">
          <table>
            <tbody>
              <tr>
                <th scope="row">Timestamps</th>
                <td>{counters.timestamps_created.current_items}</td>
                <td>
                  {formatCount(
                    counters.timestamps_created.chunks_completed,
                    counters.timestamps_created.total_chunks
                  )}{" "}
                  (
                  {percent(
                    counters.timestamps_created.chunks_completed,
                    counters.timestamps_created.total_chunks
                  )}
                  )
                </td>
              </tr>
              <tr>
                <th scope="row">Image insertions</th>
                <td>{counters.image_insertions_created.current_items}</td>
                <td>
                  {formatCount(
                    counters.image_insertions_created.chunks_completed,
                    counters.image_insertions_created.total_chunks
                  )}{" "}
                  (
                  {percent(
                    counters.image_insertions_created.chunks_completed,
                    counters.image_insertions_created.total_chunks
                  )}
                  )
                </td>
              </tr>
              <tr>
                <th scope="row">Extracted images</th>
                <td>{counters.extracted_images_created.current_items}</td>
                <td>
                  {formatCount(
                    counters.extracted_images_created.chunks_completed,
                    counters.extracted_images_created.total_chunks
                  )}{" "}
                  (
                  {percent(
                    counters.extracted_images_created.chunks_completed,
                    counters.extracted_images_created.total_chunks
                  )}
                  )
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section>
        <h3>Finalization</h3>
        <div className="status-list">
          <div
            className={`status-pill ${
              counters.finalization.collected ? "on" : "off"
            }`}
          >
            <span>Collected notes</span>
          </div>
          <div
            className={`status-pill ${
              counters.finalization.summary ? "on" : "off"
            }`}
          >
            <span>Summary</span>
          </div>
          <div
            className={`status-pill ${
              counters.finalization.collected_notes_pdf ? "on" : "off"
            }`}
          >
            <span>Collected notes PDF</span>
          </div>
          <div
            className={`status-pill ${
              counters.finalization.summary_pdf ? "on" : "off"
            }`}
          >
            <span>Summary PDF</span>
          </div>
        </div>
      </section>

      <section>
        <h3>Distribution</h3>
        <pre>{JSON.stringify(counters.notes_by_type, null, 2)}</pre>
      </section>
    </div>
  );
}
