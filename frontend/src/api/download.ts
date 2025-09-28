const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export interface DownloadRequestBody {
  video_id: string;
  resolution?: number;
  audio_only?: boolean;
  video_only?: boolean;
  audio_format?: string;
  overwrite?: boolean;
}

export interface RawDownloadProgressEvent {
  status: string; // started | downloading | finished | success | skipped | error
  video_id?: string;
  filename?: string;
  downloaded_bytes?: number;
  total_bytes?: number;
  speed?: number;
  elapsed?: number;
  eta?: number;
  fragment_index?: number;
  fragment_count?: number;
  result?: {
    status?: string;
    output_dir?: string;
    downloaded_files?: string[];
  };
  error?: string;
}

export interface DownloadUiProgress {
  status: string; // started | downloading | finished | success | skipped | error
  percent: number; // 0..100
  message: string; // human readable
  downloadedBytes?: number;
  totalBytes?: number;
  speedBps?: number;
  etaSec?: number;
}

const decoder = new TextDecoder("utf-8");

function parseSSEChunk(chunk: string): RawDownloadProgressEvent | null {
  const lines = chunk.split(/\n/).filter(Boolean);
  let eventType: string | null = null;
  let dataPayload = "";
  for (const line of lines) {
    if (line.startsWith(":")) continue;
    if (line.startsWith("event:")) {
      eventType = line.slice("event:".length).trim();
    } else if (line.startsWith("data:")) {
      dataPayload += line.slice("data:".length).trim();
    }
  }
  if (eventType && eventType !== "progress") return null;
  if (!dataPayload) return null;
  try {
    return JSON.parse(dataPayload) as RawDownloadProgressEvent;
  } catch {
    return null;
  }
}

export async function streamDownload(
  body: DownloadRequestBody,
  onProgress: (ui: DownloadUiProgress) => void
): Promise<{ abort: () => void; done: Promise<string> }> {
  const controller = new AbortController();
  let resolveDone: (path: string) => void;
  let rejectDone: (err: unknown) => void;
  const done = new Promise<string>((resolve, reject) => {
    resolveDone = resolve;
    rejectDone = reject;
  });

  (async () => {
    try {
      const resp = await fetch(`${API_BASE_URL}/videos/download/stream`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "text/event-stream",
        },
        body: JSON.stringify(body),
        signal: controller.signal,
      });
      if (!resp.ok || !resp.body) {
        const t = await resp.text();
        throw new Error(`Download stream failed ${resp.status}: ${t}`);
      }
      // map download events to friendly UI progress
      const reader = resp.body.getReader();
      let buffer = "";
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        let idx = buffer.indexOf("\n\n");
        while (idx !== -1) {
          const raw = buffer.slice(0, idx);
          buffer = buffer.slice(idx + 2);
          const parsed = parseSSEChunk(raw);
          if (parsed) {
            const phase = parsed.status;
            const downloaded = parsed.downloaded_bytes ?? 0;
            const total = parsed.total_bytes ?? 0;
            const percent =
              phase === "downloading" && total > 0
                ? Math.max(
                    0,
                    Math.min(100, Math.round((downloaded / total) * 100))
                  )
                : phase === "success" || phase === "skipped"
                ? 100
                : phase === "started"
                ? 0
                : 0;
            const speed = parsed.speed ?? 0;
            const eta = parsed.eta ?? undefined;
            const msg = buildMessage(phase, downloaded, total, speed, eta);
            onProgress({
              status: phase,
              percent,
              message: msg,
              downloadedBytes: downloaded,
              totalBytes: total,
              speedBps: speed,
              etaSec: eta,
            });
            if (
              parsed.result &&
              (parsed.result.status === "success" ||
                parsed.result.status === "skipped")
            ) {
              const files = parsed.result.downloaded_files || [];
              const chosen = chooseBestFile(files);
              if (chosen) {
                resolveDone(chosen);
              } else if (parsed.result.output_dir) {
                // last resort; cannot resolve file
                resolveDone(parsed.result.output_dir);
              }
            }
            if (phase === "error" && parsed.error) {
              rejectDone(new Error(parsed.error));
            }
          }
          idx = buffer.indexOf("\n\n");
        }
      }
    } catch (err) {
      if ((err as DOMException)?.name === "AbortError") return;
      rejectDone(err);
    }
  })();

  return { abort: () => controller.abort(), done };
}

export async function downloadOnce(body: DownloadRequestBody) {
  const resp = await fetch(`${API_BASE_URL}/videos/download`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!resp.ok) {
    const t = await resp.text();
    throw new Error(`Download failed ${resp.status}: ${t}`);
  }
  const json = (await resp.json()) as {
    status: string;
    files?: { absolute_path?: string }[];
  };
  const list = (json.files || [])
    .map((f) => f.absolute_path)
    .filter(Boolean) as string[];
  const chosen = chooseBestFile(list);
  if (!chosen) throw new Error("No file produced by download");
  return chosen;
}

// helpers
function formatBytes(n?: number) {
  if (!n || n <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"] as const;
  const i = Math.min(
    units.length - 1,
    Math.floor(Math.log(n) / Math.log(1024))
  );
  const val = n / Math.pow(1024, i);
  return `${val.toFixed(val >= 100 ? 0 : val >= 10 ? 1 : 2)} ${units[i]}`;
}

function formatEta(seconds?: number) {
  if (!seconds || seconds <= 0) return "";
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60)
    .toString()
    .padStart(2, "0");
  return `${m}:${s}`;
}

function buildMessage(
  phase: string,
  downloaded: number,
  total: number,
  speedBps: number,
  etaSec?: number
) {
  if (phase === "started") return "Preparing download…";
  if (phase === "downloading") {
    const speed = speedBps > 0 ? `${formatBytes(speedBps)}/s` : "";
    const eta = etaSec ? `, ETA ${formatEta(etaSec)}` : "";
    const totalStr = total > 0 ? formatBytes(total) : "?";
    return `Downloading… ${formatBytes(
      downloaded
    )} / ${totalStr} ${speed}${eta}`.trim();
  }
  if (phase === "finished") return "Merging and finalizing…";
  if (phase === "success") return "Download complete";
  if (phase === "skipped") return "Already downloaded (skipped)";
  if (phase === "error") return "Download error";
  return phase;
}

// Prefer final merged video file names (e.g., title.mp4). Avoid intermediate format-suffixed names like title.f401.mp4.
function chooseBestFile(files: string[]): string | undefined {
  if (!files || files.length === 0) return undefined;
  const isMp4 = (f: string) => /\.mp4$/i.test(f);
  const isFormatSuffixed = (f: string) => /\.f\d{2,4}\./i.test(f);
  // Prefer mp4 without .f### suffix
  const cleanMp4s = files.filter((f) => isMp4(f) && !isFormatSuffixed(f));
  if (cleanMp4s.length) return cleanMp4s[cleanMp4s.length - 1];
  // Otherwise any mp4 (some setups may keep format id in final name)
  const anyMp4 = files.filter(isMp4);
  if (anyMp4.length) {
    const last = anyMp4[anyMp4.length - 1];
    // Try to derive the merged file by stripping .f### if present
    if (isFormatSuffixed(last)) {
      const derived = last.replace(/\.f\d{2,4}(?=\.)/i, "");
      return derived;
    }
    return last;
  }
  // Fallback: pick last non-temp file
  const nonTemp = files.filter((f) => !/\.(part|temp)$/i.test(f));
  return nonTemp[nonTemp.length - 1] || files[files.length - 1];
}
