interface EventItem {
  id: string;
  phase: string;
  progress: number;
  message: string;
  timestamp?: string;
}

export function EventLog({ events }: { events: EventItem[] }) {
  if (events.length === 0)
    return <small className="muted">No events yet.</small>;

  return (
    <ul className="space-y-1 max-h-[420px] overflow-auto pr-2">
      {events.map((evt) => {
        const tone =
          evt.phase === "error"
            ? "text-red-600"
            : evt.phase === "done"
            ? "text-emerald-600"
            : /warn|slow/i.test(evt.message)
            ? "text-amber-600"
            : "text-slate-700";
        const ts = (() => {
          try {
            const d = new Date((evt as any).timestamp as string);
            if (Number.isNaN(d.getTime())) return null;
            return d.toLocaleTimeString(undefined, { hour12: false });
          } catch {
            return null;
          }
        })();
        return (
          <li key={evt.id} className={`text-sm ${tone}`}>
            {ts && <span className="opacity-60 mr-1">[{ts}]</span>}
            <span className="font-semibold">[{evt.phase}]</span>{" "}
            <span className="opacity-70">{evt.progress}%</span> – {evt.message}
          </li>
        );
      })}
    </ul>
  );
}
