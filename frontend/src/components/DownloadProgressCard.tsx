import { getFileDownloadUrl } from "../api/runGraph";

interface Props {
  progress: { percent: number; message: string; status?: string };
  filePath?: string | null;
}

export function DownloadProgressCard({ progress, filePath }: Props) {
  const pct = Math.max(0, Math.min(100, Math.round(progress.percent)));
  const status = progress.status ?? "downloading";
  const canDownload =
    !!filePath && (status === "success" || status === "skipped");
  const href = canDownload ? getFileDownloadUrl(filePath!) : undefined;
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Video Download</h2>
        <span
          className={`text-xs px-2 py-1 rounded-full border ${
            status === "success"
              ? "bg-emerald-50 text-emerald-700 border-emerald-200"
              : status === "error"
              ? "bg-red-50 text-red-700 border-red-200"
              : status === "skipped"
              ? "bg-blue-50 text-blue-700 border-blue-200"
              : "bg-violet-50 text-violet-700 border-violet-200"
          }`}
        >
          {status}
        </span>
      </div>
      <p className="text-slate-700">{progress.message}</p>
      <div className="flex items-center gap-3">
        <div className="flex-1 progress-track h-2 rounded-full bg-gray-200 overflow-hidden">
          <span
            className="progress-value block h-full bg-gradient-to-tr from-violet-400 to-violet-600 transition-[width]"
            style={{ width: `${pct}%` }}
          />
        </div>
        {canDownload && href && (
          <a
            className="btn btn-secondary text-sm"
            href={href}
            target="_blank"
            rel="noreferrer"
          >
            Download video
          </a>
        )}
      </div>
    </div>
  );
}
