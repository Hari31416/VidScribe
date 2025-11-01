import type { Counters } from "../types";

interface Props {
  counters?: Counters;
}

function percent(current: number, total: number): string {
  if (!total) return "0%";
  current = Math.min(current, total);
  return `${Math.round((current / total) * 100)}%`;
}

function formatCount(current: number, total: number): string {
  current = Math.min(current, total);
  return `${current}/${total}`;
}

export function CountersPanel({ counters }: Props) {
  if (!counters) {
    return <small className="muted">No counters yet.</small>;
  }

  return (
    <div className="grid gap-4 md:grid-cols-2">
      {/* Notes progress */}
      <div className="grid gap-3">
        <div className="grid grid-cols-3 gap-3">
          <StatCard
            title="Raw notes"
            value={formatCount(
              counters.notes_created.current,
              counters.notes_created.total
            )}
            sub={percent(
              counters.notes_created.current,
              counters.notes_created.total
            )}
          />
          <StatCard
            title="Integrated"
            value={formatCount(
              counters.integrated_image_notes_created.current,
              counters.integrated_image_notes_created.total
            )}
            sub={percent(
              counters.integrated_image_notes_created.current,
              counters.integrated_image_notes_created.total
            )}
          />
          <StatCard
            title="Formatted"
            value={formatCount(
              counters.formatted_notes_created.current,
              counters.formatted_notes_created.total
            )}
            sub={percent(
              counters.formatted_notes_created.current,
              counters.formatted_notes_created.total
            )}
          />
        </div>
      </div>

      {/* Media & timestamps */}
      <div className="grid gap-3">
        <div className="grid grid-cols-3 gap-3">
          <StatCard
            title="Timestamps"
            value={`${counters.timestamps_created.current_items}`}
            sub={`${formatCount(
              counters.timestamps_created.chunks_completed,
              counters.timestamps_created.total_chunks
            )} (${percent(
              counters.timestamps_created.chunks_completed,
              counters.timestamps_created.total_chunks
            )})`}
          />
          <StatCard
            title="Image inserts"
            value={`${counters.image_insertions_created.current_items}`}
            sub={`${formatCount(
              counters.image_insertions_created.chunks_completed,
              counters.image_insertions_created.total_chunks
            )} (${percent(
              counters.image_insertions_created.chunks_completed,
              counters.image_insertions_created.total_chunks
            )})`}
          />
          <StatCard
            title="Extracted imgs"
            value={`${counters.extracted_images_created.current_items}`}
            sub={`${formatCount(
              counters.extracted_images_created.chunks_completed,
              counters.extracted_images_created.total_chunks
            )} (${percent(
              counters.extracted_images_created.chunks_completed,
              counters.extracted_images_created.total_chunks
            )})`}
          />
        </div>
      </div>

      {/* Finalization toggles */}
      <div className="md:col-span-2 grid grid-cols-2 md:grid-cols-4 gap-3">
        <Pill label="Collected notes" on={counters.finalization.collected} />
        <Pill label="Summary" on={counters.finalization.summary} />
        <Pill
          label="Notes PDF"
          on={counters.finalization.collected_notes_pdf}
        />
        <Pill label="Summary PDF" on={counters.finalization.summary_pdf} />
      </div>

      {/* Distribution */}
      <div className="md:col-span-2 grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        <Pill label={`Raw: ${counters.notes_by_type.raw}`} on />
        <Pill label={`Integrated: ${counters.notes_by_type.integrated}`} on />
        <Pill label={`Formatted: ${counters.notes_by_type.formatted}`} on />
        <Pill label={`Collected: ${counters.notes_by_type.collected}`} on />
        <Pill label={`Summary: ${counters.notes_by_type.summary}`} on />
        <Pill label={`PDFs: ${counters.notes_by_type.exported_pdfs}`} on />
      </div>
    </div>
  );
}

function StatCard({
  title,
  value,
  sub,
}: {
  title: string;
  value: string;
  sub?: string;
}) {
  return (
    <div className="rounded-2xl border border-slate-200 p-4 bg-white">
      <div className="text-sm text-slate-500 font-medium">{title}</div>
      <div className="text-2xl font-extrabold">{value}</div>
      {sub && <div className="text-xs text-slate-500 mt-1">{sub}</div>}
    </div>
  );
}

function Pill({ label, on }: { label: string; on?: boolean }) {
  return (
    <div
      className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-medium ${
        on ? "bg-emerald-100 text-emerald-700" : "bg-rose-100 text-rose-700"
      }`}
    >
      {label}
    </div>
  );
}
